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
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models import Language, Messages, User, get_request_language
from models.requests.requests_auth import UpdateProfileNameRequest
from services.auth.thinking_coin.checkin_service import ensure_wallet_bootstrap
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.wallet_payload import build_wallet_payload
from services.auth.vpn_geo_enforcement import record_vpn_refresh_last_ip
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.session.redis_session_manager import (
    get_refresh_token_manager,
    get_session_manager,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS
from utils.auth import (
    JWT_ALGORITHM,
    compute_device_hash,
    create_access_token,
    create_refresh_token,
    get_client_ip,
    get_current_user,
    get_jwt_secret,
    get_user_role,
    hash_refresh_token,
    is_https,
)
from utils.auth.request_helpers import CSRF_COOKIE_NAME
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled
from utils.user_avatar_defaults import DEFAULT_USER_AVATAR_EMOJI

from .dependencies import get_language_dependency
from .helpers import auth_session_json_metadata, set_auth_cookies
from .org_profile import organization_session_payload

_record_vpn_refresh_last_ip = record_vpn_refresh_last_ip

logger = logging.getLogger(__name__)

router = APIRouter()


# Rate limiter for refresh endpoint
_rate_limiter = RedisRateLimiter()


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
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
    is_allowed, count, _ = await _rate_limiter.check_and_record(
        category="token_refresh",
        identifier=client_ip,
        max_attempts=10,
        window_seconds=60,
    )

    if not is_allowed:
        logger.info(
            "[TokenAudit] Refresh FAILED - rate limited: ip=%s, attempts=%s",
            client_ip,
            count,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please wait a moment.",
        )

    # Get refresh token from httpOnly cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        logger.info("[TokenAudit] Refresh FAILED - no refresh token cookie: ip=%s", client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided")

    # Hash refresh token once (used for both reverse lookup and validation)
    refresh_manager = get_refresh_token_manager()
    old_token_hash = hash_refresh_token(refresh_token_value)

    # Prefer reverse lookup from refresh token (authoritative for reuse detection)
    user_id = await refresh_manager.find_user_id_from_token(old_token_hash)
    token_exp = 0

    access_token = request.cookies.get("access_token")
    if not user_id and access_token:
        try:
            payload = jwt.decode(
                access_token,
                get_jwt_secret(),
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            user_id = int(payload.get("sub", 0)) or None
            token_exp = payload.get("exp", 0)
            if user_id:
                now = int(time.time())
                expired_ago = now - token_exp if token_exp > 0 else -1
                logger.info(
                    "[TokenAudit] Decoded access token: user=%s, exp=%s, expired_ago=%ss, ip=%s",
                    user_id,
                    token_exp,
                    expired_ago,
                    client_ip,
                )
        except JWTError as jwt_error:
            logger.info(
                "[TokenAudit] Refresh - invalid access token: ip=%s, error=%s",
                client_ip,
                jwt_error,
            )
            user_id = None

    if not user_id:
        logger.info(
            "[TokenAudit] Refresh FAILED - cannot determine user_id (refresh token not found): ip=%s",
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot determine user identity. Please log in again.",
        )

    # DEBUG: Log device fingerprint headers used for hash
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")
    sec_ch_platform = request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = request.headers.get("Sec-CH-UA-Mobile", "")
    logger.info(
        "[TokenAudit] Device fingerprint headers: user=%s, UA=%s..., lang=%s, encoding=%s, platform=%s, mobile=%s",
        user_id,
        user_agent[:50],
        accept_language[:20],
        accept_encoding[:20],
        sec_ch_platform,
        sec_ch_mobile,
    )

    # Validate refresh token (refresh_manager and old_token_hash already computed above)
    current_device_hash = compute_device_hash(request)

    logger.info(
        "[TokenAudit] Validating refresh token: user=%s, refresh_token=%s..., current_device=%s",
        user_id,
        old_token_hash[:8],
        current_device_hash,
    )

    is_valid, token_data, error_msg = await refresh_manager.validate_refresh_token(
        user_id=user_id,
        token_hash=old_token_hash,
        current_device_hash=current_device_hash,
        strict_device_check=True,  # Reject if device mismatch
    )

    if not is_valid:
        stored_device = token_data.get("device_hash", "unknown") if token_data else "no_data"
        logger.info(
            "[TokenAudit] Refresh FAILED: user=%s, ip=%s, reason=%s, stored_device=%s, current_device=%s",
            user_id,
            client_ip,
            error_msg,
            stored_device,
            current_device_hash,
        )

        # Clear invalid cookies
        response.delete_cookie("access_token", path="/", samesite="lax", secure=is_https(request))
        response.delete_cookie(
            "refresh_token",
            path="/api/auth",
            samesite="strict",
            secure=is_https(request),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg or "Invalid refresh token",
        )

    # Get user from database/cache
    user = await user_cache.get_by_id(user_id)
    if not user:
        logger.warning(
            "[TokenAudit] Refresh failed - user not found: user=%s, ip=%s",
            user_id,
            client_ip,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Create new access token
    new_access_token = create_access_token(user)

    # Rotate refresh token (revoke old, create new)
    new_refresh_token, new_refresh_hash = create_refresh_token(user_id)
    user_agent = request.headers.get("User-Agent", "")

    await refresh_manager.rotate_refresh_token(
        user_id=user_id,
        old_token_hash=old_token_hash,
        new_token_hash=new_refresh_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=current_device_hash,
    )

    # Remove old access token session before storing new one
    # This prevents session accumulation on token refresh
    session_manager = get_session_manager()
    old_access_token = request.cookies.get("access_token")
    if old_access_token:
        await session_manager.delete_session(user_id, token=old_access_token)

    # Store new session with device hash for same-device session tracking
    await session_manager.store_session(user_id, new_access_token, device_hash=current_device_hash)

    await _record_vpn_refresh_last_ip(user_id, request)

    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token, request)

    logger.info("[TokenAudit] Token refreshed: user=%s, ip=%s", user_id, client_ip)

    return {
        **auth_session_json_metadata(),
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get current authenticated user profile
    """
    try:
        # Get organization (use cache with database fallback)
        org = None
        try:
            if current_user.organization_id:
                org = await org_cache.get_by_id(current_user.organization_id)
        except BACKGROUND_INFRA_ERRORS as org_error:
            logger.warning("Error getting organization from cache: %s", org_error, exc_info=True)
            # Continue without org - not critical

        # Determine user role
        try:
            role = get_user_role(current_user)
        except BACKGROUND_INFRA_ERRORS as role_error:
            logger.error("Error determining user role: %s", role_error, exc_info=True)
            role = "teacher"  # Default fallback

        thinking_coins = {"balance": 0, "eligible": False}
        if feature_thinking_coins_enabled():
            if user_eligible_for_thinking_coins(current_user, org):
                await ensure_wallet_bootstrap(db, current_user, org)
            wallet_payload = await build_wallet_payload(db, current_user, org)
            thinking_coins = {
                "balance": wallet_payload.get("balance", 0),
                "eligible": wallet_payload.get("eligible", False),
            }

        return {
            "id": current_user.id,
            "phone": current_user.phone,
            "email": getattr(current_user, "email", None),
            "name": current_user.name,
            "avatar": current_user.avatar or DEFAULT_USER_AVATAR_EMOJI,
            "role": role,
            "login_password_set": getattr(current_user, "login_password_set", True),
            "organization": organization_session_payload(org),
            "thinking_coins": thinking_coins,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "last_login": (current_user.last_login.isoformat() if current_user.last_login else None),
            "ui_language": getattr(current_user, "ui_language", None),
            "prompt_language": getattr(current_user, "prompt_language", None),
            "ui_version": getattr(current_user, "ui_version", None),
            "match_prompt_to_ui": getattr(current_user, "match_prompt_to_ui", True),
            "allows_simplified_chinese": getattr(current_user, "allows_simplified_chinese", True),
        }
    except BACKGROUND_INFRA_ERRORS as me_error:
        logger.error("Error in /me endpoint: %s", me_error, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile",
        ) from me_error


@router.patch("/profile")
async def patch_profile(
    body: UpdateProfileNameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Update the current user's display name (self-service).
    """
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", lang),
        )
    user.name = body.name
    try:
        await db.commit()
    except REDIS_ERRORS as exc:
        await db.rollback()
        logger.error("[Auth] profile patch commit failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("profile_update_failed", lang),
        ) from exc

    try:
        await user_cache.invalidate(
            int(user.id), phone=str(user.phone) if user.phone else None, email=str(user.email) if user.email else None
        )
    except REDIS_ERRORS as inv_exc:
        logger.warning("[Auth] user cache invalidation after profile: %s", inv_exc)
    return {"ok": True, "name": user.name}


@router.get("/session-status")
async def get_session_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language"),
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
        current_user.id,
        client_ip,
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
                current_user.id,
            )
            return {
                "status": "invalidated",
                "message": "Session invalidated",
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        # Session is already validated by get_current_user dependency
        # Only check for invalidation notifications (e.g., max device limit exceeded)
        session_manager = get_session_manager()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # Check for invalidation notification
        notification = await session_manager.check_invalidation_notification(current_user.id, token_hash)
        if notification:
            # Clear notification after checking
            await session_manager.clear_invalidation_notification(current_user.id, token_hash)
            logger.info(
                "[TokenAudit] Session status: INVALIDATED (max devices): user=%s, notification_ip=%s",
                current_user.id,
                notification.get("ip_address", "unknown"),
            )
            return {
                "status": "invalidated",
                "message": "Session ended: maximum device limit exceeded",
                "timestamp": notification.get("timestamp", datetime.now(tz=UTC).isoformat()),
                "ip_address": notification.get("ip_address", "unknown"),
            }

        # Session is valid (already validated by get_current_user)
        # No need to call is_session_valid again - it's redundant
        logger.debug(
            "[TokenAudit] Session status: ACTIVE: user=%s, token=%s...",
            current_user.id,
            token_hash[:8],
        )
        return {"status": "active"}
    except BACKGROUND_INFRA_ERRORS as status_error:
        logger.error("Error checking session status: %s", status_error, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session status unavailable",
        ) from status_error


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """
    Logout user - revokes both access token session and refresh token.

    Security:
    - Deletes access token session from Redis
    - Revokes refresh token (prevents future token refresh)
    - Clears both httpOnly cookies
    """
    client_ip = get_client_ip(request)
    logger.info("[TokenAudit] /logout called: user=%s, ip=%s", current_user.id, client_ip)

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
        token_hint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:8] if token else "none"
        logger.info(
            "[TokenAudit] Logout deleting session: user=%s, token=%s...",
            current_user.id,
            token_hint,
        )
        await session_manager.delete_session(current_user.id, token=token)
    except BACKGROUND_INFRA_ERRORS as delete_error:
        logger.info(
            "[TokenAudit] Logout session delete failed: user=%s, error=%s",
            current_user.id,
            delete_error,
        )

    # Revoke refresh token
    try:
        refresh_token_value = request.cookies.get("refresh_token")
        if refresh_token_value:
            refresh_token_hash = hash_refresh_token(refresh_token_value)
            logger.info(
                "[TokenAudit] Logout revoking refresh token: user=%s, token=%s...",
                current_user.id,
                refresh_token_hash[:8],
            )
            refresh_manager = get_refresh_token_manager()
            await refresh_manager.revoke_refresh_token(
                user_id=current_user.id, token_hash=refresh_token_hash, reason="logout"
            )
        else:
            logger.info(
                "[TokenAudit] Logout: no refresh token cookie to revoke: user=%s",
                current_user.id,
            )
    except BACKGROUND_INFRA_ERRORS as revoke_error:
        logger.info(
            "[TokenAudit] Logout refresh token revoke failed: user=%s, error=%s",
            current_user.id,
            revoke_error,
        )

    # Clear access token cookie
    response.delete_cookie(key="access_token", path="/", samesite="lax", secure=is_https(request))

    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        samesite="strict",
        secure=is_https(request),
    )

    # Clear the double-submit CSRF cookie so no stale token lingers post-logout
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        samesite="strict",
        secure=is_https(request),
    )

    # End user sessions in activity tracker
    try:
        tracker = get_activity_tracker()
        await tracker.end_session(user_id=current_user.id)
    except BACKGROUND_INFRA_ERRORS as tracker_error:
        logger.debug("Failed to end user session on logout: %s", tracker_error)

    logger.info(
        "[TokenAudit] Logout: user=%s, phone=%s, ip=%s",
        current_user.id,
        current_user.phone,
        client_ip,
    )

    return {"message": Messages.success("logged_out", lang)}
