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

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.messages import Messages
from models.auth import Organization, User
from models.requests import DemoPasskeyRequest, LoginRequest, LoginWithSMSRequest
from services.redis_org_cache import org_cache
from services.redis_rate_limiter import (
    check_login_rate_limit,
    clear_login_attempts,
    get_login_attempts_remaining,
    RedisRateLimiter
)
from services.dashboard_session import get_dashboard_session_manager
from services.redis_session_manager import get_session_manager, get_refresh_token_manager
from services.redis_user_cache import user_cache
from utils.auth import (
    AUTH_MODE,
    BAYI_DEFAULT_ORG_CODE,
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
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
    ACCESS_TOKEN_EXPIRY_MINUTES
)

from .captcha import verify_captcha_with_retry
from .dependencies import get_language_dependency
from .helpers import set_auth_cookies, track_user_activity
from .sms import _verify_and_consume_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """
    User login with captcha verification
    
    Security features:
    - Captcha verification (bot protection)
    - Rate limiting: 10 attempts per 15 minutes (per phone)
    - Account lockout: 5 minutes after 10 failed attempts
    - Failed attempt tracking in database
    """
    # Check rate limit by phone (Redis-backed, shared across workers)
    is_allowed, rate_limit_error = check_login_rate_limit(request.phone)
    if not is_allowed:
        logger.warning(f"Rate limit exceeded for {request.phone}")
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    # Find user (use cache with SQLite fallback)
    cached_user = user_cache.get_by_phone(request.phone)
    
    if not cached_user:
        attempts_left = get_login_attempts_remaining(request.phone)
        if attempts_left > 0:
            error_msg = Messages.error("login_failed_phone_not_found", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
    
    # For read-only operations, use cached user (detached is fine)
    # For write operations, we need user attached to session - reload from DB if needed
    # Check account lockout (read-only, can use cached user)
    is_locked, _ = check_account_lockout(cached_user)
    if is_locked:
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=error_msg
        )
    
    # Verify captcha
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        # Check for database lock first - don't count as failed attempt
        if captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        
        # For all other captcha errors, increment failed attempts in database
        # Need user attached to session for modification - reload from DB
        db_user = db.query(User).filter(User.id == cached_user.id).first()
        if db_user:
            increment_failed_attempts(db_user, db)
            attempts_left = MAX_LOGIN_ATTEMPTS - db_user.failed_login_attempts
            # Update cached user's failed_login_attempts for subsequent checks
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
                detail=f"{captcha_msg}{attempts_msg}"
            )
        else:
            minutes_left = LOCKOUT_DURATION_MINUTES
            lockout_msg = Messages.error("captcha_account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=lockout_msg
            )
    
    # Verify password
    if not verify_password(request.password, cached_user.password_hash):
        # Need user attached to session for modification - reload from DB
        db_user = db.query(User).filter(User.id == cached_user.id).first()
        if db_user:
            increment_failed_attempts(db_user, db)
            attempts_left = MAX_LOGIN_ATTEMPTS - db_user.failed_login_attempts
            # Update cached user's failed_login_attempts for subsequent checks
            cached_user.failed_login_attempts = db_user.failed_login_attempts
        else:
            attempts_left = MAX_LOGIN_ATTEMPTS - cached_user.failed_login_attempts
        if attempts_left > 0:
            error_msg = Messages.error("invalid_password", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )
        else:
            minutes_left = LOCKOUT_DURATION_MINUTES
            error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=error_msg
            )
    
    # Successful login - clear rate limit attempts in Redis
    clear_login_attempts(request.phone)
    # Need user attached to session for modification - reload from DB
    db_user = db.query(User).filter(User.id == cached_user.id).first()
    if db_user:
        reset_failed_attempts(db_user, db)
        user = db_user  # Use DB user for rest of function
    else:
        user = cached_user  # Fallback to cached user
    
    # Get organization (use cache with SQLite fallback)
    org = org_cache.get_by_id(user.organization_id) if user.organization_id else None
    
    # Check organization status (locked or expired)
    if org:
        is_active = org.is_active if hasattr(org, 'is_active') else True
        if not is_active:
            logger.warning(f"Login blocked: Organization {org.code} is locked")
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        if hasattr(org, 'expires_at') and org.expires_at:
            if org.expires_at < datetime.now(timezone.utc):
                logger.warning(f"Login blocked: Organization {org.code} expired on {org.expires_at}")
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg
                )
    
    # Session management: Invalidate old sessions before creating new one
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    old_token_hash = session_manager.get_session_token(user.id)
    session_manager.invalidate_user_sessions(user.id, old_token_hash=old_token_hash, ip_address=client_ip)
    
    # Generate JWT access token
    token = create_access_token(user)
    
    # Generate refresh token
    refresh_token_value, refresh_token_hash = create_refresh_token(user.id)
    
    # Store access token session in Redis
    session_manager.store_session(user.id, token)
    
    # Store refresh token with device binding
    user_agent = http_request.headers.get("User-Agent", "")
    device_hash = compute_device_hash(http_request)
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash
    )
    
    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)
    
    org_name = org.name if org else "None"
    logger.info(f"[TokenAudit] Login success: user={user.id}, phone={user.phone}, org={org_name}, method=captcha, ip={client_ip}")
    
    # Track user activity
    track_user_activity(user, 'login', {'method': 'captcha', 'org': org_name}, http_request)
    
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
            "role": get_user_role(user)
        }
    }


