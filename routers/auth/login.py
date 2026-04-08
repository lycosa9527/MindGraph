"""
Login Endpoints
===============

User login endpoints:
- /login - Password-based login with captcha
- /login_sms - SMS-based login
- /demo/verify - Demo/bayi passkey verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.messages import Messages, Language
from models.domain.auth import User, Organization
from models.requests.requests_auth import (
    DemoPasskeyRequest,
    LoginRequest,
    LoginWithSMSRequest,
)
from services.redis.cache.redis_org_cache import org_cache
from services.redis.rate_limiting.redis_rate_limiter import (
    check_login_rate_limit,
    clear_login_attempts,
    get_login_attempts_remaining,
    RedisRateLimiter,
)
from services.monitoring.dashboard_session import get_dashboard_session_manager
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.redis.redis_email_storage import normalize_verification_email
from services.redis.session.redis_session_manager import (
    get_session_manager,
    get_refresh_token_manager,
)
from services.auth.geoip_country import evaluate_email_login_geoip
from services.redis.cache.redis_user_cache import user_cache
from utils.email_validation import validate_email_for_api
from utils.auth import (
    AUTH_MODE,
    BAYI_DEFAULT_ORG_CODE,
    EMAIL_LOGIN_CN_BLOCK_ENABLED,
    DEMO_PASSKEY,
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    PUBLIC_DASHBOARD_PASSKEY,
    RATE_LIMIT_WINDOW_MINUTES,
    check_account_lockout,
    create_access_token,
    create_refresh_token,
    compute_device_hash,
    get_client_ip,
    get_user_role,
    hash_password,
    increment_failed_attempts,
    is_admin_demo_passkey,
    is_https,
    reset_failed_attempts,
    verify_dashboard_passkey,
    verify_demo_passkey,
    verify_password,
    ACCESS_TOKEN_EXPIRY_MINUTES,
)

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .helpers import set_auth_cookies, track_user_activity
from .sms import _verify_and_consume_sms_code


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
            except Exception as e:
                logging.getLogger(__name__).debug("[Login] Diagram preload failed for user %s: %s", user_id, e)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_do_preload())
        except RuntimeError:
            pass
    except Exception as exc:
        logger.debug("Failed to preload diagrams: %s", exc)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
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
        login_key = normalize_verification_email(validate_email_for_api(request.email, lang))
        cached_user = await user_cache.get_by_email(login_key)
    else:
        login_key = request.phone.strip()
        cached_user = await user_cache.get_by_phone(login_key)

    is_allowed, _ = check_login_rate_limit(login_key)
    if not is_allowed:
        logger.warning("Rate limit exceeded for login key %s", login_key[:8] + "***")
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    if not cached_user:
        attempts_left = get_login_attempts_remaining(login_key)
        if attempts_left > 0:
            error_msg = Messages.error("login_failed_identifier_not_found", lang, attempts_left)
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
    # Skipped in demo/bayi for predictable local and showcase environments.
    if (
        request.email
        and cached_user
        and EMAIL_LOGIN_CN_BLOCK_ENABLED
        and AUTH_MODE not in ("demo", "bayi")
    ):
        whitelisted = getattr(cached_user, "email_login_whitelisted_from_cn", False)
        must_deny, geo_msg_key = evaluate_email_login_geoip(
            get_client_ip(http_request),
            whitelisted,
        )
        if must_deny:
            detail = Messages.error(geo_msg_key, lang=lang)
            if geo_msg_key == "email_login_blocked_in_mainland_china":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=detail,
                )
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
            increment_failed_attempts(db_user, db)
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
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=lockout_msg)

    # Verify password
    if not verify_password(request.password, cached_user.password_hash):
        # Need user attached to session for modification - reload from DB
        result = await db.execute(select(User).where(User.id == cached_user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            increment_failed_attempts(db_user, db)
            attempts_left = MAX_LOGIN_ATTEMPTS - db_user.failed_login_attempts
            cached_user.failed_login_attempts = db_user.failed_login_attempts
        else:
            attempts_left = MAX_LOGIN_ATTEMPTS - cached_user.failed_login_attempts
        if attempts_left > 0:
            error_msg = Messages.error("invalid_password", lang, attempts_left)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=error_msg)

    # Successful login - clear rate limit attempts in Redis
    clear_login_attempts(login_key)
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

    # Check organization status (locked or expired)
    if org:
        is_active = org.is_active if hasattr(org, "is_active") else True
        if not is_active:
            logger.warning("Login blocked: Organization %s is locked", org.code)
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

        if hasattr(org, "expires_at") and org.expires_at:
            if org.expires_at < datetime.now(UTC):
                logger.warning(
                    "Login blocked: Organization %s expired on %s",
                    org.code,
                    org.expires_at,
                )
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Session management: Allow multiple concurrent sessions (up to MAX_CONCURRENT_SESSIONS)
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"

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

    # Store access token session in Redis (automatically limits concurrent sessions)
    session_manager.store_session(user.id, token, device_hash=device_hash)

    # Store refresh token with device binding
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

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
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "email": getattr(user, "email", None),
            "name": user.name,
            "organization": org.name if org else None,
            "avatar": user.avatar or "🐈‍⬛",
            "role": get_user_role(user),
            "ui_language": getattr(user, "ui_language", None),
            "prompt_language": getattr(user, "prompt_language", None),
            "allows_simplified_chinese": getattr(user, "allows_simplified_chinese", True),
        },
    }


@router.post("/sms/login")
async def login_with_sms(
    request: LoginWithSMSRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Login with SMS verification

    Alternative to password-based login.
    Requires a valid SMS verification code.

    Benefits:
    - No password required
    - Bypasses account lockout
    - Quick verification
    """
    # Find user first (use cache with database fallback)
    user = await user_cache.get_by_phone(request.phone)

    if not user:
        error_msg = Messages.error("phone_not_registered_login", lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Get organization and check status BEFORE consuming code (use cache)
    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None

    # Check organization status
    if org:
        is_active = org.is_active if hasattr(org, "is_active") else True
        if not is_active:
            logger.warning("SMS login blocked: Organization %s is locked", org.code)
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

        if hasattr(org, "expires_at") and org.expires_at:
            if org.expires_at < datetime.now(UTC):
                logger.warning("SMS login blocked: Organization %s expired", org.code)
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # All validations passed - now consume the SMS code
    _verify_and_consume_sms_code(request.phone, request.sms_code, "login", db, lang)

    # Reload user from database for modification (cached user is detached)
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()
    if db_user:
        # Reset any failed attempts (SMS login is verified)
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
                user_cache.cache_user(db_user)
            except Exception as cache_exc:
                logger.warning("[Auth] SMS login: failed to refresh user cache: %s", cache_exc)

    # Session management: Allow multiple concurrent sessions (up to MAX_CONCURRENT_SESSIONS)
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"

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

    # Store access token session in Redis (automatically limits concurrent sessions)
    session_manager.store_session(user.id, token, device_hash=device_hash)

    # Store refresh token with device binding
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

    # Use cache for org lookup (with database fallback)
    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None
    if not org and user.organization_id:
        result = await db.execute(select(Organization).where(Organization.id == user.organization_id))
        org = result.scalar_one_or_none()
        if org:
            db.expunge(org)
            org_cache.cache_org(org)
    org_name = org.name if org else "None"

    logger.info(
        "[TokenAudit] Login success: user=%s, phone=%s, org=%s, method=sms, ip=%s, device=%s",
        user.id,
        user.phone,
        org_name,
        client_ip,
        device_hash,
    )

    # Track user activity
    await track_user_activity(user, "login", {"method": "sms", "org": org_name}, http_request, db)

    # Preload diagram list for instant library access (fire-and-forget)
    _preload_user_diagrams(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization": org.name if org else None,
            "avatar": user.avatar or "🐈‍⬛",
            "role": get_user_role(user),
            "ui_language": getattr(user, "ui_language", None),
            "prompt_language": getattr(user, "prompt_language", None),
            "allows_simplified_chinese": getattr(user, "allows_simplified_chinese", True),
        },
    }


