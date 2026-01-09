"""
Session Management Endpoints
============================

Session management endpoints:
- /me - Get current user profile
- /logout - Logout user
- /session-status - Check session validity
- /refresh - Refresh access token using refresh token

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, Header, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User
from models.messages import get_request_language, Language
from services.redis_activity_tracker import get_activity_tracker
from services.redis_org_cache import org_cache
from services.redis_rate_limiter import RedisRateLimiter
from services.redis_session_manager import get_session_manager, get_refresh_token_manager
from services.redis_user_cache import user_cache
from utils.auth import (
    get_current_user, get_user_role, is_https, get_client_ip,
    create_access_token, create_refresh_token, hash_refresh_token, compute_device_hash,
    ACCESS_TOKEN_EXPIRY_MINUTES, REFRESH_TOKEN_EXPIRY_DAYS, get_jwt_secret, JWT_ALGORITHM
)

from .dependencies import get_language_dependency
from .helpers import set_auth_cookies

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for refresh endpoint
_rate_limiter = RedisRateLimiter()


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token from httpOnly cookie.
    
    Security measures:
    - Rate limited: 10 attempts per minute per IP
    - Device binding: Validates device fingerprint
    - Token rotation: Issues new refresh token on each refresh
    - Audit logging: All refresh events are logged
    
    Returns:
        New access token (also set in httpOnly cookie)
    """
    client_ip = get_client_ip(request)
    
    # Rate limiting: 10 refresh attempts per minute per IP
    is_allowed, count, error = _rate_limiter.check_and_record(
        category="token_refresh",
        identifier=client_ip,
        max_attempts=10,
        window_seconds=60
    )
    
    if not is_allowed:
        logger.warning(f"[TokenAudit] Refresh failed - rate limited: ip={client_ip}, attempts={count}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please wait a moment."
        )
    
    # Get refresh token from httpOnly cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        logger.warning(f"[TokenAudit] Refresh failed - no refresh token: ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )
    
    # Get user_id from access token cookie (even if expired, we need to know who the user is)
    # The access token may be expired, but it still contains the user ID
    access_token = request.cookies.get("access_token")
    if not access_token:
        logger.warning(f"[TokenAudit] Refresh failed - no access token: ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided"
        )
    
    # Decode access token without verifying expiration
    try:
        import jwt
        from utils.auth import get_jwt_secret, JWT_ALGORITHM
        
        # Decode without verifying expiration
        payload = jwt.decode(
            access_token, 
            get_jwt_secret(), 
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False}
        )
        user_id = int(payload.get("sub", 0))
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
    except jwt.InvalidTokenError as e:
        logger.warning(f"[TokenAudit] Refresh failed - invalid access token: ip={client_ip}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    # Validate refresh token
    refresh_manager = get_refresh_token_manager()
    old_token_hash = hash_refresh_token(refresh_token_value)
    current_device_hash = compute_device_hash(request)
    
    is_valid, token_data, error_msg = refresh_manager.validate_refresh_token(
        user_id=user_id,
        token_hash=old_token_hash,
        current_device_hash=current_device_hash,
        strict_device_check=True  # Reject if device mismatch
    )
    
    if not is_valid:
        logger.warning(f"[TokenAudit] Refresh failed: user={user_id}, ip={client_ip}, reason={error_msg}")
        
        # Clear invalid cookies
        response.delete_cookie("access_token", path="/", samesite="lax", secure=is_https(request))
        response.delete_cookie("refresh_token", path="/api/auth", samesite="strict", secure=is_https(request))
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg or "Invalid refresh token"
        )
    
    # Get user from database/cache
    user = user_cache.get_by_id(user_id)
    if not user:
        logger.warning(f"[TokenAudit] Refresh failed - user not found: user={user_id}, ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    new_access_token = create_access_token(user)
    
    # Rotate refresh token (revoke old, create new)
    new_refresh_token, new_refresh_hash = create_refresh_token(user_id)
    user_agent = request.headers.get("User-Agent", "")
    
    refresh_manager.rotate_refresh_token(
        user_id=user_id,
        old_token_hash=old_token_hash,
        new_token_hash=new_refresh_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=current_device_hash
    )
    
    # Store new session
    session_manager = get_session_manager()
    session_manager.store_session(user_id, new_access_token)
    
    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token, request)
    
    logger.info(f"[TokenAudit] Token refreshed: user={user_id}, ip={client_ip}")
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60
    }


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
    Logout user - revokes both access token session and refresh token.
    
    Security:
    - Deletes access token session from Redis
    - Revokes refresh token (prevents future token refresh)
    - Clears both httpOnly cookies
    """
    client_ip = get_client_ip(request)
    
    # Delete access token session from Redis
    try:
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
    
    # Revoke refresh token
    try:
        refresh_token_value = request.cookies.get("refresh_token")
        if refresh_token_value:
            refresh_token_hash = hash_refresh_token(refresh_token_value)
            refresh_manager = get_refresh_token_manager()
            refresh_manager.revoke_refresh_token(
                user_id=current_user.id,
                token_hash=refresh_token_hash,
                reason="logout"
            )
    except Exception as e:
        logger.debug(f"Failed to revoke refresh token on logout: {e}")
    
    # Clear access token cookie
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=is_https(request)
    )
    
    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        samesite="strict",
        secure=is_https(request)
    )
    
    # End user sessions in activity tracker
    try:
        tracker = get_activity_tracker()
        tracker.end_session(user_id=current_user.id)
    except Exception as e:
        logger.debug(f"Failed to end user session on logout: {e}")
    
    logger.info(f"[TokenAudit] Logout: user={current_user.id}, phone={current_user.phone}, ip={client_ip}")
    
    from models.messages import Messages
    return {"message": Messages.success("logged_out", lang)}

