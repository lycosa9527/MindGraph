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
import time
from datetime import datetime
from typing import Optional

from jose import jwt, JWTError

from fastapi import APIRouter, Depends, Request, Response, Header, HTTPException, status

from models import User, Messages, get_request_language, Language
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.cache.redis_org_cache import org_cache
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from services.redis.session.redis_session_manager import (
    get_session_manager, get_refresh_token_manager
)
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import (
    get_current_user, get_user_role, is_https, get_client_ip,
    create_access_token, create_refresh_token, hash_refresh_token,
    compute_device_hash, ACCESS_TOKEN_EXPIRY_MINUTES, get_jwt_secret,
    JWT_ALGORITHM
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
    response: Response
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

    # DEBUG: Log refresh attempt entry point
    logger.info("[TokenAudit] /refresh called: ip=%s", client_ip)

    # Rate limiting: 10 refresh attempts per minute per IP
    is_allowed, count, _ = _rate_limiter.check_and_record(
        category="token_refresh",
        identifier=client_ip,
        max_attempts=10,
        window_seconds=60
    )

    if not is_allowed:
        logger.info(
            "[TokenAudit] Refresh FAILED - rate limited: ip=%s, attempts=%s",
            client_ip, count
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please wait a moment."
        )

    # Get refresh token from httpOnly cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        logger.info(
            "[TokenAudit] Refresh FAILED - no refresh token cookie: ip=%s",
            client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )

    # Hash refresh token once (used for both reverse lookup and validation)
    refresh_manager = get_refresh_token_manager()
    old_token_hash = hash_refresh_token(refresh_token_value)

    # Get user_id from access token cookie (even if expired, we need to know who the user is)
    # The access token may be expired, but it still contains the user ID
    # If access token cookie is missing, try to find user_id from refresh token hash (reverse lookup)
    access_token = request.cookies.get("access_token")
    user_id = None
    token_exp = 0

    if access_token:
        # Try to decode access token without verifying expiration
        try:
            # Decode without verifying expiration
            payload = jwt.decode(
                access_token,
                get_jwt_secret(),
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False}
            )
            user_id = int(payload.get("sub", 0))
            token_exp = payload.get("exp", 0)

            if not user_id:
                logger.info(
                    "[TokenAudit] Refresh - no user_id in token payload, "
                    "will try reverse lookup: ip=%s",
                    client_ip
                )
                user_id = None
            else:
                # DEBUG: Log token expiry info
                now = int(time.time())
                expired_ago = now - token_exp if token_exp > 0 else -1
                logger.info(
                    "[TokenAudit] Decoded access token: user=%s, exp=%s, "
                    "expired_ago=%ss, ip=%s",
                    user_id, token_exp, expired_ago, client_ip
                )

        except JWTError as jwt_error:
            logger.info(
                "[TokenAudit] Refresh - invalid access token, "
                "will try reverse lookup: ip=%s, error=%s",
                client_ip, jwt_error
            )
            user_id = None

    # If we don't have user_id from access token, try reverse lookup from refresh token hash
    if not user_id:
        user_id = refresh_manager.find_user_id_from_token(old_token_hash)

        if not user_id:
            logger.info(
                "[TokenAudit] Refresh FAILED - cannot determine user_id "
                "(no access token and refresh token not found): ip=%s",
                client_ip
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cannot determine user identity. Please log in again."
            )

        logger.info(
            "[TokenAudit] Found user_id from refresh token reverse lookup: "
            "user=%s, ip=%s",
            user_id, client_ip
        )

    # DEBUG: Log device fingerprint headers used for hash
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")
    sec_ch_platform = request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = request.headers.get("Sec-CH-UA-Mobile", "")
    logger.info(
        "[TokenAudit] Device fingerprint headers: user=%s, UA=%s..., "
        "lang=%s, encoding=%s, platform=%s, mobile=%s",
        user_id, user_agent[:50], accept_language[:20],
        accept_encoding[:20], sec_ch_platform, sec_ch_mobile
    )

    # Validate refresh token (refresh_manager and old_token_hash already computed above)
    current_device_hash = compute_device_hash(request)

    logger.info(
        "[TokenAudit] Validating refresh token: user=%s, "
        "refresh_token=%s..., current_device=%s",
        user_id, old_token_hash[:8], current_device_hash
    )

    is_valid, token_data, error_msg = refresh_manager.validate_refresh_token(
        user_id=user_id,
        token_hash=old_token_hash,
        current_device_hash=current_device_hash,
        strict_device_check=True  # Reject if device mismatch
    )

    if not is_valid:
        stored_device = (
            token_data.get("device_hash", "unknown") if token_data else "no_data"
        )
        logger.info(
            "[TokenAudit] Refresh FAILED: user=%s, ip=%s, reason=%s, "
            "stored_device=%s, current_device=%s",
            user_id, client_ip, error_msg, stored_device, current_device_hash
        )

        # Clear invalid cookies
        response.delete_cookie(
            "access_token", path="/", samesite="lax", secure=is_https(request)
        )
        response.delete_cookie(
            "refresh_token", path="/api/auth", samesite="strict",
            secure=is_https(request)
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg or "Invalid refresh token"
        )

    # Get user from database/cache
    user = user_cache.get_by_id(user_id)
    if not user:
        logger.warning(
            "[TokenAudit] Refresh failed - user not found: user=%s, ip=%s",
            user_id, client_ip
        )
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

    # Remove old access token session before storing new one
    # This prevents session accumulation on token refresh
    session_manager = get_session_manager()
    old_access_token = request.cookies.get("access_token")
    if old_access_token:
        session_manager.delete_session(user_id, token=old_access_token)

    # Store new session with device hash for same-device session tracking
    session_manager.store_session(user_id, new_access_token, device_hash=current_device_hash)

    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token, request)

    logger.info(
        "[TokenAudit] Token refreshed: user=%s, ip=%s",
        user_id, client_ip
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user profile
    """
    try:
        # Get organization (use cache with database fallback)
        org = None
        try:
            if current_user.organization_id:
                org = org_cache.get_by_id(current_user.organization_id)
        except Exception as org_error:
            logger.warning(
                "Error getting organization from cache: %s",
                org_error, exc_info=True
            )
            # Continue without org - not critical

        # Determine user role
        try:
            role = get_user_role(current_user)
        except Exception as role_error:
            logger.error(
                "Error determining user role: %s",
                role_error, exc_info=True
            )
            role = "user"  # Default fallback

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
            "last_login": (
                current_user.last_login.isoformat()
                if current_user.last_login else None
            )
        }
    except Exception as me_error:
        logger.error(
            "Error in /me endpoint: %s",
            me_error, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        ) from me_error


@router.get("/session-status")
async def get_session_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Check if current session is still valid or has been invalidated.

    Note: Session validity is already checked by get_current_user dependency.
    This endpoint only checks for invalidation notifications (e.g., max device limit).

    Returns:
        - {"status": "active"} - Session is valid
        - {"status": "invalidated", "message": "...", "timestamp": "..."} - Session was invalidated
    """
    accept_language = request.headers.get("Accept-Language", "")
    get_request_language(x_language, accept_language)
    client_ip = get_client_ip(request)

    logger.info(
        "[TokenAudit] /session-status called: user=%s, ip=%s",
        current_user.id, client_ip
    )

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
            logger.info(
                "[TokenAudit] Session status: INVALIDATED (no token): user=%s",
                current_user.id
            )
            return {
                "status": "invalidated",
                "message": "Session invalidated",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Session is already validated by get_current_user dependency
        # Only check for invalidation notifications (e.g., max device limit exceeded)
        session_manager = get_session_manager()
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        # Check for invalidation notification
        notification = session_manager.check_invalidation_notification(
            current_user.id, token_hash
        )
        if notification:
            # Clear notification after checking
            session_manager.clear_invalidation_notification(
                current_user.id, token_hash
            )
            logger.info(
                "[TokenAudit] Session status: INVALIDATED (max devices): "
                "user=%s, notification_ip=%s",
                current_user.id,
                notification.get('ip_address', 'unknown')
            )
            return {
                "status": "invalidated",
                "message": "Session ended: maximum device limit exceeded",
                "timestamp": notification.get(
                    "timestamp", datetime.utcnow().isoformat()
                ),
                "ip_address": notification.get("ip_address", "unknown")
            }

        # Session is valid (already validated by get_current_user)
        # No need to call is_session_valid again - it's redundant
        logger.debug(
            "[TokenAudit] Session status: ACTIVE: user=%s, token=%s...",
            current_user.id, token_hash[:8]
        )
        return {"status": "active"}
    except Exception as status_error:
        logger.error(
            "Error checking session status: %s",
            status_error, exc_info=True
        )
        # On error, assume session is active (fail-open)
        return {"status": "active"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency)
):
    """
    Logout user - revokes both access token session and refresh token.

    Security:
    - Deletes access token session from Redis
    - Revokes refresh token (prevents future token refresh)
    - Clears both httpOnly cookies
    """
    client_ip = get_client_ip(request)
    logger.info(
        "[TokenAudit] /logout called: user=%s, ip=%s",
        current_user.id, client_ip
    )

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
        token_hint = (
            hashlib.sha256(token.encode('utf-8')).hexdigest()[:8]
            if token else "none"
        )
        logger.info(
            "[TokenAudit] Logout deleting session: user=%s, token=%s...",
            current_user.id, token_hint
        )
        session_manager.delete_session(current_user.id, token=token)
    except Exception as delete_error:
        logger.info(
            "[TokenAudit] Logout session delete failed: user=%s, error=%s",
            current_user.id, delete_error
        )

    # Revoke refresh token
    try:
        refresh_token_value = request.cookies.get("refresh_token")
        if refresh_token_value:
            refresh_token_hash = hash_refresh_token(refresh_token_value)
            logger.info(
                "[TokenAudit] Logout revoking refresh token: user=%s, "
                "token=%s...",
                current_user.id, refresh_token_hash[:8]
            )
            refresh_manager = get_refresh_token_manager()
            refresh_manager.revoke_refresh_token(
                user_id=current_user.id,
                token_hash=refresh_token_hash,
                reason="logout"
            )
        else:
            logger.info(
                "[TokenAudit] Logout: no refresh token cookie to revoke: "
                "user=%s",
                current_user.id
            )
    except Exception as revoke_error:
        logger.info(
            "[TokenAudit] Logout refresh token revoke failed: user=%s, "
            "error=%s",
            current_user.id, revoke_error
        )

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
    except Exception as tracker_error:
        logger.debug(
            "Failed to end user session on logout: %s",
            tracker_error
        )

    logger.info(
        "[TokenAudit] Logout: user=%s, phone=%s, ip=%s",
        current_user.id, current_user.phone, client_ip
    )

    return {"message": Messages.success("logged_out", lang)}
