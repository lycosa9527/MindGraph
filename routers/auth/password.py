"""
Password Reset Endpoint
========================

Password reset endpoints:
- /reset-password - Reset password with SMS verification
- /reset-password-email - Reset password with email verification code

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import (
    ChangePasswordRequest,
    ResetPasswordWithEmailRequest,
    ResetPasswordWithSMSRequest,
)
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import email_cn_geo_blocked
from services.auth.password_security import (
    invalidate_user_cache_after_password_write,
    revoke_refresh_tokens_and_sessions,
)
from services.redis.cache.redis_user_cache import user_cache
from utils.email_validation import validate_email_for_api
from utils.auth import (
    AUTH_MODE,
    EMAIL_LOGIN_CN_BLOCK_ENABLED,
    hash_password,
    get_client_ip,
    get_current_user,
    verify_password,
)
from services.redis.redis_email_storage import normalize_verification_email

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .email import verify_and_consume_email_code
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


def _geo_guard_reset_password_email(
    http_request: Request,
    lang: Language,
) -> JSONResponse | None:
    """
    Enforce mainland/VPN geo policy for email-based password reset.

    Returns a 403 JSONResponse when the client must be blocked with optional CN
    cookie stamping; None when the request may proceed. Raises HTTPException
    for non-CN service-unavailable style blocks.
    """
    if not EMAIL_LOGIN_CN_BLOCK_ENABLED or AUTH_MODE in ("demo", "bayi"):
        return None
    must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
        get_client_ip(http_request),
        http_request,
        whitelisted_from_cn=False,
    )
    if not must_deny:
        return None
    detail = Messages.error(geo_msg_key, lang=lang)
    if geo_msg_key == "email_login_blocked_in_mainland_china":
        return json_forbidden_cn_geo(detail, http_request, stamp_cn)
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def _raise_for_captcha_failure(captcha_error: Optional[str], lang: Language) -> None:
    """Map captcha verification failure to HTTPException (shared pattern with phone routes)."""
    if captcha_error == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("captcha_expired", lang),
        )
    if captcha_error == "not_found":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("captcha_not_found", lang),
        )
    if captcha_error == "incorrect":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("captcha_incorrect", lang),
        )
    if captcha_error == "database_locked":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("captcha_database_unavailable", lang),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Messages.error("captcha_verify_failed", lang),
    )


@router.post("/reset-password")
async def reset_password_with_sms(
    request: ResetPasswordWithSMSRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Reset password with SMS verification

    Allows users to reset their password using SMS verification.
    Also unlocks the account if it was locked.
    """
    # Find user (use cache with database fallback)
    cached_user = await user_cache.get_by_phone(request.phone)

    if not cached_user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Verify SMS code
    await _verify_and_consume_sms_code(request.phone, request.sms_code, "reset_password", db, lang)

    # Reload user from database for modification (cached users are detached)
    result = await db.execute(select(User).where(User.id == cached_user.id))
    user = result.scalar_one_or_none()
    if not user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Update password and unlock account
    # Note: We manually unlock instead of using reset_failed_attempts() because
    # password reset is not a login event, so last_login should not be updated
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Unlock account
    user.locked_until = None

    # Write to database FIRST
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to update password in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        ) from e

    await invalidate_user_cache_after_password_write(user, "Password reset")
    await revoke_refresh_tokens_and_sessions(user.id, "password_reset")

    # Get client IP address
    client_ip = get_client_ip(http_request) if http_request else "unknown"

    logger.info(
        "[TokenAudit] Password reset: user=%s, phone=%s, method=sms, ip=%s",
        user.id,
        user.phone,
        client_ip,
    )

    return {
        "message": Messages.success("password_reset_success", lang),
        "phone": user.phone[:3] + "****" + user.phone[-4:],
    }


@router.post("/reset-password-email")
async def reset_password_with_email(
    request: ResetPasswordWithEmailRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Reset password using email verification code (for accounts registered with email only).
    """
    email_validated = validate_email_for_api(request.email, lang)
    email_norm = normalize_verification_email(email_validated)

    cached_user = await user_cache.get_by_email(email_norm)
    if not cached_user:
        error_msg = Messages.error("email_not_registered_reset", lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    blocked = _geo_guard_reset_password_email(http_request, lang)
    if blocked is not None:
        return blocked

    await verify_and_consume_email_code(request.email, request.email_code, "reset_password", lang)

    result = await db.execute(select(User).where(User.id == cached_user.id))
    user = result.scalar_one_or_none()
    if not user:
        error_msg = Messages.error("email_not_registered_reset", lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("[Auth] Failed to update password (email reset) in database: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        ) from exc

    await invalidate_user_cache_after_password_write(user, "Password reset (email)")
    await revoke_refresh_tokens_and_sessions(user.id, "password_reset")

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    logger.info(
        "[TokenAudit] Password reset: user=%s, email=%s, method=email, ip=%s",
        user.id,
        email_norm[:3] + "***",
        client_ip,
    )

    return {"message": Messages.success("password_reset_success", lang)}


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Change password (for authenticated users)

    Allows authenticated users to change their password.
    Requires captcha and current password verification.
    """
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        _raise_for_captcha_failure(captcha_error, lang)

    # Verify current password
    if not verify_password(request.current_password, current_user.password_hash):
        error_msg = Messages.error("invalid_password_change", lang)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    # Check if new password is different
    if verify_password(request.new_password, current_user.password_hash):
        error_msg = Messages.error("password_same_as_current", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Reload user from database for modification
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Clear any failed attempts
    user.locked_until = None

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Failed to change password for user %s: %s", user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password",
        ) from e

    await invalidate_user_cache_after_password_write(user, "Password changed")
    await revoke_refresh_tokens_and_sessions(user.id, "password_change")

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    logger.info(
        "[TokenAudit] Password changed: user=%s, phone=%s, ip=%s",
        user.id,
        user.phone,
        client_ip,
    )

    return {"message": Messages.success("password_change_success", lang)}
