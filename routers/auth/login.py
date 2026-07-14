"""
Login Endpoints
===============

User login endpoints:
- /login - Password-based login with captcha
- /login_sms - SMS-based login
- /bayi/passkey - Bayi 6-digit passkey login (AUTH_MODE=bayi only)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
from datetime import UTC, datetime
from types import CoroutineType

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from models.requests.requests_auth import (
    LoginRequest,
    LoginWithEmailRequest,
    LoginWithSMSRequest,
    PasskeyVerifyRequest,
)
from routers.auth.org_profile import organization_session_payload
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import email_cn_geo_blocked
from services.auth.vpn_geo_enforcement import record_vpn_login_geo
from services.infrastructure.security.abuseipdb_service import (
    schedule_abuseipdb_report_on_lockout,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from services.redis.rate_limiting.redis_rate_limiter import (
    RedisRateLimiter,
    check_ip_rate_limit,
    check_login_rate_limit,
    clear_ip_attempts,
    clear_login_attempts,
    get_login_attempts_remaining,
)
from services.redis.redis_email_storage import normalize_verification_email
from services.redis.session.redis_session_manager import (
    get_refresh_token_manager,
    get_session_manager,
)
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS
from utils.auth import (
    AUTH_MODE,
    EMAIL_LOGIN_CN_BLOCK_ENABLED,
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    RATE_LIMIT_WINDOW_MINUTES,
    check_account_lockout,
    compute_device_hash,
    create_access_token,
    create_refresh_token,
    get_client_ip,
    get_user_role,
    hash_password,
    increment_failed_attempts,
    is_https,
    reset_failed_attempts,
    verify_bayi_passkey,
    verify_password,
    verify_password_timing_dummy,
)
from utils.auth.config import BAYI_DEFAULT_ORG_CODE, BAYI_DEFAULT_ORG_ID, BAYI_PASSKEY
from utils.auth.org_subscription import enforce_org_accessible_or_raise, ensure_org_subscription_current
from utils.db.rls_request import bind_system_bootstrap_rls_dependency
from utils.email_mainland_china import raise_if_mainland_china_email_for_email_login
from utils.email_validation import validate_email_for_api
from utils.user_avatar_defaults import DEFAULT_USER_AVATAR_EMOJI

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .email import verify_and_consume_email_code
from .helpers import auth_session_json_metadata, set_auth_cookies, track_user_activity
from .sms import _verify_and_consume_sms_code

_bg_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro: CoroutineType) -> None:
    """Schedule a coroutine as a tracked background task to prevent silent GC and log exceptions."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _bg_tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            logger.debug("[bg_task] background task raised: %s", t.exception())

    task.add_done_callback(_on_done)


def _generic_login_failed_message(lang: Language, attempts_left: int) -> str:
    """Uniform login failure text (unknown account vs bad password)."""
    return Messages.error("login_failed_phone_not_found", lang, attempts_left)


def _raise_if_session_persistence_failed(
    session_ok: bool,
    refresh_ok: bool,
    lang: Language,
    user_id: int,
    method: str,
) -> None:
    if session_ok and refresh_ok:
        return
    logger.error(
        "[TokenAudit] Session persistence failed: user=%s, method=%s, session=%s, refresh=%s",
        user_id,
        method,
        session_ok,
        refresh_ok,
    )
    error_msg = Messages.error("database_temporarily_unavailable", lang)
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_msg)


def _preload_user_diagrams(user_id: int):
    """
    Fire-and-forget preload of user's diagram list into Redis cache.
    Non-blocking - runs in background after login returns.
    """
    try:

        async def _do_preload():
            try:
                cache = get_diagram_cache()
                await cache.preload_user_diagrams(user_id)
            except REDIS_ERRORS as exc:
                logging.getLogger(__name__).debug("[Login] Diagram preload failed for user %s: %s", user_id, exc)

        try:
            asyncio.get_running_loop()
            _fire_and_forget(_do_preload())
        except RuntimeError:
            pass
    except DATABASE_ERRORS as exc:
        logger.debug("Failed to preload diagrams: %s", exc)


