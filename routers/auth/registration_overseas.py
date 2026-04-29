"""
Overseas education email registration (GeoIP not CN, no invitation).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import RegisterOverseasRequest
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import overseas_email_registration_allowed
from services.auth.vpn_geo_enforcement import record_vpn_login_geo
from services.auth.swot_academic import require_academic_email_if_configured
from services.monitoring.registration_metrics import registration_metrics
from services.redis.cache.redis_user_cache import user_cache
from services.redis.session.redis_session_manager import (
    get_session_manager,
    get_refresh_token_manager,
)
from services.redis.redis_email_storage import normalize_verification_email
from utils.auth import (
    AUTH_MODE,
    ACCESS_TOKEN_EXPIRY_MINUTES,
    compute_device_hash,
    create_access_token,
    create_refresh_token,
    get_client_ip,
    hash_password,
)
from utils.email_mainland_china import raise_if_mainland_china_email_for_overseas_registration
from utils.email_validation import validate_email_for_api

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .email import verify_and_consume_email_code
from .helpers import commit_user_with_retry, set_auth_cookies, track_user_activity

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register-overseas")
async def register_overseas(
    request: RegisterOverseasRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Register with education email for users outside mainland China (GeoIP not CN).
    No invitation code; organization_id is NULL; Simplified Chinese UI is disabled.
    """
    if AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    if not request.outside_mainland_acknowledged:
        error_msg = Messages.error("register_overseas_acknowledgment_required", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    registration_metrics.record_attempt()
    start_time = time.time()
    retry_count = 0
    cache_write_success = False

    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        duration = time.time() - start_time
        registration_metrics.record_failure("captcha_failed", duration)
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

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    allowed, geo_err, stamp_cn = overseas_email_registration_allowed(
        client_ip,
        request=http_request,
    )
    if not allowed:
        duration = time.time() - start_time
        registration_metrics.record_failure("geoip_blocked", duration)
        detail = Messages.error(geo_err, lang)
        if geo_err == "registration_email_not_available_in_region":
            return json_forbidden_cn_geo(detail, http_request, stamp_cn)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    email_validated = validate_email_for_api(request.email, lang)
    raise_if_mainland_china_email_for_overseas_registration(email_validated, lang)
    require_academic_email_if_configured(email_validated, "register", lang)
    email_norm = normalize_verification_email(email_validated)

    result = await db.execute(select(User).where(User.email == email_norm))
    if result.scalar_one_or_none():
        duration = time.time() - start_time
        registration_metrics.record_failure("email_exists", duration)
        error_msg = Messages.error("email_already_registered", lang)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

    await verify_and_consume_email_code(request.email, request.email_code, "register", lang)

    new_user = User(
        phone=None,
        email=email_norm,
        password_hash=hash_password(request.password),
        name=request.name,
        organization_id=None,
        created_at=datetime.now(UTC),
        allows_simplified_chinese=False,
        email_login_whitelisted_from_cn=False,
        ui_language="en",
    )

    db.add(new_user)
    retry_count = await commit_user_with_retry(db, new_user, max_retries=5, lang=lang)

    session_manager = get_session_manager()
    token = create_access_token(new_user)
    refresh_token_value, refresh_token_hash = create_refresh_token(new_user.id)
    device_hash = compute_device_hash(http_request)
    user_agent = http_request.headers.get("User-Agent", "")

    async def cache_user_async() -> None:
        nonlocal cache_write_success
        try:
            await user_cache.cache_user(new_user)
            cache_write_success = True
            logger.info("[Auth] Overseas user registered: ID %s email=%s", new_user.id, email_norm[:3] + "***")
        except Exception as exc:
            cache_write_success = False
            logger.warning("[Auth] Failed to cache overseas user ID %s: %s", new_user.id, exc)

    async def store_session_async() -> None:
        try:
            await session_manager.store_session(new_user.id, token, device_hash=device_hash)
        except Exception as exc:
            logger.warning("[Auth] Failed to store session for user ID %s: %s", new_user.id, exc)

    async def store_refresh_token_async() -> None:
        try:
            refresh_manager = get_refresh_token_manager()
            await refresh_manager.store_refresh_token(
                user_id=new_user.id,
                token_hash=refresh_token_hash,
                ip_address=client_ip,
                user_agent=user_agent,
                device_hash=device_hash,
            )
        except Exception as exc:
            logger.warning(
                "[Auth] Failed to store refresh token for user ID %s: %s",
                new_user.id,
                exc,
            )

    await asyncio.gather(
        cache_user_async(),
        store_session_async(),
        store_refresh_token_async(),
        return_exceptions=True,
    )

    duration = time.time() - start_time
    registration_metrics.record_success(duration, retry_count, cache_write_success)

    set_auth_cookies(response, token, refresh_token_value, http_request)

    await record_vpn_login_geo(new_user.id, http_request)

    logger.info(
        "[TokenAudit] Registration success (overseas email): user=%s ip=%s",
        new_user.id,
        client_ip,
    )

    await track_user_activity(
        new_user,
        "login",
        {"method": "register_overseas", "org": None, "action": "register"},
        http_request,
        db,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "email": new_user.email,
            "name": new_user.name,
            "organization": None,
            "allows_simplified_chinese": False,
            "ui_language": new_user.ui_language,
            "prompt_language": getattr(new_user, "prompt_language", None),
            "match_prompt_to_ui": getattr(new_user, "match_prompt_to_ui", True),
        },
    }
