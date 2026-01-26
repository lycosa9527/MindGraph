"""
Password Reset Endpoint
========================

Password reset endpoint:
- /reset_password - Reset password with SMS verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import ChangePasswordRequest, ResetPasswordWithSMSRequest
from services.redis.session import get_refresh_token_manager, get_session_manager
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import hash_password, get_client_ip, get_current_user, verify_password

from .dependencies import get_language_dependency
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reset-password")
async def reset_password_with_sms(
    request: ResetPasswordWithSMSRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Reset password with SMS verification

    Allows users to reset their password using SMS verification.
    Also unlocks the account if it was locked.
    """
    # Find user (use cache with database fallback)
    cached_user = user_cache.get_by_phone(request.phone)

    if not cached_user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )

    # Verify SMS code
    _verify_and_consume_sms_code(
        request.phone,
        request.sms_code,
        "reset_password",
        db,
        lang
    )

    # Reload user from database for modification (cached users are detached)
    user = db.query(User).filter(User.id == cached_user.id).first()
    if not user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )

    # Update password and unlock account
    # Note: We manually unlock instead of using reset_failed_attempts() because
    # password reset is not a login event, so last_login should not be updated
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Unlock account
    user.locked_until = None

    # Write to database FIRST
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to update password in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        ) from e

    # Invalidate and re-cache user (password changed)
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
        logger.info("[Auth] Password reset and cache updated for user ID %s", user.id)
    except Exception as e:
        logger.warning("[Auth] Failed to update cache after password reset: %s", e)

    # Revoke all refresh tokens (security: password changed)
    try:
        refresh_manager = get_refresh_token_manager()
        revoked_count = refresh_manager.revoke_all_refresh_tokens(
            user_id=user.id,
            reason="password_reset"
        )
        if revoked_count > 0:
            logger.info("[TokenAudit] Password reset: revoked %s refresh tokens for user %s", revoked_count, user.id)
    except Exception as e:
        logger.warning("[Auth] Failed to revoke refresh tokens after password reset: %s", e)

    # Invalidate all access token sessions
    try:
        session_manager = get_session_manager()
        session_manager.invalidate_user_sessions(user.id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate sessions after password reset: %s", e)

    # Get client IP address
    client_ip = get_client_ip(http_request) if http_request else "unknown"

    logger.info("[TokenAudit] Password reset: user=%s, phone=%s, method=sms, ip=%s", user.id, user.phone, client_ip)

    return {
        "message": Messages.success("password_reset_success", lang),
        "phone": user.phone[:3] + "****" + user.phone[-4:]
    }


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Change password (for authenticated users)

    Allows authenticated users to change their password.
    Requires current password verification.
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.password_hash):
        error_msg = Messages.error("invalid_password_change", lang)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg
        )

    # Check if new password is different
    if verify_password(request.new_password, current_user.password_hash):
        error_msg = Messages.error("password_same_as_current", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Reload user from database for modification
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Clear any failed attempts
    user.locked_until = None

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Failed to change password for user %s: %s", user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        ) from e

    # Invalidate and re-cache user
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
        logger.info("Password changed for user ID %s", user.id)
    except Exception as e:
        logger.warning("Failed to update cache after password change: %s", e)

    # Revoke all refresh tokens (security: password changed)
    try:
        refresh_manager = get_refresh_token_manager()
        revoked_count = refresh_manager.revoke_all_refresh_tokens(
            user_id=user.id,
            reason="password_change"
        )
        if revoked_count > 0:
            logger.info("[TokenAudit] Password change: revoked %s refresh tokens for user %s", revoked_count, user.id)
    except Exception as e:
        logger.warning("Failed to revoke refresh tokens after password change: %s", e)

    # Invalidate all access token sessions (except current one will need re-auth)
    try:
        session_manager = get_session_manager()
        session_manager.invalidate_user_sessions(user.id)
    except Exception as e:
        logger.warning("Failed to invalidate sessions after password change: %s", e)

    logger.info("[TokenAudit] Password changed: user=%s, phone=%s", user.id, user.phone)

    return {
        "message": Messages.success("password_change_success", lang)
    }
