"""
Shared WebSocket authentication helpers.

Decode JWT from query or ``access_token`` cookie, validate Redis session,
and load the user from the Redis user cache. Call before ``websocket.accept()``
when possible; callers that must accept first may run after accept.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Optional, Tuple

from fastapi import HTTPException, WebSocket

from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
from services.redis.session.redis_session_manager import (
    get_session_manager as redis_get_session_manager,
)
from utils.auth import decode_access_token


async def authenticate_websocket_user(
    websocket: WebSocket,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Validate credentials and return the cached user, or an error reason.

    Returns:
        (user, None) on success, (None, error_reason) on failure.
    """
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get("access_token")
    if not token:
        return None, "No authentication token"

    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None, "Invalid token"

    user_id_str = payload.get("sub")
    user_id: Optional[int] = None
    if user_id_str is not None:
        try:
            user_id = int(user_id_str)
        except (TypeError, ValueError):
            user_id = None
    if user_id is None:
        return None, "Invalid token payload"

    session_mgr = redis_get_session_manager()
    if session_mgr and not session_mgr.is_session_valid(user_id, token):
        return None, "Session expired"

    user = await redis_user_cache.get_by_id(user_id)
    if not user:
        return None, "User not found"
    return user, None
