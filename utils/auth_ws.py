"""
Shared WebSocket authentication helpers.

Resolve the session token with the same rules as HTTP (Bearer, cookie, then
``?token=`` only if JWT- or mgat_-shaped), then validate Redis session and load
the user from the Redis user cache. Call before ``websocket.accept()`` when
possible; callers that must accept first may run after accept.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Optional, Tuple

from fastapi import WebSocket

from services.auth.http_auth_token import extract_bearer_token_from_websocket
from utils.auth.auth_resolution import load_user_from_jwt_session_token


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

    user = await load_user_from_jwt_session_token(token)
    if user is not None:
        return user, None
    return None, "Invalid token"
