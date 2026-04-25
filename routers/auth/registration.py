"""
Registration Endpoints
======================

User registration endpoints:
- /register - Captcha-based registration
- /register_sms - SMS-based registration

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
from models.domain.messages import Messages, Language
from models.domain.auth import User, Organization
from models.requests.requests_auth import RegisterRequest, RegisterWithSMSRequest
from utils.auth import (
    AUTH_MODE,
    hash_password,
    get_client_ip,
    create_access_token,
    create_refresh_token,
    compute_device_hash,
    ACCESS_TOKEN_EXPIRY_MINUTES,
)
from utils.invitations import INVITE_PATTERN
from services.redis.cache.redis_user_cache import user_cache
from services.redis.cache.redis_org_cache import org_cache
from services.redis.redis_distributed_lock import phone_registration_lock
from services.redis.session.redis_session_manager import (
    get_session_manager,
    get_refresh_token_manager,
)
from services.auth.vpn_geo_enforcement import record_vpn_login_geo
from services.monitoring.registration_metrics import registration_metrics
from services.auth.phone_uniqueness import any_user_id_with_phone

from .dependencies import get_language_dependency
from .helpers import commit_user_with_retry, set_auth_cookies, track_user_activity
from .captcha import verify_captcha_with_retry
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


async def finalize_sms_registration_session(
    *,
    new_user: User,
    org: Organization,
    http_request: Request,
    response: Response,
    db: AsyncSession,
    start_time: float,
    retry_count: int,
    register_action: str,
) -> dict:
    """
    Common session, cookies, cache, and response body after a successful
    phone registration that did not use a password on the same request
    (SMS verification or quick registration with room code).
    """
    cache_write_success = False
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    old_token_hash = await session_manager.get_session_token(new_user.id)
    await session_manager.invalidate_user_sessions(new_user.id, old_token_hash=old_token_hash, ip_address=client_ip)

    token = create_access_token(new_user)
    refresh_token_value, refresh_token_hash = create_refresh_token(new_user.id)
    device_hash = compute_device_hash(http_request)
    user_agent = http_request.headers.get("User-Agent", "")

    async def cache_user_async() -> None:
        nonlocal cache_write_success
        try:
            await user_cache.cache_user(new_user)
            cache_write_success = True
            phone_prefix = new_user.phone[:3] if new_user.phone and len(new_user.phone) >= 3 else "***"
            phone_suffix = new_user.phone[-4:] if new_user.phone and len(new_user.phone) >= 4 else ""
            logger.info(
                "[Auth] New user registered and cached: ID %s, phone %s***%s",
                new_user.id,
                phone_prefix,
                phone_suffix,
            )
        except Exception as ex:
            cache_write_success = False
            logger.warning("[Auth] Failed to cache new user ID %s: %s", new_user.id, ex)

    async def store_session_async() -> None:
        try:
            await session_manager.store_session(new_user.id, token, device_hash=device_hash)
        except Exception as ex:
            logger.warning("[Auth] Failed to store session for user ID %s: %s", new_user.id, ex)

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
        except Exception as ex:
            logger.warning(
                "[Auth] Failed to store refresh token for user ID %s: %s",
                new_user.id,
                ex,
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
    org_name = org.name if org else "None"
    log_method = "room_quick" if register_action == "register_quick" else "sms"
    logger.info(
        "[TokenAudit] Registration success: user=%s, phone=***, org=%s, method=%s, ip=%s",
        new_user.id,
        org_name,
        log_method,
        client_ip,
    )
    await track_user_activity(
        new_user,
        "login",
        {"method": log_method, "org": org_name, "action": register_action},
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
            "name": new_user.name,
            "organization": org.name,
            "ui_language": getattr(new_user, "ui_language", None),
            "prompt_language": getattr(new_user, "prompt_language", None),
        },
    }


@router.post("/register")
async def register(
    request: RegisterRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Register new user (K12 teacher)

    Validates:
    - Captcha verification (bot protection)
    - 11-digit Chinese mobile number
    - 8+ character password
    - Mandatory name (no numbers)
    - Valid invitation code (automatically binds user to school)

    Note: Organization is automatically determined from invitation code.
    Each invitation code is unique and belongs to one school.

    Registration is only available in standard and enterprise modes.
    Demo and bayi modes use passkey authentication instead.
    """
    # Check authentication mode - registration not allowed in demo/bayi modes
    if AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Track registration attempt
    registration_metrics.record_attempt()
    start_time = time.time()

    # Validate captcha first (anti-bot protection)
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

    logger.debug("Captcha verified for registration: %s", request.phone)

    retry_count = 0
    cache_write_success = False

    # Find organization by invitation code (each invitation code is unique)
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        duration = time.time() - start_time
        registration_metrics.record_failure("invitation_code_invalid", duration)
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        duration = time.time() - start_time
        registration_metrics.record_failure("invitation_code_invalid", duration)
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Use cache for org lookup (with database fallback)
    org = await org_cache.get_by_invitation_code(provided_invite)
    if not org:
        result = await db.execute(select(Organization).where(Organization.invitation_code == provided_invite))
        org = result.scalar_one_or_none()
        if not org:
            duration = time.time() - start_time
            registration_metrics.record_failure("invitation_code_invalid", duration)
            error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        # Cache organization after database query for next time
        if org:
            try:
                await org_cache.cache_org(org)
            except Exception as e:
                logger.debug("[Auth] Failed to cache org after database query: %s", e)

    logger.debug(
        "User registering with invitation code for organization: %s (%s)",
        org.code,
        org.name,
    )

    # Use distributed lock to prevent race condition on phone uniqueness check
    try:
        async with phone_registration_lock(request.phone):
            if await any_user_id_with_phone(db, request.phone) is not None:
                duration = time.time() - start_time
                registration_metrics.record_failure("phone_exists", duration)
                error_msg = Messages.error("phone_already_registered", lang)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

            # Create new user
            new_user = User(
                phone=request.phone,
                password_hash=hash_password(request.password),
                name=request.name,
                organization_id=org.id,
                created_at=datetime.now(UTC),
            )

            # Write to database FIRST (source of truth) with retry logic for lock errors
            db.add(new_user)
            retry_count = await commit_user_with_retry(
                db, new_user, max_retries=5, lang=lang
            )
    except RuntimeError as e:
        # Lock acquisition failed - fall back to current behavior
        duration = time.time() - start_time
        registration_metrics.record_failure("lock_timeout", duration)
        logger.warning(
            "[Auth] Failed to acquire distributed lock for phone %s***: %s, proceeding without lock",
            request.phone[:3],
            e,
        )
        raise
    except HTTPException as e:
        # Track specific HTTP exceptions before re-raising
        duration = time.time() - start_time
        if e.status_code == status.HTTP_400_BAD_REQUEST and "sms_code" in str(e.detail).lower():
            registration_metrics.record_failure("sms_code_invalid", duration)
        raise
    except Exception as e:
        # Track other failures (database lock, etc.)
        duration = time.time() - start_time
        if "database is locked" in str(e).lower() or "locked" in str(e).lower():
            registration_metrics.record_failure("database_deadlock", duration)
        else:
            registration_metrics.record_failure("other", duration)
        raise

    # Session management: Allow multiple concurrent sessions (up to MAX_CONCURRENT_SESSIONS)
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"

    # Generate JWT access token
    token = create_access_token(new_user)

    # Generate refresh token
    refresh_token_value, refresh_token_hash = create_refresh_token(new_user.id)

    # Compute device hash for session and token binding
    device_hash = compute_device_hash(http_request)
    user_agent = http_request.headers.get("User-Agent", "")

    # Parallel cache write, session creation, and refresh token storage
    async def cache_user_async():
        """Cache user in Redis (non-blocking)."""
        nonlocal cache_write_success
        try:
            await user_cache.cache_user(new_user)
            cache_write_success = True
            phone_prefix = new_user.phone[:3] if new_user.phone and len(new_user.phone) >= 3 else "***"
            phone_suffix = new_user.phone[-4:] if new_user.phone and len(new_user.phone) >= 4 else ""
            logger.info(
                "[Auth] New user registered and cached: ID %s, phone %s***%s",
                new_user.id,
                phone_prefix,
                phone_suffix,
            )
        except Exception as e:
            cache_write_success = False
            logger.warning("[Auth] Failed to cache new user ID %s: %s", new_user.id, e)

    async def store_session_async():
        """Store session in Redis (non-blocking)."""
        try:
            await session_manager.store_session(new_user.id, token, device_hash=device_hash)
        except Exception as e:
            logger.warning("[Auth] Failed to store session for user ID %s: %s", new_user.id, e)

    async def store_refresh_token_async():
        """Store refresh token in Redis with device binding."""
        try:
            refresh_manager = get_refresh_token_manager()
            await refresh_manager.store_refresh_token(
                user_id=new_user.id,
                token_hash=refresh_token_hash,
                ip_address=client_ip,
                user_agent=user_agent,
                device_hash=device_hash,
            )
        except Exception as e:
            logger.warning(
                "[Auth] Failed to store refresh token for user ID %s: %s",
                new_user.id,
                e,
            )

    # Execute cache write, session creation, and refresh token storage in parallel
    await asyncio.gather(
        cache_user_async(),
        store_session_async(),
        store_refresh_token_async(),
        return_exceptions=True,
    )

    # Track successful registration
    duration = time.time() - start_time
    registration_metrics.record_success(duration, retry_count, cache_write_success)

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

    await record_vpn_login_geo(new_user.id, http_request)

    org_name = org.name if org else "None"
    logger.info(
        "[TokenAudit] Registration success: user=%s, phone=%s, org=%s, method=captcha, ip=%s",
        new_user.id,
        new_user.phone,
        org_name,
        client_ip,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "name": new_user.name,
            "organization": org.name,
            "ui_language": getattr(new_user, "ui_language", None),
            "prompt_language": getattr(new_user, "prompt_language", None),
        },
    }


