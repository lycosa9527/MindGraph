"""
Session Management Endpoints
============================

Session management endpoints:
- /me - Get current user profile
- /logout - Logout user
- /session-status - Check session validity

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, Header
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User
from models.messages import get_request_language, Language
from services.redis_activity_tracker import get_activity_tracker
from services.redis_org_cache import org_cache
from services.redis_session_manager import get_session_manager
from utils.auth import get_current_user, get_user_role, is_https

from .dependencies import get_language_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user profile
    """
    # Get organization (use cache with SQLite fallback)
    org = org_cache.get_by_id(current_user.organization_id) if current_user.organization_id else None
    
    # Determine user role
    role = get_user_role(current_user)
    
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "name": current_user.name,
        "avatar": current_user.avatar or "🐈‍⬛",
        "role": role,
        "organization": {
            "id": org.id if org else None,
            "code": org.code if org else None,
            "name": org.name if org else None
        },
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


@router.get("/session-status")
async def get_session_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Check if current session is still valid or has been invalidated.
    
    Returns:
        - {"status": "active"} - Session is valid
        - {"status": "invalidated", "message": "...", "timestamp": "..."} - Session was invalidated
    """
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    try:
        # Get token from request
        token = None
        if request.cookies.get("access_token"):
            token = request.cookies.get("access_token")
        elif request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            return {
                "status": "invalidated",
                "message": "Session invalidated",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check session validity
        session_manager = get_session_manager()
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        
        # Check if session is valid
        if session_manager.is_session_valid(current_user.id, token):
            return {"status": "active"}
        
        # Check for invalidation notification
        notification = session_manager.check_invalidation_notification(current_user.id, token_hash)
        if notification:
            # Clear notification after checking
            session_manager.clear_invalidation_notification(current_user.id, token_hash)
            return {
                "status": "invalidated",
                "message": "Your session was invalidated because you logged in from another location",
                "timestamp": notification.get("timestamp", datetime.utcnow().isoformat()),
                "ip_address": notification.get("ip_address", "unknown")
            }
        
        # Session invalid but no notification (expired or manually deleted)
        return {
            "status": "invalidated",
            "message": "Session expired",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking session status: {e}", exc_info=True)
        # On error, assume session is active (fail-open)
        return {"status": "active"}


@router.post("/logout")
async def logout(
    request: Request, 
    response: Response, 
    current_user: User = Depends(get_current_user),
    lang: str = Depends(get_language_dependency)
):
    """
    Logout user (client-side token removal)
    
    JWT tokens are stateless, so logout happens on client side
    by removing the token from storage.
    """
    # Delete session from Redis
    try:
        # Get token from request to remove specific session (for multiple sessions mode)
        token = None
        if request.cookies.get("access_token"):
            token = request.cookies.get("access_token")
        elif request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        session_manager = get_session_manager()
        session_manager.delete_session(current_user.id, token=token)
    except Exception as e:
        logger.debug(f"Failed to delete session on logout: {e}")
    
    # Clear the cookie (must match original cookie settings)
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=is_https(request)
    )
    
    # End user sessions in activity tracker
    try:
        from services.redis_activity_tracker import get_activity_tracker
        tracker = get_activity_tracker()
        tracker.end_session(user_id=current_user.id)
    except Exception as e:
        logger.debug(f"Failed to end user session on logout: {e}")
    
    logger.info(f"User logged out: {current_user.phone}")
    
    from models.messages import Messages
    return {"message": Messages.success("logged_out", lang)}

