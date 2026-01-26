"""
Phone Number Change Endpoints
=============================

Phone number change endpoints with SMS verification:
- /phone/send-code - Send SMS verification code to new phone number
- /phone/change - Complete phone number change with SMS verification

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
from models.requests.requests_auth import SendChangePhoneSMSRequest, ChangePhoneRequest
from services.redis.redis_sms_storage import get_sms_storage
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from services.redis.cache.redis_user_cache import user_cache
from services.auth.sms_middleware import (
    get_sms_middleware,
    SMSServiceError,
    SMS_CODE_EXPIRY_MINUTES,
    SMS_RESEND_INTERVAL_SECONDS,
    SMS_MAX_ATTEMPTS_PER_PHONE,
    SMS_MAX_ATTEMPTS_WINDOW_HOURS
)
from utils.auth import get_current_user

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .helpers import commit_user_with_retry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/phone/send-code")
async def send_change_phone_code(
    request: SendChangePhoneSMSRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Send SMS verification code to new phone number for phone change

    Requires authentication. Sends a 6-digit verification code to the new phone number.

    Security:
    - Requires valid authentication
    - Captcha verification required (bot protection)

    Rate limiting:
    - 60 seconds cooldown between requests for same phone/purpose
    - Maximum 5 codes per hour per phone number
    """
    new_phone = request.new_phone

    # Check if new phone is same as current phone
    if new_phone == current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("phone_same_as_current", lang)
        )

    # Check if new phone is already registered by another user
    existing_user = user_cache.get_by_phone(new_phone)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("phone_already_in_use", lang)
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

    purpose = "change_phone"

    # Get Redis SMS storage and rate limiter
    sms_storage = get_sms_storage()
    rate_limiter = get_rate_limiter()

    # Check rate limiting: cooldown between requests (via Redis TTL)
    exists, remaining_ttl = sms_storage.check_exists_and_get_ttl(new_phone, purpose)

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
    allowed, window_count, error_message = rate_limiter.check_and_record(
        "sms", new_phone, SMS_MAX_ATTEMPTS_PER_PHONE, SMS_MAX_ATTEMPTS_WINDOW_HOURS * 3600
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

    if not sms_storage.store(new_phone, code, purpose, ttl_seconds):
        phone_masked = new_phone[:3] + "****" + new_phone[-4:]
        logger.error("Failed to store SMS code in Redis for %s", phone_masked)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("sms_service_temporarily_unavailable", lang)
        )

    # Now send the SMS with pre-generated code
    try:
        success, message, _ = await sms_middleware.send_verification_code(new_phone, purpose, code=code, lang=lang)
    except SMSServiceError as e:
        # SMS middleware error - remove the Redis record since SMS won't be sent
        sms_storage.remove(new_phone, purpose)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

    if not success:
        # SMS sending failed - remove the Redis record
        sms_storage.remove(new_phone, purpose)
        if message and message != "SMS service not available":
            error_detail = message
        else:
            error_detail = Messages.error("sms_service_temporarily_unavailable", lang)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

    phone_masked = new_phone[:3] + "****" + new_phone[-4:]
    logger.info("SMS code sent to %s for phone change (user: %s)", phone_masked, current_user.id)

    return {
        "message": Messages.success("verification_code_sent", lang),
        "expires_in": SMS_CODE_EXPIRY_MINUTES * 60,  # in seconds
        "resend_after": SMS_RESEND_INTERVAL_SECONDS  # in seconds
    }


@router.post("/phone/change")
async def change_phone(
    request: ChangePhoneRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Complete phone number change with SMS verification

    Requires authentication and valid SMS verification code.
    Updates the user's phone number in the database.
    """
    new_phone = request.new_phone
    sms_code = request.sms_code

    # Check if new phone is same as current phone
    if new_phone == current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("phone_same_as_current", lang)
        )

    # Check if new phone is already registered by another user
    existing_user = user_cache.get_by_phone(new_phone)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("phone_already_in_use", lang)
        )

    # Verify and consume SMS code
    sms_storage = get_sms_storage()
    purpose = "change_phone"

    if not sms_storage.verify_and_remove(new_phone, sms_code, purpose):
        error_msg = Messages.error("sms_code_invalid", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Store old phone for logging and cache invalidation
    old_phone = current_user.phone

    # Update phone number in database
    current_user.phone = new_phone

    # Commit with retry for database lock handling
    success = commit_user_with_retry(db, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("database_temporarily_unavailable", lang)
        )

    # Invalidate cache for both old and new phone
    user_cache.invalidate(current_user.id, old_phone)
    user_cache.invalidate(current_user.id, new_phone)

    # Re-cache user with new phone
    user_cache.cache_user(current_user)

    old_phone_masked = old_phone[:3] + "****" + old_phone[-4:]
    new_phone_masked = new_phone[:3] + "****" + new_phone[-4:]
    logger.info("Phone changed for user %s: %s -> %s", current_user.id, old_phone_masked, new_phone_masked)

    return {
        "message": Messages.success("phone_changed_success", lang),
        "phone": new_phone
    }