@router.post("/register_sms")
async def register_with_sms(
    request: RegisterWithSMSRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Register new user with SMS verification

    Alternative to captcha-based registration.
    Requires a valid SMS verification code.

    Validates:
    - 11-digit Chinese mobile number
    - 8+ character password
    - Mandatory name (no numbers)
    - Valid invitation code
    - SMS verification code (consumed last to avoid wasting codes)

    Registration is only available in standard and enterprise modes.
    Demo and bayi modes use passkey authentication instead.
    """
    # Check authentication mode - registration not allowed in demo/bayi modes
    if AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Track registration attempt
    registration_metrics.record_attempt()
    start_time = time.time()
    retry_count = 0

    # Find organization by invitation code
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        duration = time.time() - start_time
        registration_metrics.record_failure("invitation_code_invalid", duration)
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        duration = time.time() - start_time
        registration_metrics.record_failure("invitation_code_invalid", duration)
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Use cache for org lookup (with database fallback)
    org = await org_cache.get_by_invitation_code(provided_invite)
    if not org:
        result = await db.execute(select(Organization).where(Organization.invitation_code == provided_invite))
        org = result.scalar_one_or_none()
        if not org:
            duration = time.time() - start_time
            registration_metrics.record_failure("invitation_code_invalid", duration)
            error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        # Cache organization after database query for next time
        if org:
            try:
                await org_cache.cache_org(org)
            except Exception as e:
                logger.debug("[Auth] Failed to cache org after database query: %s", e)

    # Use distributed lock to prevent race condition on phone uniqueness check
    try:
        async with phone_registration_lock(request.phone):
            if await any_user_id_with_phone(db, request.phone) is not None:
                duration = time.time() - start_time
                registration_metrics.record_failure("phone_exists", duration)
                error_msg = Messages.error("phone_already_registered", lang)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

            # All validations passed - now consume the SMS code
            await _verify_and_consume_sms_code(request.phone, request.sms_code, "register", db, lang)

            logger.debug(
                "User registering with SMS for organization: %s (%s)",
                org.code,
                org.name,
            )

            # Create new user
            new_user = User(
                phone=request.phone,
                password_hash=hash_password(request.password),
                name=request.name,
                organization_id=org.id,
                created_at=datetime.now(UTC),
            )

            # Write to database FIRST (source of truth) with retry logic for lock errors
            db.add(new_user)
            retry_count = await commit_user_with_retry(
                db, new_user, max_retries=5, lang=lang
            )
    except RuntimeError as e:
        duration = time.time() - start_time
        registration_metrics.record_failure("lock_timeout", duration)
        logger.warning(
            "[Auth] Failed to acquire distributed lock for phone %s***: %s, proceeding without lock",
            request.phone[:3],
            e,
        )
        raise
    except HTTPException as e:
        duration = time.time() - start_time
        if e.status_code == status.HTTP_400_BAD_REQUEST and "sms_code" in str(e.detail).lower():
            registration_metrics.record_failure("sms_code_invalid", duration)
        raise
    except Exception as e:
        duration = time.time() - start_time
        if "database is locked" in str(e).lower() or "locked" in str(e).lower():
            registration_metrics.record_failure("database_deadlock", duration)
        else:
            registration_metrics.record_failure("other", duration)
        raise

    return await finalize_sms_registration_session(
        new_user=new_user,
        org=org,
        http_request=http_request,
        response=response,
        db=db,
        start_time=start_time,
        retry_count=retry_count,
        register_action="register_sms",
    )
