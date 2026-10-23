"""Unit tests for canvas-collab stability helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import Headers

from services.online_collab.lifecycle import online_collab_session_closing as sc
from utils.collab_ws_origin import (
    canvas_collab_websocket_origin_is_allowed,
    close_ws_if_origin_disallowed,
    load_collab_ws_allowed_origins_env,
    parse_collab_ws_allowed_origins,
)


class _OriginSocket:
    """Minimal socket for the production CSWSH close path."""

    def __init__(self, origin: str) -> None:
        """Store the Origin header the browser sent."""
        self.headers = Headers({"origin": origin})
        self.closed: list[tuple[int, str]] = []

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Record a close so the test can see a rejection."""
        self.closed.append((code, reason))


def test_parse_collab_ws_allowed_origins_trims_and_lowercases_scheme_host() -> None:
    """Test parse collab ws allowed origins trims and lowercases scheme host."""
    got = parse_collab_ws_allowed_origins(
        " https://A.EXAMPLE.com , https://B.example.com ",
    )
    assert got == frozenset({"https://a.example.com", "https://b.example.com"})


def test_origin_allowed_when_policy_off() -> None:
    """Test origin allowed when policy off."""
    allowed: frozenset[str] = frozenset()
    hdr = Headers({"origin": "https://evil.example"})
    assert canvas_collab_websocket_origin_is_allowed(hdr, allowed) is True


def test_origin_rejected_when_not_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test origin rejected when not in list."""
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    allowed = frozenset({"https://good.example"})
    hdr = Headers({"origin": "https://bad.example"})
    assert canvas_collab_websocket_origin_is_allowed(hdr, allowed) is False


def test_origin_rejected_when_header_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Native clients must send Origin; missing header is not first-party."""
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    allowed = frozenset({"https://good.example"})
    assert canvas_collab_websocket_origin_is_allowed(Headers({}), allowed) is False


def test_origin_allowed_when_matches_public_site(monkeypatch: pytest.MonkeyPatch) -> None:
    """EXTERNAL_BASE_URL is a first-party Origin (Word Voice, watch server URL)."""
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://mg.example.com")
    monkeypatch.setenv("COLLAB_WS_ALLOWED_ORIGINS", "https://app.example.com")
    allowed = load_collab_ws_allowed_origins_env()
    hdr = Headers({"origin": "https://mg.example.com"})
    assert canvas_collab_websocket_origin_is_allowed(hdr, allowed) is True
    evil = Headers({"origin": "https://evil.example"})
    assert canvas_collab_websocket_origin_is_allowed(evil, allowed) is False


def test_load_origins_stays_off_without_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """EXTERNAL_BASE_URL alone does not turn CSWSH policy on."""
    monkeypatch.delenv("COLLAB_WS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://mg.example.com")
    assert load_collab_ws_allowed_origins_env() == frozenset()


def test_www_and_mg_allowed_whenever_policy_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """www and mg HTTPS are first-party even when the allowlist names neither."""
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    monkeypatch.setenv("COLLAB_WS_ALLOWED_ORIGINS", "https://app.example.com")
    allowed = load_collab_ws_allowed_origins_env()
    www = Headers({"origin": "https://www.mindspringedu.com"})
    mg = Headers({"origin": "https://mg.mindspringedu.com"})
    assert canvas_collab_websocket_origin_is_allowed(www, allowed) is True
    assert canvas_collab_websocket_origin_is_allowed(mg, allowed) is True
    http_www = Headers({"origin": "http://www.mindspringedu.com"})
    assert canvas_collab_websocket_origin_is_allowed(http_www, allowed) is False
    http_mg = Headers({"origin": "http://mg.mindspringedu.com"})
    assert canvas_collab_websocket_origin_is_allowed(http_mg, allowed) is False
    other = Headers({"origin": "https://evil.example"})
    assert canvas_collab_websocket_origin_is_allowed(other, allowed) is False


@pytest.mark.asyncio
async def test_production_www_origin_is_not_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The logged www upgrade must pass even when the allowlist names neither host."""
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    monkeypatch.delenv("EXTERNAL_BASE_URL", raising=False)
    monkeypatch.setenv("COLLAB_WS_ALLOWED_ORIGINS", "https://app.example.com")
    logged = _OriginSocket("https://www.mindspringedu.com")
    folded = _OriginSocket("HTTPS://WWW.MindSpringEdu.com/")
    evil = _OriginSocket("https://evil.example")
    assert await close_ws_if_origin_disallowed(logged, "MindmateCollab") is False
    assert await close_ws_if_origin_disallowed(folded, "SlideRemote") is False
    assert await close_ws_if_origin_disallowed(evil, "MindmateNotify") is True
    assert not logged.closed
    assert not folded.closed
    assert evil.closed == [(1008, "Cross-origin connection is not allowed")]


@pytest.mark.asyncio
async def test_workshop_session_closing_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test workshop session closing probe."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"1")
    monkeypatch.setattr(
        "services.online_collab.lifecycle.online_collab_session_closing.get_async_redis",
        lambda: mock_redis,
    )

    assert await sc.workshop_session_is_closing("ABC123") is True
