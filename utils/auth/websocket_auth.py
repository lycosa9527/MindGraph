"""
WebSocket Authentication for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Authentication functions for WebSocket connections.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import select

from models.domain.auth import User
from services.auth.http_auth_token import extract_bearer_token_from_websocket
from utils.auth_ws import authenticate_websocket_user
from utils.db.session_open import system_rls_session
from . import auth_resolution
from .tokens import decode_access_token

logger = logging.getLogger(__name__)

# Redis modules (optional)
_redis = SimpleNamespace(
    available=False,
    get_session_manager=None,
    user_cache=None,
)

try:
    from services.redis.session.redis_session_manager import get_session_manager
    from services.redis.cache.redis_user_cache import user_cache

    _redis.available = True
    _redis.get_session_manager = get_session_manager
    _redis.user_cache = user_cache
except ImportError:
    pass


async def get_current_user_ws(websocket) -> User:
    """
    Get current user from WebSocket connection.

    Prefer ``authenticate_websocket_user`` from ``utils.auth_ws`` for new code.
    WebSocket routes do not run HTTP middleware; DB fallback uses system RLS.
    """
    user, _error = await authenticate_websocket_user(websocket)
    if user is not None:
        return user

    token = extract_bearer_token_from_websocket(websocket)
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        raise WebSocketDisconnect(code=4001, reason="No token provided")

    try:
        user = await auth_resolution.load_user_from_jwt_session_token(token)
        if user is not None:
            return user

        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            raise WebSocketDisconnect(code=4001, reason="Invalid token")

        if not _redis.available or _redis.get_session_manager is None:
            await websocket.close(code=4001, reason="Redis unavailable")
            raise WebSocketDisconnect(code=4001, reason="Redis unavailable")

        session_manager = _redis.get_session_manager()
        if not await session_manager.is_session_valid(int(user_id), token):
            await websocket.close(code=4001, reason="Session expired or invalidated")
            raise WebSocketDisconnect(code=4001, reason="Session expired or invalidated")

        cached_user = None
        if _redis.user_cache:
            cached_user = await _redis.user_cache.get_by_id(int(user_id))

        if cached_user:
            return cached_user

        async with system_rls_session() as db:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()
            if user:
                db.expunge(user)
                if _redis.user_cache:
                    await _redis.user_cache.cache_user(user)

        if not user:
            await websocket.close(code=4001, reason="User not found")
            raise WebSocketDisconnect(code=4001, reason="User not found")

        return user

    except HTTPException as exc:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001, reason=str(exc.detail)) from exc
