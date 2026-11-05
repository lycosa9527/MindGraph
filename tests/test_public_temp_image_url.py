"""Public temp-image URLs stay on localhost when the request is loopback."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from routers.api.helpers import build_public_temp_image_url


def _request(host: str, *, forwarded_host: str = "", forwarded_proto: str = "") -> Request:
    """Minimal ASGI request with a Host header."""
    headers = [(b"host", host.encode("ascii"))]
    if forwarded_host:
        headers.append((b"x-forwarded-host", forwarded_host.encode("ascii")))
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode("ascii")))
    return Request(
        {
            "type": "http",
            "asgi": {"spec_version": "2.3", "version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/diagrams/1/png",
            "raw_path": b"/api/diagrams/1/png",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 9),
            "server": ("127.0.0.1", 9527),
        }
    )


def test_loopback_ignores_external_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local Vite/API must not emit the test/prod public host."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://test.mindspringedu.com")
    url = build_public_temp_image_url(_request("localhost:9527"), "diagram_abc.png?sig=1")
    assert url.startswith("http://localhost:9527/api/temp_images/diagram_abc.png")
    assert "test.mindspringedu.com" not in url


def test_remote_request_uses_external_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phones and public hosts still get EXTERNAL_BASE_URL."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://test.mindspringedu.com")
    url = build_public_temp_image_url(_request("test.mindspringedu.com"), "diagram_abc.png?sig=1")
    assert url == "https://test.mindspringedu.com/api/temp_images/diagram_abc.png?sig=1"


def test_http_external_base_url_is_upgraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A public EXTERNAL_BASE_URL set with http still emits https."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", "http://test.mindspringedu.com")
    url = build_public_temp_image_url(_request("test.mindspringedu.com"), "diagram_abc.png?sig=1")
    assert url == "https://test.mindspringedu.com/api/temp_images/diagram_abc.png?sig=1"


def test_forwarded_http_proto_is_upgraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inbound http behind the proxy does not leak into the public image URL."""
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    request = _request(
        "www.mindspringedu.com",
        forwarded_host="www.mindspringedu.com",
        forwarded_proto="http",
    )
    url = build_public_temp_image_url(request, "diagram_abc.png?sig=1")
    assert url == "https://www.mindspringedu.com/api/temp_images/diagram_abc.png?sig=1"


def test_public_request_scheme_http_is_upgraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """EXTERNAL_HOST fallback uses https for a public hostname."""
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    monkeypatch.setenv("EXTERNAL_HOST", "mg.mindspringedu.com")
    url = build_public_temp_image_url(_request("mg.mindspringedu.com"), "a.png?sig=1")
    assert url == "https://www.mindspringedu.com/api/temp_images/a.png?sig=1"
