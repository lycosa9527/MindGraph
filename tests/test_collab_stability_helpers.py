"""Unit tests for canvas-collab stability helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import Headers

from utils.collab_ws_origin import (
    canvas_collab_websocket_origin_is_allowed,
    parse_collab_ws_allowed_origins,
)


def test_parse_collab_ws_allowed_origins_trims_and_lowercases_scheme_host() -> None:
    got = parse_collab_ws_allowed_origins(
        " https://A.EXAMPLE.com , https://B.example.com ",
    )
    assert got == frozenset({"https://a.example.com", "https://b.example.com"})


def test_origin_allowed_when_policy_off() -> None:
    allowed: frozenset[str] = frozenset()
    hdr = Headers({"origin": "https://evil.example"})
    assert canvas_collab_websocket_origin_is_allowed(hdr, allowed) is True


def test_origin_rejected_when_not_in_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLLAB_WS_ALLOW_MISSING_ORIGIN", raising=False)
    allowed = frozenset({"https://good.example"})
    hdr = Headers({"origin": "https://bad.example"})
    assert canvas_collab_websocket_origin_is_allowed(hdr, allowed) is False


@pytest.mark.asyncio
async def test_workshop_session_closing_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.online_collab.lifecycle import online_collab_session_closing as sc

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"1")
    monkeypatch.setattr(
        "services.online_collab.lifecycle.online_collab_session_closing.get_async_redis",
        lambda: mock_redis,
    )

    assert await sc.workshop_session_is_closing("ABC123") is True
