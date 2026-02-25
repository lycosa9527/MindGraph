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
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.messages import Messages, Language
from models.domain.auth import User, Organization
from models.requests.requests_auth import RegisterRequest, RegisterWithSMSRequest
from utils.auth import (
    AUTH_MODE, hash_password, get_client_ip,
    create_access_token, create_refresh_token, compute_device_hash,
    ACCESS_TOKEN_EXPIRY_MINUTES
)
from utils.invitations import INVITE_PATTERN
from services.redis.cache.redis_user_cache import user_cache
from services.redis.cache.redis_org_cache import org_cache
from services.redis.redis_distributed_lock import phone_registration_lock
from services.redis.session.redis_session_manager import get_session_manager, get_refresh_token_manager
from services.monitoring.registration_metrics import registration_metrics

from .dependencies import get_language_dependency
from .helpers import (
    commit_user_with_retry,
    set_auth_cookies,
    track_user_activity
)
from .captcha import verify_captcha_with_retry
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register")
async def register(
    request: RegisterRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )

    # Track registration attempt
    registration_metrics.record_attempt()
    start_time = time.time()

    # Validate captcha first (anti-bot protection)
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        duration = time.time() - start_time
        registration_metrics.record_failure('captcha_failed', duration)
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

    logger.debug("Captcha verified for registration: %s", request.phone)

    retry_count = 0
    cache_write_success = False

    # Find organization by invitation code (each invitation code is unique)
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        duration = time.time() - start_time
        registration_metrics.record_failure('invitation_code_invalid', duration)
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        duration = time.time() - start_time
        registration_metrics.record_failure('invitation_code_invalid', duration)
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Use cache for org lookup (with database fallback)
    org = org_cache.get_by_invitation_code(provided_invite)
    if not org:
        org = db.query(Organization).filter(
            Organization.invitation_code == provided_invite
        ).first()
        if not org:
            duration = time.time() - start_time
            registration_metrics.record_failure('invitation_code_invalid', duration)
            error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        # Cache organization after database query for next time
        if org:
            try:
                org_cache.cache_org(org)
            except Exception as e:
                logger.debug("[Auth] Failed to cache org after database query: %s", e)

    logger.debug(
        "User registering with invitation code for organization: %s (%s)",
        org.code, org.name
    )

    # Use distributed lock to prevent race condition on phone uniqueness check
    try:
        async with phone_registration_lock(request.phone):
            # Check if phone already exists (use cache with database fallback)
            existing_user = user_cache.get_by_phone(request.phone)
            if existing_user:
                duration = time.time() - start_time
                registration_metrics.record_failure('phone_exists', duration)
                error_msg = Messages.error("phone_already_registered", lang)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=error_msg
                )

            # Create new user
            new_user = User(
                phone=request.phone,
                password_hash=hash_password(request.password),
                name=request.name,
                organization_id=org.id,
                created_at=datetime.now(timezone.utc)
            )

            # Write to database FIRST (source of truth) with retry logic for lock errors
            db.add(new_user)
            retry_count = await commit_user_with_retry(db, new_user, max_retries=5)
    except RuntimeError as e:
        # Lock acquisition failed - fall back to current behavior
        duration = time.time() - start_time
        registration_metrics.record_failure('lock_timeout', duration)
        logger.warning(
            "[Auth] Failed to acquire distributed lock for phone %s***: %s, "
            "proceeding without lock",
            request.phone[:3], e
        )
        raise
    except HTTPException as e:
        # Track specific HTTP exceptions before re-raising
        duration = time.time() - start_time
        if e.status_code == status.HTTP_400_BAD_REQUEST and "sms_code" in str(e.detail).lower():
            registration_metrics.record_failure('sms_code_invalid', duration)
        raise
    except Exception as e:
        # Track other failures (database lock, etc.)
        duration = time.time() - start_time
        if "database is locked" in str(e).lower() or "locked" in str(e).lower():
            registration_metrics.record_failure('database_deadlock', duration)
        else:
            registration_metrics.record_failure('other', duration)
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
            user_cache.cache_user(new_user)
            cache_write_success = True
            phone_prefix = (
                new_user.phone[:3] if len(new_user.phone) >= 3 else '***'
            )
            phone_suffix = (
                new_user.phone[-4:] if len(new_user.phone) >= 4 else ''
            )
            logger.info(
                "[Auth] New user registered and cached: ID %s, phone %s***%s",
                new_user.id, phone_prefix, phone_suffix
            )
        except Exception as e:
            cache_write_success = False
            logger.warning("[Auth] Failed to cache new user ID %s: %s", new_user.id, e)

    async def store_session_async():
        """Store session in Redis (non-blocking)."""
        try:
            session_manager.store_session(new_user.id, token, device_hash=device_hash)
        except Exception as e:
            logger.warning(
                "[Auth] Failed to store session for user ID %s: %s",
                new_user.id, e
            )

    async def store_refresh_token_async():
        """Store refresh token in Redis with device binding."""
        try:
            refresh_manager = get_refresh_token_manager()
            refresh_manager.store_refresh_token(
                user_id=new_user.id,
                token_hash=refresh_token_hash,
                ip_address=client_ip,
                user_agent=user_agent,
                device_hash=device_hash
            )
        except Exception as e:
            logger.warning(
                "[Auth] Failed to store refresh token for user ID %s: %s",
                new_user.id, e
            )

    # Execute cache write, session creation, and refresh token storage in parallel
    await asyncio.gather(
        cache_user_async(),
        store_session_async(),
        store_refresh_token_async(),
        return_exceptions=True
    )

    # Track successful registration
    duration = time.time() - start_time
    registration_metrics.record_success(duration, retry_count, cache_write_success)

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

    org_name = org.name if org else "None"
    logger.info(
        "[TokenAudit] Registration success: user=%s, phone=%s, org=%s, "
        "method=captcha, ip=%s",
        new_user.id, new_user.phone, org_name, client_ip
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "name": new_user.name,
            "organization": org.name
        }
    }


