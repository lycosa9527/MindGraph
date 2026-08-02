"""Tests for Document Summary server-side URL page fetch (SSRF + stream cap)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncIterator, Optional

import pytest
from fastapi import HTTPException

from services.knowledge import url_page_fetch
from services.knowledge.url_page_fetch import (
    MAX_FETCH_BYTES,
    fallback_title_from_url,
    fetch_url_page_text,
)


def test_fallback_title_from_url_uses_host_and_path() -> None:
    """Missing page titles should not produce scheme-like filenames."""
    title = fallback_title_from_url("https://www.example.com/lesson/photosynthesis")
    assert "https" not in title.lower()
    assert "example.com" in title
    assert "photosynthesis" in title


def test_fallback_title_from_url_host_only() -> None:
    """Host-only URLs become a short slug title."""
    title = fallback_title_from_url("https://news.example.org/")
    assert title == "news.example.org"


@pytest.mark.asyncio
async def test_fetch_blocks_loopback_ip() -> None:
    """Loopback IP literals are rejected before any HTTP request."""
    with pytest.raises(HTTPException) as exc_info:
        await fetch_url_page_text("http://127.0.0.1/secret")
    assert exc_info.value.status_code == 400
    assert "not allowed" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_fetch_blocks_private_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hostnames that resolve to private IPs are rejected."""

    def _fake_getaddrinfo(host: str, *_args: Any, **_kwargs: Any) -> list[tuple]:
        assert host == "internal.example"
        return [(None, None, None, None, ("10.0.0.5", 0))]

    monkeypatch.setattr(url_page_fetch.socket, "getaddrinfo", _fake_getaddrinfo)
    with pytest.raises(HTTPException) as exc_info:
        await fetch_url_page_text("https://internal.example/doc")
    assert exc_info.value.status_code == 400


class _FakeResponse:
    """Minimal httpx streaming response for fetch tests."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        chunks: Optional[list[bytes]] = None,
        location: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {"content-type": content_type}
        if location:
            self.headers["location"] = location
        self.charset_encoding = "utf-8"
        self._chunks = chunks or [
            b"<html><head><title>Lesson</title></head><body><article><p>Plants grow.</p></article></body></html>"
        ]

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        """Yield response body chunks."""
        for chunk in self._chunks:
            yield chunk


class _FakeStreamContext:
    """Async context manager wrapping a fake response."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> bool:
        return False


class _FakeAsyncClient:
    """Records pinned URL / headers for SSRF assertions."""

    last_url: str = ""
    last_headers: dict[str, str] = {}
    last_extensions: Any = None
    response: _FakeResponse = _FakeResponse()
    follow_redirects: Optional[bool] = None

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        _FakeAsyncClient.follow_redirects = kwargs.get("follow_redirects")

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> bool:
        return False

    def stream(self, _method: str, url: str, **kwargs: Any) -> _FakeStreamContext:
        """Capture request target and return the configured fake response."""
        _FakeAsyncClient.last_url = url
        _FakeAsyncClient.last_headers = kwargs.get("headers") or {}
        _FakeAsyncClient.last_extensions = kwargs.get("extensions")
        return _FakeStreamContext(_FakeAsyncClient.response)


@pytest.mark.asyncio
async def test_fetch_pins_dns_ip_and_sets_host_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public DNS result is pinned; Host/SNI keep the original hostname."""

    def _fake_getaddrinfo(host: str, *_args: Any, **_kwargs: Any) -> list[tuple]:
        assert host == "example.com"
        return [(None, None, None, None, ("8.8.8.8", 0))]

    monkeypatch.setattr(url_page_fetch.socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(url_page_fetch.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse()

    text, title = await fetch_url_page_text("https://example.com/a")
    assert title == "Lesson"
    assert "Plants grow." in text
    assert _FakeAsyncClient.last_url.startswith("https://8.8.8.8/")
    assert _FakeAsyncClient.last_headers.get("Host") == "example.com"
    assert _FakeAsyncClient.last_extensions == {"sni_hostname": "example.com"}
    assert _FakeAsyncClient.follow_redirects is False


@pytest.mark.asyncio
async def test_fetch_rejects_redirect_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect status codes are rejected (no follow)."""

    def _fake_getaddrinfo(_host: str, *_args: Any, **_kwargs: Any) -> list[tuple]:
        return [(None, None, None, None, ("1.1.1.1", 0))]

    monkeypatch.setattr(url_page_fetch.socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(url_page_fetch.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse(status_code=302, location="http://evil.example/")

    with pytest.raises(HTTPException) as exc_info:
        await fetch_url_page_text("https://example.com/redir")
    assert exc_info.value.status_code == 400
    assert "Redirect" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_fetch_aborts_stream_when_over_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming aborts once MAX_FETCH_BYTES is exceeded."""

    def _fake_getaddrinfo(_host: str, *_args: Any, **_kwargs: Any) -> list[tuple]:
        return [(None, None, None, None, ("9.9.9.9", 0))]

    monkeypatch.setattr(url_page_fetch.socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(url_page_fetch.httpx, "AsyncClient", _FakeAsyncClient)
    oversize = b"x" * (MAX_FETCH_BYTES // 2 + 1)
    _FakeAsyncClient.response = _FakeResponse(chunks=[oversize, oversize])

    with pytest.raises(HTTPException) as exc_info:
        await fetch_url_page_text("https://example.com/huge")
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_fetch_rejects_non_html_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-HTML binary content types are rejected before extract."""

    def _fake_getaddrinfo(_host: str, *_args: Any, **_kwargs: Any) -> list[tuple]:
        return [(None, None, None, None, ("8.8.4.4", 0))]

    monkeypatch.setattr(url_page_fetch.socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(url_page_fetch.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse(
        content_type="application/pdf",
        chunks=[b"%PDF-1.4 binary"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await fetch_url_page_text("https://example.com/file.pdf")
    assert exc_info.value.status_code == 422


def test_ingest_web_url_route_applies_rate_limit() -> None:
    """Regression: ingest-web-url must rate-limit before fetch/ingest."""
    source = (Path(__file__).resolve().parents[1] / "routers" / "api" / "knowledge_space" / "packages.py").read_text(
        encoding="utf-8"
    )
    assert "doc_summary_ingest_web_url" in source
    assert "check_endpoint_rate_limit" in source
    rate_idx = source.index("doc_summary_ingest_web_url")
    fetch_idx = source.index("fetch_url_page_text(page_url)")
    assert rate_idx < fetch_idx
