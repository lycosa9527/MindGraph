"""
SMS Verification Endpoints
==========================

SMS verification endpoints:
- /sms/send - Send SMS verification code
- /sms/verify - Verify SMS code (standalone)
- _verify_and_consume_sms_code() - Helper function for consuming SMS codes

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.messages import Messages, Language
from models.requests.requests_auth import SendSMSCodeRequest, SendSMSCodeSimpleRequest, VerifySMSCodeRequest
from services.auth.sms_middleware import (
    get_sms_middleware,
    SMSServiceError,
    SMS_CODE_EXPIRY_MINUTES,
    SMS_RESEND_INTERVAL_SECONDS,
    SMS_MAX_ATTEMPTS_PER_PHONE,
    SMS_MAX_ATTEMPTS_WINDOW_HOURS
)
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from services.redis.redis_sms_storage import get_sms_storage
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import AUTH_MODE

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sms/send")
async def send_sms_code(
    request: SendSMSCodeRequest,
    _http_request: Request,
    _db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Send SMS verification code

    Sends a 6-digit verification code via Tencent SMS.

    Security:
    - Captcha verification required (bot protection)

    Purposes:
    - register: For new user registration
    - login: For SMS-based login
    - reset_password: For password recovery

    Rate limiting:
    - 60 seconds cooldown between requests for same phone/purpose
    - Maximum 5 codes per hour per phone number
    """
    # Check authentication mode - registration SMS not allowed in demo/bayi modes
    if request.purpose == "register" and AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )

    # Verify captcha first (anti-bot protection)
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        if captcha_error == "expired":
            error_msg = Messages.error("captcha_expired", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "not_found":
            error_msg = Messages.error("captcha_not_found", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "incorrect":
            error_msg = Messages.error("captcha_incorrect", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("captcha_verify_failed", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

    sms_middleware = get_sms_middleware()

    # Check if SMS service is available
    if not sms_middleware.is_available:
        error_msg = Messages.error("sms_service_not_configured", lang)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )

    phone = request.phone
    purpose = request.purpose

    # For registration, check if phone already exists (use cache)
    if purpose == "register":
        existing_user = user_cache.get_by_phone(phone)
        if existing_user:
            error_msg = Messages.error("phone_already_registered", lang)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )

    # For login and reset_password, check if user exists (use cache)
    if purpose in ["login", "reset_password"]:
        existing_user = user_cache.get_by_phone(phone)
        if not existing_user:
            if purpose == "login":
                error_msg = Messages.error("phone_not_registered_login", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )
            else:  # reset_password
                error_msg = Messages.error("phone_not_registered_reset", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )

    # Get Redis SMS storage and rate limiter
    sms_storage = get_sms_storage()
    rate_limiter = get_rate_limiter()

    # Check rate limiting: cooldown between requests (via Redis TTL)
    exists, remaining_ttl = sms_storage.check_exists_and_get_ttl(phone, purpose)

    if exists and remaining_ttl > 0:
        total_ttl = SMS_CODE_EXPIRY_MINUTES * 60  # 300 seconds for 5 minutes
        code_age = total_ttl - remaining_ttl

        # Only block if code was sent within the cooldown period
        if code_age < SMS_RESEND_INTERVAL_SECONDS:
            wait_seconds = SMS_RESEND_INTERVAL_SECONDS - code_age
            if wait_seconds >= 60:
                wait_minutes = (wait_seconds // 60) + 1
                error_msg = Messages.error("sms_cooldown_minutes", lang, wait_minutes)
            else:
                error_msg = Messages.error("sms_cooldown_seconds", lang, wait_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )

    # Check rate limit within time window using Redis rate limiter
    allowed, window_count, _error_message = rate_limiter.check_and_record(
        "sms", phone, SMS_MAX_ATTEMPTS_PER_PHONE, SMS_MAX_ATTEMPTS_WINDOW_HOURS * 3600
    )

    if not allowed:
        error_msg = Messages.error("too_many_sms_requests", lang, window_count, SMS_MAX_ATTEMPTS_WINDOW_HOURS)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )

    # Generate verification code first
    code = sms_middleware.generate_code()

    # Store verification code in Redis BEFORE sending SMS
    ttl_seconds = SMS_CODE_EXPIRY_MINUTES * 60

    if not sms_storage.store(phone, code, purpose, ttl_seconds):
        phone_masked = phone[:3] + "****" + phone[-4:]
        logger.error("Failed to store SMS code in Redis for %s", phone_masked)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("sms_service_temporarily_unavailable", lang)
        )

    # Now send the SMS with pre-generated code
    try:
        success, message, _ = await sms_middleware.send_verification_code(phone, purpose, code=code, lang=lang)
    except SMSServiceError as e:
        # SMS middleware error - remove the Redis record since SMS won't be sent
        sms_storage.remove(phone, purpose)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        ) from e

    if not success:
        # SMS sending failed - remove the Redis record
        sms_storage.remove(phone, purpose)
        if message and message != "SMS service not available":
            error_detail = message
        else:
            error_detail = Messages.error("sms_service_temporarily_unavailable", lang)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

    phone_masked = phone[:3] + "****" + phone[-4:]
    logger.info("SMS code sent to %s for %s", phone_masked, purpose)

    return {
        "message": Messages.success("verification_code_sent", lang),
        "expires_in": SMS_CODE_EXPIRY_MINUTES * 60,  # in seconds
        "resend_after": SMS_RESEND_INTERVAL_SECONDS  # in seconds
    }


