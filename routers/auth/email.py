"""
Email verification endpoints (Tencent SES delivers; product language: email verification code).

- /email/send — Send 6-digit code (purposes: register, reset_password, login)
- /email/verify — Verify code without consuming (peek match)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import SendEmailCodeRequest, VerifyEmailCodeRequest
from services.auth.email_middleware import SESServiceError, get_email_middleware
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import (
    email_cn_geo_blocked,
    overseas_email_registration_allowed,
)
from services.auth.swot_academic import require_academic_email_if_configured
from services.auth.ses_service import (
    EMAIL_CODE_EXPIRY_MINUTES,
    EMAIL_MAX_ATTEMPTS_PER_ADDRESS,
    EMAIL_MAX_ATTEMPTS_WINDOW_HOURS,
    EMAIL_RESEND_INTERVAL_SECONDS,
)
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from services.redis.cache.redis_user_cache import user_cache
from services.redis.redis_email_storage import (
    get_email_storage,
    mask_email_for_log,
    normalize_verification_email,
)
from config.settings import config
from utils.auth import AUTH_MODE, EMAIL_LOGIN_CN_BLOCK_ENABLED, get_client_ip
from utils.email_mainland_china import (
    raise_if_mainland_china_email_for_email_login,
    raise_if_mainland_china_email_for_overseas_registration,
)
from utils.email_validation import validate_email_code_digits, validate_email_for_api

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/email/send")
async def send_email_code(
    request: SendEmailCodeRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Send email verification code via Tencent SES (template).

    Security: captcha required. Rate limits mirror SMS (cooldown + hourly cap).
    For purpose=register: GeoIP must not be mainland China (CN); email must not exist.
    """
    if request.purpose == "register" and AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        if captcha_error == "expired":
            error_msg = Messages.error("captcha_expired", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if captcha_error == "not_found":
            error_msg = Messages.error("captcha_not_found", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if captcha_error == "incorrect":
            error_msg = Messages.error("captcha_incorrect", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_msg)
        error_msg = Messages.error("captcha_verify_failed", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    client_ip = get_client_ip(http_request)

    if request.purpose == "register":
        geo_allowed, geo_err, stamp_cn = overseas_email_registration_allowed(
            client_ip,
            request=http_request,
        )
        if not geo_allowed:
            detail = Messages.error(geo_err, lang)
            if geo_err == "registration_email_not_available_in_region":
                return json_forbidden_cn_geo(detail, http_request, stamp_cn)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    if request.purpose == "reset_password" and EMAIL_LOGIN_CN_BLOCK_ENABLED and AUTH_MODE not in ("demo", "bayi"):
        must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
            client_ip,
            http_request,
            whitelisted_from_cn=False,
        )
        if must_deny:
            detail = Messages.error(geo_msg_key, lang=lang)
            if geo_msg_key == "email_login_blocked_in_mainland_china":
                return json_forbidden_cn_geo(detail, http_request, stamp_cn)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    email_middleware = get_email_middleware()
    if not email_middleware.is_available:
        error_msg = Messages.error("email_service_not_configured", lang)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_msg)

    email_validated = validate_email_for_api(request.email, lang)
    if request.purpose == "register":
        raise_if_mainland_china_email_for_overseas_registration(email_validated, lang)
    elif request.purpose == "login":
        raise_if_mainland_china_email_for_email_login(email_validated, lang)
    require_academic_email_if_configured(email_validated, request.purpose, lang)
    email_norm = normalize_verification_email(email_validated)
    purpose = request.purpose

    if purpose == "register":
        result = await db.execute(select(User).where(User.email == email_norm))
        if result.scalar_one_or_none():
            error_msg = Messages.error("email_already_registered", lang)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

    if purpose == "reset_password":
        existing_user = await user_cache.get_by_email(email_norm)
        if not existing_user:
            error_msg = Messages.error("email_not_registered_reset", lang)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    if purpose == "login":
        cached_user = await user_cache.get_by_email(email_norm)
        if not cached_user:
            error_msg = Messages.error("email_not_registered_login", lang)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        if EMAIL_LOGIN_CN_BLOCK_ENABLED and AUTH_MODE not in ("demo", "bayi"):
            whitelisted = getattr(cached_user, "email_login_whitelisted_from_cn", False)
            must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
                client_ip,
                http_request,
                whitelisted_from_cn=whitelisted,
            )
            if must_deny:
                detail = Messages.error(geo_msg_key, lang=lang)
                if geo_msg_key == "email_login_blocked_in_mainland_china":
                    return json_forbidden_cn_geo(detail, http_request, stamp_cn)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=detail,
                )

    email_storage = get_email_storage()
    rate_limiter = get_rate_limiter()

    send_window_seconds = config.EMAIL_SEND_WINDOW_MINUTES * 60
    allowed_ip_send, _ip_send_count, _ = rate_limiter.check_and_record(
        "email_send_ip",
        client_ip,
        config.EMAIL_SEND_MAX_ATTEMPTS_PER_IP,
        send_window_seconds,
    )
    if not allowed_ip_send:
        error_msg = Messages.error("too_many_email_send_attempts_ip", lang, config.EMAIL_SEND_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    exists, remaining_ttl = email_storage.check_exists_and_get_ttl(email_validated, purpose)

    if exists and remaining_ttl > 0:
        total_ttl = EMAIL_CODE_EXPIRY_MINUTES * 60
        code_age = total_ttl - remaining_ttl
        if code_age < EMAIL_RESEND_INTERVAL_SECONDS:
            wait_seconds = EMAIL_RESEND_INTERVAL_SECONDS - code_age
            if wait_seconds >= 60:
                wait_minutes = (wait_seconds // 60) + 1
                error_msg = Messages.error("email_cooldown_minutes", lang, wait_minutes)
            else:
                error_msg = Messages.error("email_cooldown_seconds", lang, wait_seconds)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    allowed, window_count, _ = rate_limiter.check_and_record(
        "email",
        email_norm,
        EMAIL_MAX_ATTEMPTS_PER_ADDRESS,
        EMAIL_MAX_ATTEMPTS_WINDOW_HOURS * 3600,
    )

    if not allowed:
        error_msg = Messages.error(
            "too_many_email_requests",
            lang,
            window_count,
            EMAIL_MAX_ATTEMPTS_WINDOW_HOURS,
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    code = email_middleware.generate_code()
    ttl_seconds = EMAIL_CODE_EXPIRY_MINUTES * 60

    if not email_storage.store(email_validated, code, purpose, ttl_seconds):
        logger.error("Failed to store email code in Redis for %s", mask_email_for_log(email_validated))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("email_service_temporarily_unavailable", lang),
        )

    try:
        success, message, _ = await email_middleware.send_verification_code(
            email_validated,
            purpose,
            code=code,
            lang=lang,
        )
    except SESServiceError as exc:
        email_storage.remove(email_validated, purpose)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not success:
        email_storage.remove(email_validated, purpose)
        if message and message != "SES service not available":
            error_detail = message
        else:
            error_detail = Messages.error("email_service_temporarily_unavailable", lang)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail)

    logger.info("Email code sent to %s for %s", mask_email_for_log(email_validated), purpose)

    return {
        "message": Messages.success("verification_email_sent", lang),
        "expires_in": EMAIL_CODE_EXPIRY_MINUTES * 60,
        "resend_after": EMAIL_RESEND_INTERVAL_SECONDS,
    }


@router.post("/email/verify")
async def verify_email_code(
    request: VerifyEmailCodeRequest,
    http_request: Request,
    _db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Verify email code without consuming (peek). Rate-limited per email+purpose and per IP."""
    email_validated = validate_email_for_api(request.email, lang)
    if request.purpose == "login":
        raise_if_mainland_china_email_for_email_login(email_validated, lang)
    require_academic_email_if_configured(email_validated, request.purpose, lang)
    code_validated = validate_email_code_digits(request.code, lang)

    email_norm = normalize_verification_email(email_validated)

    if request.purpose in ("login", "reset_password") and EMAIL_LOGIN_CN_BLOCK_ENABLED and AUTH_MODE not in (
        "demo",
        "bayi",
    ):
        client_ip_geo = get_client_ip(http_request) if http_request else "unknown"
        if request.purpose == "login":
            cached_verify = await user_cache.get_by_email(email_norm)
            whitelisted = (
                getattr(cached_verify, "email_login_whitelisted_from_cn", False) if cached_verify else False
            )
        else:
            whitelisted = False
        must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
            client_ip_geo,
            http_request,
            whitelisted_from_cn=whitelisted,
        )
        if must_deny:
            detail = Messages.error(geo_msg_key, lang=lang)
            if geo_msg_key == "email_login_blocked_in_mainland_china":
                return json_forbidden_cn_geo(detail, http_request, stamp_cn)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    window_seconds = config.EMAIL_VERIFY_WINDOW_MINUTES * 60
    combo_id = f"{email_norm}:{request.purpose}"
    rate_limiter = get_rate_limiter()

    allowed_combo, _combo_count, _ = rate_limiter.check_and_record(
        "email_verify_combo",
        combo_id,
        config.EMAIL_VERIFY_MAX_ATTEMPTS_PER_COMBO,
        window_seconds,
    )
    if not allowed_combo:
        error_msg = Messages.error("too_many_email_verify_attempts", lang, config.EMAIL_VERIFY_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    allowed_ip, _ip_count, _ = rate_limiter.check_and_record(
        "email_verify_ip",
        client_ip,
        config.EMAIL_VERIFY_MAX_ATTEMPTS_PER_IP,
        window_seconds,
    )
    if not allowed_ip:
        error_msg = Messages.error("too_many_email_verify_attempts", lang, config.EMAIL_VERIFY_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    email_storage = get_email_storage()
    stored_code = email_storage.peek(email_validated, request.purpose)

    if stored_code is None:
        error_msg = Messages.error("email_code_invalid", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    if stored_code != code_validated:
        error_msg = Messages.error("email_code_invalid", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    logger.info("Email code verified (peek): %s", request.purpose)

    return {"valid": True, "message": Messages.success("verification_code_valid", lang)}


def verify_and_consume_email_code(email: str, code: str, purpose: str, lang: Language = "en") -> bool:
    """
    Verify and consume email code (atomic). For use by future registration flows.

    Returns True if valid; raises HTTPException otherwise.

    HTTP routes that call this must apply their own guardrails: captcha and/or
    rate limits on the route, and consume the code once at the end of the flow
    (same pattern as register_with_sms + _verify_and_consume_sms_code).
    """
    email_validated = validate_email_for_api(email, lang)
    if purpose == "login":
        raise_if_mainland_china_email_for_email_login(email_validated, lang)
    require_academic_email_if_configured(email_validated, purpose, lang)
    validate_email_code_digits(code, lang)
    email_storage = get_email_storage()
    if email_storage.verify_and_remove(email_validated, code, purpose):
        return True
    error_msg = Messages.error("email_code_invalid", lang)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
