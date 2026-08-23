"""WebSocket auth accepts mgat_ + account for Word add-in Voice dialog."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, WebSocket, status

from services.infrastructure.utils.log_user_context import bind_log_user, format_log_user_suffix
from utils.auth_ws import authenticate_websocket_user


def _ws(
    *,
    authorization: str = "",
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> WebSocket:
    hdrs = dict(headers or {})
    if authorization:
        hdrs["Authorization"] = authorization
    ws = MagicMock(spec=WebSocket)
    ws.headers = hdrs
    ws.cookies = {}
    ws.query_params = query or {}
    ws.state = SimpleNamespace()
    ws.url = SimpleNamespace(path="/api/ws/voice-notes")
    return ws


@pytest.mark.asyncio
async def test_authenticate_websocket_mgat_query_account() -> None:
    """mgat_ via ?token= with ?account= validates through validate_user_token."""
    user = SimpleNamespace(id=3, name="Roy", phone=None, email=None)
    ws = _ws(query={"token": "mgat_abc", "account": "13800138000", "client": "word-addin"})
    with patch(
        "utils.auth_ws.validate_user_token",
        new=AsyncMock(return_value=user),
    ) as validate:
        got, err = await authenticate_websocket_user(ws)
        try:
            assert err is None
            assert got is user
            assert format_log_user_suffix() == " user=Roy(3)"
            validate.assert_awaited_once_with("mgat_abc", "13800138000", request=ws)
        finally:
            bind_log_user(None)


@pytest.mark.asyncio
async def test_authenticate_websocket_mgat_missing_account() -> None:
    """mgat_ without account phone is rejected."""
    ws = _ws(query={"token": "mgat_abc"})
    got, err = await authenticate_websocket_user(ws)
    assert got is None
    assert err == "Account required"


@pytest.mark.asyncio
async def test_authenticate_websocket_mgat_invalid_maps_detail() -> None:
    """HTTPException detail from validate_user_token becomes the auth error."""
    ws = _ws(
        authorization="Bearer mgat_abc",
        headers={"X-MG-Account": "13800138000"},
    )
    with patch(
        "utils.auth_ws.validate_user_token",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        ),
    ):
        got, err = await authenticate_websocket_user(ws)
    assert got is None
    assert err == "Invalid or expired token"