@router.post("/login_sms")
async def login_with_sms(
    request: LoginWithSMSRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
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
    # Find user first (use cache with SQLite fallback)
    user = user_cache.get_by_phone(request.phone)
    
    if not user:
        error_msg = Messages.error("phone_not_registered_login", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )
    
    # Get organization and check status BEFORE consuming code (use cache)
    org = org_cache.get_by_id(user.organization_id) if user.organization_id else None
    
    # Check organization status
    if org:
        is_active = org.is_active if hasattr(org, 'is_active') else True
        if not is_active:
            logger.warning(f"SMS login blocked: Organization {org.code} is locked")
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        if hasattr(org, 'expires_at') and org.expires_at:
            if org.expires_at < datetime.now(timezone.utc):
                logger.warning(f"SMS login blocked: Organization {org.code} expired")
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg
                )
    
    # All validations passed - now consume the SMS code
    _verify_and_consume_sms_code(
        request.phone,
        request.sms_code,
        "login",
        db,
        lang
    )
    
    # Reset any failed attempts (SMS login is verified)
    reset_failed_attempts(user, db)
    
    # Session management: Invalidate old sessions before creating new one
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    old_token_hash = session_manager.get_session_token(user.id)
    session_manager.invalidate_user_sessions(user.id, old_token_hash=old_token_hash, ip_address=client_ip)
    
    # Generate JWT access token
    token = create_access_token(user)
    
    # Generate refresh token
    refresh_token_value, refresh_token_hash = create_refresh_token(user.id)
    
    # Store access token session in Redis
    session_manager.store_session(user.id, token)
    
    # Store refresh token with device binding
    user_agent = http_request.headers.get("User-Agent", "")
    device_hash = compute_device_hash(http_request)
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash
    )
    
    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, http_request)
    
    # Use cache for org lookup (with SQLite fallback)
    org = org_cache.get_by_id(user.organization_id) if user.organization_id else None
    if not org and user.organization_id:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        if org:
            db.expunge(org)
            org_cache.cache_org(org)
    org_name = org.name if org else "None"
    
    logger.info(f"[TokenAudit] Login success: user={user.id}, phone={user.phone}, org={org_name}, method=sms, ip={client_ip}")
    
    # Track user activity
    track_user_activity(user, 'login', {'method': 'sms', 'org': org_name}, http_request)
    
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
            "role": get_user_role(user)
        }
    }