@router.post("/register_sms")
async def register_with_sms(
    request: RegisterWithSMSRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )

    # Track registration attempt
    registration_metrics.record_attempt()
    start_time = time.time()
    retry_count = 0
    cache_write_success = False

    # Find organization by invitation code
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        duration = time.time() - start_time
        registration_metrics.record_failure('invitation_code_invalid', duration)
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        duration = time.time() - start_time
        registration_metrics.record_failure('invitation_code_invalid', duration)
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Use cache for org lookup (with database fallback)
    org = org_cache.get_by_invitation_code(provided_invite)
    if not org:
        org = db.query(Organization).filter(
            Organization.invitation_code == provided_invite
        ).first()
        if not org:
            duration = time.time() - start_time
            registration_metrics.record_failure('invitation_code_invalid', duration)
            error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        # Cache organization after database query for next time
        if org:
            try:
                org_cache.cache_org(org)
            except Exception as e:
                logger.debug("[Auth] Failed to cache org after database query: %s", e)

    # Use distributed lock to prevent race condition on phone uniqueness check
    try:
        async with phone_registration_lock(request.phone):
            # Check if phone already exists (use cache with database fallback)
            existing_user = user_cache.get_by_phone(request.phone)
            if existing_user:
                duration = time.time() - start_time
                registration_metrics.record_failure('phone_exists', duration)
                error_msg = Messages.error("phone_already_registered", lang)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=error_msg
                )

            # All validations passed - now consume the SMS code
            _verify_and_consume_sms_code(
                request.phone,
                request.sms_code,
                "register",
                db,
                lang
            )

            logger.debug(
                "User registering with SMS for organization: %s (%s)",
                org.code, org.name
            )

            # Create new user
            new_user = User(
                phone=request.phone,
                password_hash=hash_password(request.password),
                name=request.name,
                organization_id=org.id,
                created_at=datetime.now(timezone.utc)
            )

            # Write to database FIRST (source of truth) with retry logic for lock errors
            db.add(new_user)
            retry_count = await commit_user_with_retry(db, new_user, max_retries=5)
    except RuntimeError as e:
        duration = time.time() - start_time
        registration_metrics.record_failure('lock_timeout', duration)
        logger.warning(
            "[Auth] Failed to acquire distributed lock for phone %s***: %s, "
            "proceeding without lock",
            request.phone[:3], e
        )
        raise
    except HTTPException as e:
        duration = time.time() - start_time
        if e.status_code == status.HTTP_400_BAD_REQUEST and "sms_code" in str(e.detail).lower():
            registration_metrics.record_failure('sms_code_invalid', duration)
        raise
    except Exception as e:
        duration = time.time() - start_time
        if "database is locked" in str(e).lower() or "locked" in str(e).lower():
            registration_metrics.record_failure('database_deadlock', duration)
        else:
            registration_metrics.record_failure('other', duration)
        raise

    # Session management: Invalidate old sessions before creating new one
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    old_token_hash = session_manager.get_session_token(new_user.id)
    session_manager.invalidate_user_sessions(new_user.id, old_token_hash=old_token_hash, ip_address=client_ip)

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
            user_cache.cache_user(new_user)
            cache_write_success = True
            phone_prefix = (
                new_user.phone[:3] if len(new_user.phone) >= 3 else '***'
            )
            phone_suffix = (
                new_user.phone[-4:] if len(new_user.phone) >= 4 else ''
            )
            logger.info(
                "[Auth] New user registered and cached: ID %s, phone %s***%s",
                new_user.id, phone_prefix, phone_suffix
            )
        except Exception as e:
            cache_write_success = False
            logger.warning("[Auth] Failed to cache new user ID %s: %s", new_user.id, e)

    async def store_session_async():
        """Store session in Redis (non-blocking)."""
        try:
            session_manager.store_session(new_user.id, token, device_hash=device_hash)
        except Exception as e:
            logger.warning(
                "[Auth] Failed to store session for user ID %s: %s",
                new_user.id, e
            )

    async def store_refresh_token_async():
        """Store refresh token in Redis with device binding."""
        try:
            refresh_manager = get_refresh_token_manager()
            refresh_manager.store_refresh_token(
                user_id=new_user.id,
                token_hash=refresh_token_hash,
                ip_address=client_ip,
                user_agent=user_agent,
                device_hash=device_hash
            )
        except Exception as e:
            logger.warning(
                "[Auth] Failed to store refresh token for user ID %s: %s",
                new_user.id, e
            )

    # Execute cache write, session creation, and refresh token storage in parallel
    await asyncio.gather(
        cache_user_async(),
        store_session_async(),
        store_refresh_token_async(),
        return_exceptions=True
    )

    # Track successful registration
    duration = time.time() - start_time
    registration_metrics.record_success(duration, retry_count, cache_write_success)

    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)

    org_name = org.name if org else "None"
    logger.info(
        "[TokenAudit] Registration success: user=%s, phone=%s, org=%s, "
        "method=sms, ip=%s",
        new_user.id, new_user.phone, org_name, client_ip
    )

    # Track user activity
    track_user_activity(
        new_user, 'login',
        {'method': 'sms', 'org': org_name, 'action': 'register'},
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
            "organization": org.name
        }
    }
