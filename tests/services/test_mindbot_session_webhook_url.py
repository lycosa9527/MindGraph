"""Tests for sessionWebhook URL validation (SSRF guardrails)."""

from __future__ import annotations

import socket

import pytest

from services.mindbot.session_webhook_url import validate_session_webhook_url


@pytest.mark.asyncio
async def test_rejects_empty() -> None:
    ok, reason = await validate_session_webhook_url("")
    assert ok is False
    assert reason


@pytest.mark.asyncio
async def test_rejects_userinfo() -> None:
    ok, _ = await validate_session_webhook_url("https://user:pass@example.com/hook")
    assert ok is False


@pytest.mark.asyncio
async def test_rejects_loopback_ipv4_literal() -> None:
    ok, _ = await validate_session_webhook_url("https://127.0.0.1/session")
    assert ok is False


@pytest.mark.asyncio
async def test_rejects_private_ipv4_literal() -> None:
    ok, _ = await validate_session_webhook_url("https://192.168.0.1/x")
    assert ok is False


@pytest.mark.asyncio
async def test_rejects_loopback_ipv6_literal() -> None:
    ok, _ = await validate_session_webhook_url("https://[::1]/x")
    assert ok is False


@pytest.mark.asyncio
async def test_rejects_http_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HTTP", raising=False)
    ok, _ = await validate_session_webhook_url("http://1.1.1.1/x")
    assert ok is False


@pytest.mark.asyncio
async def test_allowlist_blocks_other_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS", "allowed.example")
    ok, _ = await validate_session_webhook_url("https://other.example/h")
    assert ok is False


@pytest.mark.asyncio
async def test_allowlist_allows_resolved_public_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_SESSION_WEBHOOK_ALLOW_HOSTS", "allowed.example")

    def fake_gai(host: str, port: int, *_args: object, **_kwargs: object) -> list:
        if host == "allowed.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]
        raise socket.gaierror("nxdomain")

    monkeypatch.setattr(
        "services.mindbot.session_webhook_url.socket.getaddrinfo",
        fake_gai,
    )
    ok, reason = await validate_session_webhook_url("https://allowed.example/path")
    assert ok is True
    assert reason == ""