@router.post("/demo/verify")
async def verify_demo(
    passkey_request: DemoPasskeyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """
    Verify demo/bayi passkey and return JWT token
    
    Demo mode and Bayi mode allow access with a 6-digit passkey.
    Supports both regular demo access and admin demo access.
    In bayi mode, creates bayi-specific users.
    """
    # Enhanced logging for debugging (without revealing actual passkeys)
    from utils.auth import DEMO_PASSKEY
    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(DEMO_PASSKEY)
    logger.info(f"Passkey verification attempt ({AUTH_MODE} mode) - Received: {received_length} chars, Expected: {expected_length} chars")
    
    if not verify_demo_passkey(passkey_request.passkey):
        logger.warning(f"Passkey verification failed - Check .env file for whitespace in DEMO_PASSKEY or ADMIN_DEMO_PASSKEY")
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg
        )
    
    # Check if this is admin demo access
    is_admin_access = is_admin_demo_passkey(passkey_request.passkey)
    
    # Determine user phone and name based on mode
    if AUTH_MODE == "bayi":
        user_phone = "bayi-admin@system.com" if is_admin_access else "bayi@system.com"
        user_name = "Bayi Admin" if is_admin_access else "Bayi User"
    else:
        user_phone = "demo-admin@system.com" if is_admin_access else "demo@system.com"
        user_name = "Demo Admin" if is_admin_access else "Demo User"
    
    # Get or create user (use cache with SQLite fallback)
    auth_user = user_cache.get_by_phone(user_phone)
    
    if not auth_user:
        # Get or create organization based on mode
        if AUTH_MODE == "bayi":
            org = db.query(Organization).filter(
                Organization.code == BAYI_DEFAULT_ORG_CODE
            ).first()
            if not org:
                # Create bayi organization if it doesn't exist
                org = Organization(
                    code=BAYI_DEFAULT_ORG_CODE,
                    name="Bayi School",
                    invitation_code="BAYI2024",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(org)
                db.commit()
                db.refresh(org)
                logger.info(f"Created bayi organization: {BAYI_DEFAULT_ORG_CODE}")
                # Cache the newly created org (non-blocking)
                try:
                    org_cache.cache_org(org)
                except Exception as e:
                    logger.warning(f"Failed to cache bayi org: {e}")
        else:
            # Demo mode: use first available organization
            org = db.query(Organization).first()
            if not org:
                error_msg = Messages.error("no_organizations_available", "en")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
        
        try:
            # Use a short, simple password (bcrypt max is 72 bytes)
            auth_user = User(
                phone=user_phone,
                password_hash=hash_password("passkey-no-pwd"),
                name=user_name,
                organization_id=org.id,
                created_at=datetime.now(timezone.utc)
            )
            db.add(auth_user)
            db.commit()
            db.refresh(auth_user)
            logger.info(f"Created new {AUTH_MODE} user: {user_phone}")
            
            # Cache the newly created user and org (non-blocking)
            try:
                user_cache.cache_user(auth_user)
                if org:
                    org_cache.cache_org(org)
            except Exception as e:
                logger.warning(f"Failed to cache demo user/org: {e}")
        except Exception as e:
            # If creation fails, try to rollback and check if user was somehow created
            db.rollback()
            logger.error(f"Failed to create {AUTH_MODE} user: {e}")
            
            # Try to get the user again in case it was created by another request (use cache)
            auth_user = user_cache.get_by_phone(user_phone)
            if not auth_user:
                error_msg = Messages.error("user_creation_failed", "en", str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
    
    # Session management: Invalidate old sessions before creating new one
    session_manager = get_session_manager()
    client_ip = get_client_ip(request)
    old_token_hash = session_manager.get_session_token(auth_user.id)
    session_manager.invalidate_user_sessions(auth_user.id, old_token_hash=old_token_hash, ip_address=client_ip)
    
    # Generate JWT access token
    token = create_access_token(auth_user)
    
    # Generate refresh token
    client_ip = get_client_ip(request)
    refresh_token_value, refresh_token_hash = create_refresh_token(auth_user.id)
    
    # Store access token session in Redis
    session_manager.store_session(auth_user.id, token)
    
    # Store refresh token with device binding
    user_agent = request.headers.get("User-Agent", "")
    device_hash = compute_device_hash(request)
    refresh_manager = get_refresh_token_manager()
    refresh_manager.store_refresh_token(
        user_id=auth_user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash
    )
    
    # Set cookies (both access and refresh tokens)
    set_auth_cookies(response, token, refresh_token_value, request)
    
    log_msg = f"[TokenAudit] Login success: user={auth_user.id}, mode={AUTH_MODE}, admin={is_admin_access}, ip={client_ip}"
    logger.info(log_msg)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        "user": {
            "id": auth_user.id,
            "phone": auth_user.phone,
            "name": auth_user.name,
            "role": "admin" if is_admin_access else "user"
        }
    }


@router.post("/public-dashboard/verify")
async def verify_public_dashboard(
    passkey_request: DemoPasskeyRequest,
    request: Request,
    response: Response,
    lang: str = Depends(get_language_dependency)
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
        window_seconds=15 * 60  # 15 minutes
    )
    
    if not is_allowed:
        logger.warning(f"Dashboard passkey rate limit exceeded for IP {client_ip} ({attempt_count} attempts)")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or Messages.error("too_many_login_attempts", lang, 15)
        )
    
    # Enhanced logging for debugging (without revealing actual passkeys)
    from utils.auth import PUBLIC_DASHBOARD_PASSKEY
    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(PUBLIC_DASHBOARD_PASSKEY)
    logger.info(f"Dashboard passkey verification attempt - Received: {received_length} chars, Expected: {expected_length} chars")
    
    if not verify_dashboard_passkey(passkey_request.passkey):
        logger.warning(f"Dashboard passkey verification failed for IP {client_ip}")
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg
        )
    
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
        max_age=24 * 60 * 60  # 24 hours
    )
    
    logger.info(f"Dashboard access granted for IP {client_ip}")
    
    return {
        "success": True,
        "message": "Access granted",
        "dashboard_token": dashboard_token
    }

