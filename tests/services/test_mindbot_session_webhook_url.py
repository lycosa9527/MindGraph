"""Tests for sessionWebhook URL validation (SSRF guardrails).

validate_session_webhook_url returns (ok: bool, reason: str, pinned_ip: str).
pinned_ip is the first resolved IP when ok=True and host is a hostname.

DNS resolution is mocked via _getaddrinfo_timeout (the async wrapper) rather
than socket.getaddrinfo directly to avoid issues with asyncio.to_thread.
"""

from __future__ import annotations

import socket

import pytest

from services.mindbot.session.webhook_url import validate_session_webhook_url


@pytest.mark.asyncio
async def test_rejects_empty() -> None:
    ok, reason, pinned_ip = await validate_session_webhook_url("")
    assert ok is False
    assert reason
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_rejects_userinfo() -> None:
    ok, _, pinned_ip = await validate_session_webhook_url("https://user:pass@example.com/hook")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_rejects_loopback_ipv4_literal() -> None:
    ok, _, pinned_ip = await validate_session_webhook_url("https://127.0.0.1/session")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_rejects_private_ipv4_literal() -> None:
    ok, _, pinned_ip = await validate_session_webhook_url("https://192.168.0.1/x")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_rejects_loopback_ipv6_literal() -> None:
    ok, _, pinned_ip = await validate_session_webhook_url("https://[::1]/x")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_rejects_http_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP", raising=False)
    ok, _, pinned_ip = await validate_session_webhook_url("http://1.1.1.1/x")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_allowlist_blocks_other_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS", "allowed.example")
    ok, _, pinned_ip = await validate_session_webhook_url("https://other.example/h")
    assert ok is False
    assert pinned_ip == ""


@pytest.mark.asyncio
async def test_allowlist_allows_resolved_public_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS", "allowed.example")

    async def fake_getaddrinfo(_host: str, _port: int, _timeout: float) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", _port))]

    monkeypatch.setattr(
        "services.mindbot.session.webhook_url._getaddrinfo_timeout",
        fake_getaddrinfo,
    )
    ok, reason, _ = await validate_session_webhook_url("https://allowed.example/path")
    assert ok is True
    assert reason == ""


@pytest.mark.asyncio
async def test_returns_pinned_ip_for_resolved_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful hostname validation must return the resolved IP as pinned_ip."""

    async def fake_getaddrinfo(_host: str, _port: int, _timeout: float) -> list:
        # Use 8.8.8.8 (Google DNS) — a globally routable public IP.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", _port))]

    monkeypatch.setattr(
        "services.mindbot.session.webhook_url._getaddrinfo_timeout",
        fake_getaddrinfo,
    )
    ok, reason, pinned_ip = await validate_session_webhook_url("https://api.example.com/hook")
    assert ok is True
    assert reason == ""
    assert pinned_ip == "8.8.8.8", "Pinned IP must be the first resolved address"


@pytest.mark.asyncio
async def test_public_literal_ip_returns_empty_pinned_ip() -> None:
    """A literal public IP host is valid but needs no pinning — pinned_ip must be empty."""
    ok, reason, pinned_ip = await validate_session_webhook_url("https://1.1.1.1/hook")
    assert ok is True
    assert reason == ""
    assert pinned_ip == "", "Literal IP hosts need no DNS pinning"


@pytest.mark.asyncio
async def test_rejects_dns_resolved_private_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hostname that resolves to a private IP must be rejected."""

    async def fake_getaddrinfo(_host: str, _port: int, _timeout: float) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", _port))]

    monkeypatch.setattr(
        "services.mindbot.session.webhook_url._getaddrinfo_timeout",
        fake_getaddrinfo,
    )
    ok, reason, pinned_ip = await validate_session_webhook_url("https://evil.example.com/hook")
    assert ok is False
    assert "disallowed" in reason
    assert pinned_ip == ""