@router.post("/sms/verify")
async def verify_sms_code(
    request: VerifySMSCodeRequest,
    _http_request: Request,
    _db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Verify SMS code (standalone verification)

    Verifies the SMS code without performing any action.
    Useful for frontend validation before form submission.

    Note: This does NOT consume the code - the actual action
    endpoints (register_sms, login_sms, reset_password) will
    consume it.
    """
    phone = request.phone
    code = request.code
    purpose = request.purpose

    # Get SMS storage
    sms_storage = get_sms_storage()

    # Peek at the stored code to verify (without consuming)
    stored_code = sms_storage.peek(phone, purpose)

    if stored_code is None:
        error_msg = Messages.error("sms_code_invalid", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    if stored_code != code:
        error_msg = Messages.error("sms_code_invalid", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    phone_masked = phone[:3] + "****" + phone[-4:]
    logger.info("SMS code verified: %s (Purpose: %s)", phone_masked, purpose)

    return {
        "valid": True,
        "message": Messages.success("verification_code_valid", lang)
    }


def _verify_and_consume_sms_code(
    phone: str,
    code: str,
    purpose: str,
    _db: Session,
    lang: Language = "en"
) -> bool:
    """
    Internal helper to verify and consume SMS code

    Returns True if valid, raises HTTPException if invalid

    Uses Redis Lua script for atomic compare-and-delete to prevent race conditions.
    Only one concurrent request can consume the code successfully.

    Args:
        phone: Phone number
        code: SMS verification code
        purpose: Purpose of verification (register, login, reset_password)
        db: Database session (kept for API compatibility, not used for SMS anymore)
        lang: Language for error messages (default: "en")
    """
    # Get SMS storage
    sms_storage = get_sms_storage()

    # Atomic verify and remove - prevents race conditions
    if sms_storage.verify_and_remove(phone, code, purpose):
        phone_masked = phone[:3] + "****" + phone[-4:]
        logger.info("SMS code consumed: %s (Purpose: %s)", phone_masked, purpose)
        return True

    # Code verification failed
    error_msg = Messages.error("sms_code_invalid", lang)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_msg
    )


async def _send_sms_code_with_purpose(
    request: SendSMSCodeSimpleRequest,
    _http_request: Request,
    purpose: str,
    _db: Session,
    lang: Language
):
    """
    Internal helper to send SMS code with a fixed purpose.

    Reuses the logic from send_sms_code but with purpose pre-set.
    """
    # Check authentication mode - registration SMS not allowed in demo/bayi modes
    if purpose == "register" and AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )

    # Verify captcha first (anti-bot protection)
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        if captcha_error == "expired":
            error_msg = Messages.error("captcha_expired", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "not_found":
            error_msg = Messages.error("captcha_not_found", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "incorrect":
            error_msg = Messages.error("captcha_incorrect", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("captcha_verify_failed", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

    sms_middleware = get_sms_middleware()

    # Check if SMS service is available
    if not sms_middleware.is_available:
        error_msg = Messages.error("sms_service_not_configured", lang)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )

    phone = request.phone

    # For registration, check if phone already exists (use cache)
    if purpose == "register":
        existing_user = user_cache.get_by_phone(phone)
        if existing_user:
            error_msg = Messages.error("phone_already_registered", lang)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )

    # For login and reset_password, check if user exists (use cache)
    if purpose in ["login", "reset_password"]:
        existing_user = user_cache.get_by_phone(phone)
        if not existing_user:
            if purpose == "login":
                error_msg = Messages.error("phone_not_registered_login", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )
            else:  # reset_password
                error_msg = Messages.error("phone_not_registered_reset", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )

    # Get Redis SMS storage and rate limiter
    sms_storage = get_sms_storage()
    rate_limiter = get_rate_limiter()

    # Check rate limiting: cooldown between requests (via Redis TTL)
    exists, remaining_ttl = sms_storage.check_exists_and_get_ttl(phone, purpose)

    if exists and remaining_ttl > 0:
        total_ttl = SMS_CODE_EXPIRY_MINUTES * 60  # 300 seconds for 5 minutes
        code_age = total_ttl - remaining_ttl

        # Only block if code was sent within the cooldown period
        if code_age < SMS_RESEND_INTERVAL_SECONDS:
            wait_seconds = SMS_RESEND_INTERVAL_SECONDS - code_age
            if wait_seconds >= 60:
                wait_minutes = (wait_seconds // 60) + 1
                error_msg = Messages.error("sms_cooldown_minutes", lang, wait_minutes)
            else:
                error_msg = Messages.error("sms_cooldown_seconds", lang, wait_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )

    # Check rate limit within time window using Redis rate limiter
    allowed, window_count, _error_message = rate_limiter.check_and_record(
        "sms", phone, SMS_MAX_ATTEMPTS_PER_PHONE, SMS_MAX_ATTEMPTS_WINDOW_HOURS * 3600
    )

    if not allowed:
        error_msg = Messages.error("too_many_sms_requests", lang, window_count, SMS_MAX_ATTEMPTS_WINDOW_HOURS)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )

    # Generate verification code first
    code = sms_middleware.generate_code()

    # Store verification code in Redis BEFORE sending SMS
    ttl_seconds = SMS_CODE_EXPIRY_MINUTES * 60

    if not sms_storage.store(phone, code, purpose, ttl_seconds):
        phone_masked = phone[:3] + "****" + phone[-4:]
        logger.error("Failed to store SMS code in Redis for %s", phone_masked)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("sms_service_temporarily_unavailable", lang)
        )

    # Now send the SMS with pre-generated code
    try:
        success, message, _ = await sms_middleware.send_verification_code(phone, purpose, code=code, lang=lang)
    except SMSServiceError as e:
        # SMS middleware error - remove the Redis record since SMS won't be sent
        sms_storage.remove(phone, purpose)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        ) from e

    if not success:
        # SMS sending failed - remove the Redis record
        sms_storage.remove(phone, purpose)
        if message and message != "SMS service not available":
            error_detail = message
        else:
            error_detail = Messages.error("sms_service_temporarily_unavailable", lang)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

    phone_masked = phone[:3] + "****" + phone[-4:]
    logger.info("SMS code sent to %s for %s", phone_masked, purpose)

    return {
        "message": Messages.success("verification_code_sent", lang),
        "expires_in": SMS_CODE_EXPIRY_MINUTES * 60,  # in seconds
        "resend_after": SMS_RESEND_INTERVAL_SECONDS  # in seconds
    }


@router.post("/sms/send-login")
async def send_sms_code_for_login(
    request: SendSMSCodeSimpleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Send SMS verification code for login

    Convenience endpoint that sends SMS code with purpose='login'.
    Requires captcha verification.
    """
    return await _send_sms_code_with_purpose(request, http_request, "login", db, lang)


@router.post("/sms/send-reset")
async def send_sms_code_for_reset(
    request: SendSMSCodeSimpleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Send SMS verification code for password reset

    Convenience endpoint that sends SMS code with purpose='reset_password'.
    Requires captcha verification.
    """
    return await _send_sms_code_with_purpose(request, http_request, "reset_password", db, lang)


@router.post("/sms/send-register")
async def send_sms_code_for_register(
    request: SendSMSCodeSimpleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Send SMS verification code for registration

    Convenience endpoint that sends SMS code with purpose='register'.
    Requires captcha verification.
    Not available in demo/bayi modes.
    """
    return await _send_sms_code_with_purpose(request, http_request, "register", db, lang)
