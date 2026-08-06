"""Kitty WS reject must accept then close so browsers see real close codes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.websockets import WebSocketState

from services.kitty.ws.lifecycle import reject_kitty_websocket


@pytest.mark.asyncio
async def test_reject_kitty_websocket_accepts_then_closes_with_code() -> None:
    websocket = MagicMock()
    websocket.client_state = WebSocketState.CONNECTING

    async def _accept() -> None:
        websocket.client_state = WebSocketState.CONNECTED

    websocket.accept = AsyncMock(side_effect=_accept)
    websocket.close = AsyncMock()

    await reject_kitty_websocket(websocket, 4001, "Authentication failed")

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once()
    assert websocket.close.await_args.kwargs["code"] == 4001
    assert "Authentication" in websocket.close.await_args.kwargs["reason"]


@pytest.mark.asyncio
async def test_reject_kitty_websocket_skips_accept_when_already_connected() -> None:
    websocket = MagicMock()
    websocket.client_state = WebSocketState.CONNECTED
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    await reject_kitty_websocket(websocket, 4403, "Diagram scope access denied")

    websocket.accept.assert_not_awaited()
    websocket.close.assert_awaited_once()
    assert websocket.close.await_args.kwargs["code"] == 4403