@router.post("/demo/verify")
async def verify_demo(
    passkey_request: DemoPasskeyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Verify demo/bayi passkey and return JWT token

    Demo mode and Bayi mode allow access with a 6-digit passkey.
    Supports both regular demo access and admin demo access.
    In bayi mode, creates bayi-specific users.
    """
    # Enhanced logging for debugging (without revealing actual passkeys)
    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(DEMO_PASSKEY)
    logger.info(
        "Passkey verification attempt (%s mode) - Received: %s chars, Expected: %s chars",
        AUTH_MODE,
        received_length,
        expected_length,
    )

    if not verify_demo_passkey(passkey_request.passkey):
        logger.warning(
            "Passkey verification failed - Check .env file for whitespace in DEMO_PASSKEY or ADMIN_DEMO_PASSKEY"
        )
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    # Check if this is admin demo access
    is_admin_access = is_admin_demo_passkey(passkey_request.passkey)

    # Determine user phone and name based on mode
    if AUTH_MODE == "bayi":
        user_phone = "bayi-admin@system.com" if is_admin_access else "bayi@system.com"
        user_name = "Bayi Admin" if is_admin_access else "Bayi User"
    else:
        user_phone = "demo-admin@system.com" if is_admin_access else "demo@system.com"
        user_name = "Demo Admin" if is_admin_access else "Demo User"

    # Get or create user (use cache with database fallback)
    auth_user = await user_cache.get_by_phone(user_phone)

    if not auth_user:
        # Get or create organization based on mode
        if AUTH_MODE == "bayi":
            result = await db.execute(select(Organization).where(Organization.code == BAYI_DEFAULT_ORG_CODE))
            org = result.scalar_one_or_none()
            if not org:
                # Create bayi organization if it doesn't exist
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
                except Exception:
                    await db.rollback()
                    raise
                logger.info("Created bayi organization: %s", BAYI_DEFAULT_ORG_CODE)
                # Cache the newly created org (non-blocking)
                try:
                    org_cache.cache_org(org)
                except Exception as e:
                    logger.warning("Failed to cache bayi org: %s", e)
        else:
            # Demo mode: use first available organization
            result = await db.execute(select(Organization))
            org = result.scalars().first()
            if not org:
                error_msg = Messages.error("no_organizations_available", "en")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)

        try:
            # Use a short, simple password (bcrypt max is 72 bytes)
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
            except Exception:
                await db.rollback()
                raise
            logger.info("Created new %s user: %s", AUTH_MODE, user_phone)

            # Cache the newly created user and org (non-blocking)
            try:
                user_cache.cache_user(auth_user)
                if org:
                    org_cache.cache_org(org)
            except Exception as e:
                logger.warning("Failed to cache demo user/org: %s", e)
        except Exception as e:
            # If creation fails, try to rollback and check if user was somehow created
            await db.rollback()
            logger.error("Failed to create %s user: %s", AUTH_MODE, e)

            # Try to get the user again in case it was created by another request (use cache)
            auth_user = await user_cache.get_by_phone(user_phone)
            if not auth_user:
                error_msg = Messages.error("user_creation_failed", "en", str(e))
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg) from e

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
    session_manager.store_session(auth_user.id, token, device_hash=device_hash)

    # Store refresh token with device binding
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=auth_user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, request)

    logger.info(
        "[TokenAudit] Login success: user=%s, mode=%s, admin=%s, ip=%s, device=%s",
        auth_user.id,
        AUTH_MODE,
        is_admin_access,
        client_ip,
        device_hash,
    )

    # Preload diagram list for instant library access (fire-and-forget)
    _preload_user_diagrams(auth_user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": auth_user.id,
            "phone": auth_user.phone,
            "name": auth_user.name,
            "role": "admin" if is_admin_access else "user",
            "ui_language": getattr(auth_user, "ui_language", None),
            "prompt_language": getattr(auth_user, "prompt_language", None),
        },
    }


@router.post("/public-dashboard/verify")
async def verify_public_dashboard(
    passkey_request: DemoPasskeyRequest,
    request: Request,
    response: Response,
    lang: Language = Depends(get_language_dependency),
):
    """
    Verify public dashboard passkey and return dashboard session token

    Public dashboard allows access with a 6-digit passkey.
    Creates a simple dashboard session (not a full user account).
    """
    client_ip = get_client_ip(request)

    # Rate limiting: 5 attempts per IP per 15 minutes
    rate_limiter = RedisRateLimiter()
    is_allowed, attempt_count, error_msg = rate_limiter.check_and_record(
        category="dashboard_passkey",
        identifier=client_ip,
        max_attempts=5,
        window_seconds=15 * 60,  # 15 minutes
    )

    if not is_allowed:
        logger.warning(
            "Dashboard passkey rate limit exceeded for IP %s (%s attempts)",
            client_ip,
            attempt_count,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or Messages.error("too_many_login_attempts", lang, 15),
        )

    # Enhanced logging for debugging (without revealing actual passkeys)
    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(PUBLIC_DASHBOARD_PASSKEY)
    logger.info(
        "Dashboard passkey verification attempt - Received: %s chars, Expected: %s chars",
        received_length,
        expected_length,
    )

    if not verify_dashboard_passkey(passkey_request.passkey):
        logger.warning("Dashboard passkey verification failed for IP %s", client_ip)
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    # Create dashboard session
    session_manager = get_dashboard_session_manager()
    dashboard_token = session_manager.create_session(client_ip)

    # Set dashboard access cookie
    response.set_cookie(
        key="dashboard_access_token",
        value=dashboard_token,
        httponly=True,
        secure=is_https(request),  # Auto-detect HTTPS
        samesite="lax",
        max_age=24 * 60 * 60,  # 24 hours
    )

    logger.info("Dashboard access granted for IP %s", client_ip)

    return {
        "success": True,
        "message": "Access granted",
        "dashboard_token": dashboard_token,
    }
