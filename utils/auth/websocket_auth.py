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

from fastapi import Depends, HTTPException
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from .tokens import decode_access_token

logger = logging.getLogger(__name__)

# Redis modules (optional)
_REDIS_AVAILABLE = False
_get_session_manager = None
_user_cache = None

try:
    from services.redis.session.redis_session_manager import get_session_manager
    from services.redis.cache.redis_user_cache import user_cache
    _REDIS_AVAILABLE = True
    _get_session_manager = get_session_manager
    _user_cache = user_cache
except ImportError:
    pass


async def get_current_user_ws(
    websocket,
    db: Session = Depends(get_db)
) -> User:
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
    token = websocket.query_params.get('token')

    # Try cookies if no token in query
    if not token:
        token = websocket.cookies.get('access_token')

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        raise WebSocketDisconnect(code=4001, reason="No token provided")

    try:
        # Decode and validate token
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            raise WebSocketDisconnect(code=4001, reason="Invalid token")

        # Session validation: Check if session exists in Redis
        if not _REDIS_AVAILABLE:
            await websocket.close(code=4001, reason="Redis unavailable")
            raise WebSocketDisconnect(code=4001, reason="Redis unavailable")

        if _get_session_manager is None:
            await websocket.close(code=4001, reason="Session manager unavailable")
            raise WebSocketDisconnect(code=4001, reason="Session manager unavailable")

        session_manager = _get_session_manager()
        if not session_manager.is_session_valid(int(user_id), token):
            await websocket.close(code=4001, reason="Session expired or invalidated")
            raise WebSocketDisconnect(code=4001, reason="Session expired or invalidated")

        # Use cache for user lookup (with SQLite fallback)
        user = None
        if _user_cache:
            user = _user_cache.get_by_id(int(user_id))

        if not user:
            # Fallback to DB if not in cache
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                db.expunge(user)
                if _user_cache:
                    _user_cache.cache_user(user)

        if not user:
            await websocket.close(code=4001, reason="User not found")
            raise WebSocketDisconnect(code=4001, reason="User not found")

        return user

    except HTTPException as e:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001, reason=str(e.detail)) from e