async def _complete_login_after_otp_verified(
    user: User,
    http_request: Request,
    response: Response,
    db: AsyncSession,
    method: str,
    lang: Language,
) -> dict:
    """
    Shared session/cookie issuance after SMS or email OTP has been verified and consumed.
    """
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        await reset_failed_attempts(db_user, db)
        user = db_user

    if db_user and not getattr(db_user, "allows_simplified_chinese", True):
        prefs_changed = False
        if (db_user.ui_language or "").lower() == "zh":
            db_user.ui_language = "en"
            prefs_changed = True
        if (db_user.prompt_language or "").lower() == "zh":
            db_user.prompt_language = "en"
            prefs_changed = True
        if prefs_changed:
            await db.commit()
            await db.refresh(db_user)
            user = db_user
            try:
                await user_cache.cache_user(db_user)
            except REDIS_ERRORS as cache_exc:
                logger.warning("[%s OTP login] failed to refresh user cache: %s", method, cache_exc)

    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"

    # Successful OTP login clears the shared brute-force counters so legitimate
    # users are not locked out by their own verification attempts.
    login_key = (user.email or "") if method == "email_otp" else (user.phone or "")
    if login_key:
        await clear_login_attempts(login_key)
    await clear_ip_attempts(client_ip)

    token = create_access_token(user)

    refresh_token_value, refresh_token_hash = create_refresh_token(user.id)

    device_hash = compute_device_hash(http_request)

    user_agent = http_request.headers.get("User-Agent", "")
    accept_language = http_request.headers.get("Accept-Language", "")
    sec_ch_platform = http_request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = http_request.headers.get("Sec-CH-UA-Mobile", "")
    logger.info(
        "[TokenAudit] Login device fingerprint: user=%s, device_hash=%s, UA=%s..., lang=%s, platform=%s, mobile=%s",
        user.id,
        device_hash,
        user_agent[:50],
        accept_language[:20],
        sec_ch_platform,
        sec_ch_mobile,
    )

    session_ok = await session_manager.store_session(user.id, token, device_hash=device_hash)

    refresh_manager = get_refresh_token_manager()
    refresh_ok = await refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )
    _raise_if_session_persistence_failed(session_ok, refresh_ok, lang, user.id, method)

    set_auth_cookies(response, token, refresh_token_value, http_request)

    await record_vpn_login_geo(user.id, http_request)

    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None
    if not org and user.organization_id:
        result_org = await db.execute(select(Organization).where(Organization.id == user.organization_id))
        org = result_org.scalar_one_or_none()
        if org:
            db.expunge(org)
            await org_cache.cache_org(org)
    if org:
        org = await ensure_org_subscription_current(org) or org
    org_name = org.name if org else "None"

    logger.info(
        "[TokenAudit] Login success: user=%s, phone=%s, org=%s, method=%s, ip=%s, device=%s",
        user.id,
        user.phone,
        org_name,
        method,
        client_ip,
        device_hash,
    )

    await track_user_activity(user, "login", {"method": method, "org": org_name}, http_request, db)

    _preload_user_diagrams(user.id)

    return {
        **auth_session_json_metadata(),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "email": getattr(user, "email", None),
            "name": user.name,
            "organization": organization_session_payload(org),
            "avatar": user.avatar or DEFAULT_USER_AVATAR_EMOJI,
            "role": get_user_role(user),
            "ui_language": getattr(user, "ui_language", None),
            "prompt_language": getattr(user, "prompt_language", None),
            "match_prompt_to_ui": getattr(user, "match_prompt_to_ui", True),
            "allows_simplified_chinese": getattr(user, "allows_simplified_chinese", True),
        },
    }


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    User login with captcha verification

    Security features:
    - Captcha verification (bot protection)
    - Rate limiting: 10 attempts per 15 minutes (per phone)
    - Account lockout: 5 minutes after 10 failed attempts
    - Failed attempt tracking in database
    """
    if request.email:
        email_validated = validate_email_for_api(request.email, lang)
        raise_if_mainland_china_email_for_email_login(email_validated, lang)
        login_key = normalize_verification_email(email_validated)
        user_row = await db.execute(select(User).where(User.email == login_key))
        cached_user = user_row.scalar_one_or_none()
    else:
        login_key = (request.phone or "").strip()
        if not login_key:
            cached_user = None
        else:
            user_row = await db.execute(select(User).where(User.phone == login_key))
            cached_user = user_row.scalar_one_or_none()

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    ip_allowed, _ip_error = await check_ip_rate_limit(client_ip)
    if not ip_allowed:
        logger.warning("IP rate limit exceeded for login from %s", client_ip)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    is_allowed, _ = await check_login_rate_limit(login_key)
    if not is_allowed:
        logger.warning("Rate limit exceeded for login key %s", login_key[:8] + "***")
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    if not cached_user:
        verify_password_timing_dummy(request.password)
        attempts_left = await get_login_attempts_remaining(login_key)
        if attempts_left > 0:
            error_msg = _generic_login_failed_message(lang, attempts_left)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    # Check account lockout (read-only, can use cached user)
    is_locked, _ = check_account_lockout(cached_user)
    if is_locked:
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=error_msg)

    # Email login: block GeoIP CN unless whitelisted (phone login unchanged).
    # Skipped in bayi for school deployments.
    if request.email and cached_user and EMAIL_LOGIN_CN_BLOCK_ENABLED and AUTH_MODE != "bayi":
        whitelisted = getattr(cached_user, "email_login_whitelisted_from_cn", False)
        must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
            get_client_ip(http_request),
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

    # Verify captcha
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        # Check for database lock first - don't count as failed attempt
        if captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_msg)

        # For all other captcha errors, increment failed attempts in database
        # Need user attached to session for modification - reload from DB
        result = await db.execute(select(User).where(User.id == cached_user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            await increment_failed_attempts(db_user, db)
            attempts_left = MAX_LOGIN_ATTEMPTS - db_user.failed_login_attempts
            cached_user.failed_login_attempts = db_user.failed_login_attempts
        else:
            attempts_left = MAX_LOGIN_ATTEMPTS - cached_user.failed_login_attempts

        # Provide specific captcha error message
        if captcha_error == "expired":
            captcha_msg = Messages.error("captcha_expired", lang)
        elif captcha_error == "not_found":
            captcha_msg = Messages.error("captcha_not_found", lang)
        elif captcha_error == "incorrect":
            captcha_msg = Messages.error("captcha_incorrect", lang)
        else:
            captcha_msg = Messages.error("captcha_verify_failed", lang)

        if attempts_left > 0:
            attempts_msg = Messages.error("captcha_retry_attempts", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{captcha_msg}{attempts_msg}",
            )
        minutes_left = LOCKOUT_DURATION_MINUTES
        lockout_msg = Messages.error("captcha_account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        schedule_abuseipdb_report_on_lockout(get_client_ip(http_request))
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=lockout_msg)

    # Verify password
    if not verify_password(request.password, cached_user.password_hash):
        # Need user attached to session for modification - reload from DB
        result = await db.execute(select(User).where(User.id == cached_user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            await increment_failed_attempts(db_user, db)
            attempts_left = MAX_LOGIN_ATTEMPTS - db_user.failed_login_attempts
            cached_user.failed_login_attempts = db_user.failed_login_attempts
        else:
            attempts_left = MAX_LOGIN_ATTEMPTS - cached_user.failed_login_attempts
        if attempts_left > 0:
            error_msg = _generic_login_failed_message(lang, attempts_left)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        schedule_abuseipdb_report_on_lockout(get_client_ip(http_request))
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=error_msg)

    # Successful login - clear rate limit attempts in Redis
    await clear_login_attempts(login_key)
    await clear_ip_attempts(client_ip)
    # Need user attached to session for modification - reload from DB
    result = await db.execute(select(User).where(User.id == cached_user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        await reset_failed_attempts(db_user, db)
        user = db_user
    else:
        user = cached_user

    if db_user and not getattr(db_user, "allows_simplified_chinese", True):
        prefs_changed = False
        if (db_user.ui_language or "").lower() == "zh":
            db_user.ui_language = "en"
            prefs_changed = True
        if (db_user.prompt_language or "").lower() == "zh":
            db_user.prompt_language = "en"
            prefs_changed = True
        if prefs_changed:
            await db.commit()
            await db.refresh(db_user)
            user = db_user

    # Get organization (use cache with database fallback)
    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None

    # Check organization status (locked; expired subscription downgrades to trial)
    if org:
        org = await enforce_org_accessible_or_raise(org, lang)

    # Session management: Allow multiple concurrent sessions (up to MAX_CONCURRENT_SESSIONS)
    session_manager = get_session_manager()

    # Generate JWT access token
    token = create_access_token(user)

    # Generate refresh token
    refresh_token_value, refresh_token_hash = create_refresh_token(user.id)

    # Compute device hash for session and token binding
    device_hash = compute_device_hash(http_request)

    # DEBUG: Log device fingerprint at login time
    user_agent = http_request.headers.get("User-Agent", "")
    accept_language = http_request.headers.get("Accept-Language", "")
    sec_ch_platform = http_request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = http_request.headers.get("Sec-CH-UA-Mobile", "")
    logger.info(
        "[TokenAudit] Login device fingerprint: user=%s, device_hash=%s, UA=%s..., lang=%s, platform=%s, mobile=%s",
        user.id,
        device_hash,
        user_agent[:50],
        accept_language[:20],
        sec_ch_platform,
        sec_ch_mobile,
    )

    session_ok = await session_manager.store_session(user.id, token, device_hash=device_hash)

    # Store refresh token with device binding
    refresh_manager = get_refresh_token_manager()
    refresh_ok = await refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )
    _raise_if_session_persistence_failed(session_ok, refresh_ok, lang, user.id, "captcha")

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

    await record_vpn_login_geo(user.id, http_request)

    org_name = org.name if org else "None"
    logger.info(
        "[TokenAudit] Login success: user=%s, phone=%s, email=%s, org=%s, method=captcha, ip=%s, device=%s",
        user.id,
        user.phone,
        getattr(user, "email", None),
        org_name,
        client_ip,
        device_hash,
    )

    # Track user activity
    await track_user_activity(user, "login", {"method": "captcha", "org": org_name}, http_request, db)

    # Preload diagram list for instant library access (fire-and-forget)
    _preload_user_diagrams(user.id)

    return {
        **auth_session_json_metadata(),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "email": getattr(user, "email", None),
            "name": user.name,
            "organization": organization_session_payload(org),
            "avatar": user.avatar or DEFAULT_USER_AVATAR_EMOJI,
            "role": get_user_role(user),
            "ui_language": getattr(user, "ui_language", None),
            "prompt_language": getattr(user, "prompt_language", None),
            "match_prompt_to_ui": getattr(user, "match_prompt_to_ui", True),
            "allows_simplified_chinese": getattr(user, "allows_simplified_chinese", True),
        },
    }


@router.post("/sms/login")
async def login_with_sms(
    request: LoginWithSMSRequest,
    http_request: Request,
    response: Response,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Login with SMS verification

    Alternative to password-based login.
    Requires a valid SMS verification code.

    Benefits:
    - No password required
    - Quick verification

    Brute-force protection: per-IP and per-identifier rate limits are applied
    to the OTP verification attempt (same window as password login) so the
    6-digit code cannot be exhaustively guessed within its TTL.
    """
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    ip_allowed, _ip_error = await check_ip_rate_limit(client_ip)
    if not ip_allowed:
        logger.warning("IP rate limit exceeded for SMS login from %s", client_ip)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    key_allowed, _ = await check_login_rate_limit((request.phone or "").strip())
    if not key_allowed:
        logger.warning("Rate limit exceeded for SMS login key %s***", (request.phone or "")[:8])
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    user_row = await db.execute(select(User).where(User.phone == request.phone))
    user = user_row.scalar_one_or_none()

    if not user:
        attempts_left = await get_login_attempts_remaining(request.phone)
        if attempts_left > 0:
            error_msg = _generic_login_failed_message(lang, attempts_left)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    is_locked, _ = check_account_lockout(user)
    if is_locked:
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=error_msg)

    # Get organization and check status BEFORE consuming code (use cache)
    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None

    # Check organization status (locked; expired subscription downgrades to trial)
    if org:
        org = await enforce_org_accessible_or_raise(org, lang)

    # All validations passed - now consume the SMS code
    await _verify_and_consume_sms_code(request.phone, request.sms_code, "login", db, lang)

    return await _complete_login_after_otp_verified(
        user,
        http_request,
        response,
        db,
        "sms",
        lang,
    )


