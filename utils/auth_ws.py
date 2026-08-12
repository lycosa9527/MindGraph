"""
Shared WebSocket authentication helpers.

Resolve the session token with the same rules as HTTP (Bearer, cookie, then
``?token=`` only if JWT- or mgat_-shaped). JWT sessions load from Redis user
cache; ``mgat_`` tokens require account phone (``X-MG-Account`` header or
``account`` / ``phone`` query) — used by the Word add-in Voice dialog.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Optional, Tuple

from fastapi import HTTPException, WebSocket

from services.auth.bearer_token import extract_bearer_token_from_websocket
from utils.auth.auth_resolution import load_user_from_jwt_session_token
from utils.auth.user_tokens import validate_user_token


def _websocket_account_phone(websocket: WebSocket) -> str:
    """Account phone for mgat_ WebSocket auth (header, then query)."""
    header = (websocket.headers.get("X-MG-Account") or "").strip()
    if header:
        return header
    account = (websocket.query_params.get("account") or "").strip()
    if account:
        return account
    return (websocket.query_params.get("phone") or "").strip()


async def authenticate_websocket_user(
    websocket: WebSocket,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Validate credentials and return the cached user, or an error reason.

    Returns:
        (user, None) on success, (None, error_reason) on failure.
    """
    token = extract_bearer_token_from_websocket(websocket)
    if not token:
        return None, "No authentication token"

    if token.startswith("mgat_"):
        account = _websocket_account_phone(websocket)
        if not account:
            return None, "Account required"
        try:
            user = await validate_user_token(token, account, request=websocket)
        except HTTPException as exc:
            detail = exc.detail
            if isinstance(detail, str) and detail.strip():
                return None, detail
            return None, "Invalid token"
        return user, None

    user = await load_user_from_jwt_session_token(token)
    if user is not None:
        return user, None
    return None, "Invalid token"
