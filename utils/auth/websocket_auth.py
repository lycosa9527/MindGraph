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

from fastapi import Depends, HTTPException
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
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


async def get_current_user_ws(websocket, db: AsyncSession = Depends(get_async_db)) -> User:
    """
    Get current user from WebSocket connection.
    Extracts JWT from query params or cookies.

    Args:
        websocket: WebSocket connection
        db: Database session

    Returns:
        User object if authenticated

    Raises:
        WebSocketDisconnect: If authentication fails
    """
    # Try query params first
    token = websocket.query_params.get("token")

    # Try cookies if no token in query
    if not token:
        token = websocket.cookies.get("access_token")

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

        if not _redis.available:
            await websocket.close(code=4001, reason="Redis unavailable")
            raise WebSocketDisconnect(code=4001, reason="Redis unavailable")

        if _redis.get_session_manager is None:
            await websocket.close(code=4001, reason="Session manager unavailable")
            raise WebSocketDisconnect(code=4001, reason="Session manager unavailable")

        session_manager = _redis.get_session_manager()
        if not await session_manager.is_session_valid(int(user_id), token):
            await websocket.close(code=4001, reason="Session expired or invalidated")
            raise WebSocketDisconnect(code=4001, reason="Session expired or invalidated")

        user = None
        if _redis.user_cache:
            user = await _redis.user_cache.get_by_id(int(user_id))

        if not user:
            # Fallback to DB if not in cache
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

    except HTTPException as e:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001, reason=str(e.detail)) from e