@router.post("/email/login")
async def login_with_email(
    request: LoginWithEmailRequest,
    http_request: Request,
    response: Response,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Login with email verification code (SES).

    Same guarantees as SMS login: no password, org checks, code consumed once.

    Brute-force protection: per-IP and per-identifier rate limits are applied
    to the OTP verification attempt (same window as password login).
    """
    email_validated = validate_email_for_api(request.email, lang)
    raise_if_mainland_china_email_for_email_login(email_validated, lang)
    email_key = normalize_verification_email(email_validated)

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    ip_allowed, _ip_error = await check_ip_rate_limit(client_ip)
    if not ip_allowed:
        logger.warning("IP rate limit exceeded for email login from %s", client_ip)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    key_allowed, _ = await check_login_rate_limit(email_key)
    if not key_allowed:
        logger.warning("Rate limit exceeded for email login key %s***", email_key[:8])
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    user_row = await db.execute(select(User).where(User.email == email_key))
    user = user_row.scalar_one_or_none()

    if not user:
        attempts_left = await get_login_attempts_remaining(email_key)
        if attempts_left > 0:
            error_msg = _generic_login_failed_message(lang, attempts_left)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None

    if org:
        org = await enforce_org_accessible_or_raise(org, lang)

    if EMAIL_LOGIN_CN_BLOCK_ENABLED and AUTH_MODE != "bayi":
        must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
            get_client_ip(http_request),
            http_request,
            whitelisted_from_cn=getattr(user, "email_login_whitelisted_from_cn", False),
        )
        if must_deny:
            detail = Messages.error(geo_msg_key, lang=lang)
            if geo_msg_key == "email_login_blocked_in_mainland_china":
                return json_forbidden_cn_geo(detail, http_request, stamp_cn)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )

    await verify_and_consume_email_code(request.email, request.email_code, "login", lang)

    return await _complete_login_after_otp_verified(
        user,
        http_request,
        response,
        db,
        "email_otp",
        lang,
    )


@router.post("/bayi/passkey")
async def verify_bayi_passkey_login(
    passkey_request: PasskeyVerifyRequest,
    request: Request,
    response: Response,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Verify Bayi 6-digit passkey and return JWT cookies (AUTH_MODE=bayi only).

    Separate from vendor SSO ``/loginByXz``. Ensures ``bayi@system.com`` exists when first used.
    Grant admin via ``ADMIN_PHONES`` (include ``bayi@system.com`` for passkey admins).
    """
    if AUTH_MODE != "bayi":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Bayi passkey login is disabled: set AUTH_MODE=bayi to use this endpoint. "
                f"(current mode is {AUTH_MODE!r})"
            ),
        )

    client_ip = get_client_ip(request)
    rate_limiter = RedisRateLimiter()
    is_allowed, attempt_count, error_msg = await rate_limiter.check_and_record(
        category="bayi_passkey",
        identifier=client_ip,
        max_attempts=5,
        window_seconds=15 * 60,
    )
    if not is_allowed:
        logger.warning(
            "Bayi passkey rate limit exceeded for IP %s (%s attempts)",
            client_ip,
            attempt_count,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or Messages.error("too_many_login_attempts", lang, 15),
        )

    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(BAYI_PASSKEY)
    logger.info(
        "Bayi passkey attempt - Received: %s chars (reference length=%s)",
        received_length,
        expected_length,
    )

    if not verify_bayi_passkey(passkey_request.passkey):
        logger.warning(
            "Bayi passkey verification failed — check .env whitespace for BAYI_PASSKEY",
        )
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    user_phone = "bayi@system.com"
    user_name = "Bayi User"

    existing_row = await db.execute(select(User).where(User.phone == user_phone))
    auth_user = existing_row.scalar_one_or_none()

    if not auth_user:
        org = None
        if BAYI_DEFAULT_ORG_ID is not None:
            result = await db.execute(select(Organization).where(Organization.id == BAYI_DEFAULT_ORG_ID))
            org = result.scalar_one_or_none()
            if not org:
                logger.error(
                    "Bayi passkey signup: organization id %s (BAYI_DEFAULT_ORG_ID) not found",
                    BAYI_DEFAULT_ORG_ID,
                )
                error_msg = Messages.error("no_organizations_available", lang)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        else:
            result = await db.execute(select(Organization).where(Organization.code == BAYI_DEFAULT_ORG_CODE))
            org = result.scalar_one_or_none()
            if not org:
                org = Organization(
                    code=BAYI_DEFAULT_ORG_CODE,
                    name="Bayi School",
                    invitation_code="BAYI2024",
                    created_at=datetime.now(UTC),
                )
                db.add(org)
                try:
                    await db.commit()
                    await db.refresh(org)
                except DATABASE_ERRORS:
                    await db.rollback()
                    raise
                logger.info("Created bayi organization: %s", BAYI_DEFAULT_ORG_CODE)
                try:
                    await org_cache.cache_org(org)
                except DATABASE_ERRORS as cache_org_err:
                    logger.warning("Failed to cache bayi org: %s", cache_org_err)

        try:
            auth_user = User(
                phone=user_phone,
                password_hash=hash_password("passkey-no-pwd"),
                name=user_name,
                organization_id=org.id,
                created_at=datetime.now(UTC),
            )
            db.add(auth_user)
            try:
                await db.commit()
                await db.refresh(auth_user)
            except REDIS_ERRORS:
                await db.rollback()
                raise
            logger.info("Created Bayi passkey user: %s", user_phone)

            try:
                await user_cache.cache_user(auth_user)
                if org:
                    await org_cache.cache_org(org)
            except REDIS_ERRORS as cache_err:
                logger.warning("Failed to cache Bayi passkey user/org: %s", cache_err)
        except REDIS_ERRORS as exc:
            await db.rollback()
            logger.error("Failed to create Bayi passkey user: %s", exc)

            retry_row = await db.execute(select(User).where(User.phone == user_phone))
            auth_user = retry_row.scalar_one_or_none()
            if not auth_user:
                error_msg = Messages.error("user_creation_failed", "en", str(exc))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg,
                ) from exc

    # Session management: Allow multiple concurrent sessions (up to MAX_CONCURRENT_SESSIONS)
    session_manager = get_session_manager()
    client_ip = get_client_ip(request)

    # Generate JWT access token
    token = create_access_token(auth_user)

    # Generate refresh token
    refresh_token_value, refresh_token_hash = create_refresh_token(auth_user.id)

    # Compute device hash for session and token binding
    device_hash = compute_device_hash(request)

    # DEBUG: Log device fingerprint at login time
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    sec_ch_platform = request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = request.headers.get("Sec-CH-UA-Mobile", "")
    logger.info(
        "[TokenAudit] Login device fingerprint: user=%s, device_hash=%s, UA=%s..., lang=%s, platform=%s, mobile=%s",
        auth_user.id,
        device_hash,
        user_agent[:50],
        accept_language[:20],
        sec_ch_platform,
        sec_ch_mobile,
    )

    # Store access token session in Redis (automatically limits concurrent sessions)
    await session_manager.store_session(auth_user.id, token, device_hash=device_hash)

    # Store refresh token with device binding
    refresh_manager = get_refresh_token_manager()
    await refresh_manager.store_refresh_token(
        user_id=auth_user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, request)

    await record_vpn_login_geo(auth_user.id, request)

    effective_role = get_user_role(auth_user)
    logger.info(
        "[TokenAudit] Login success: user=%s, mode=%s, effective_role=%s, ip=%s, device=%s",
        auth_user.id,
        AUTH_MODE,
        effective_role,
        client_ip,
        device_hash,
    )

    # Preload diagram list for instant library access (fire-and-forget)
    _preload_user_diagrams(auth_user.id)

    return {
        **auth_session_json_metadata(),
        "user": {
            "id": auth_user.id,
            "phone": auth_user.phone,
            "name": auth_user.name,
            "role": effective_role,
            "ui_language": getattr(auth_user, "ui_language", None),
            "prompt_language": getattr(auth_user, "prompt_language", None),
            "match_prompt_to_ui": getattr(auth_user, "match_prompt_to_ui", True),
        },
    }


