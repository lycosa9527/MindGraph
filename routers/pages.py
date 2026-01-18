"""
MindGraph Authentication & Utility Routes
==========================================

FastAPI routes for authentication endpoints and utility functions.
Page rendering is handled by Vue SPA (v5.0.0+).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from config.database import SessionLocal
from models.auth import User, Organization
from services.redis.redis_session_manager import get_session_manager
from utils.auth import (
    AUTH_MODE,
    get_client_ip,
    is_https,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    decrypt_bayi_token,
    validate_bayi_token_body,
    is_ip_whitelisted,
    create_access_token,
    hash_password,
    compute_device_hash
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["Authentication"])


# ============================================================================
# BAYI MODE AUTHENTICATION
# ============================================================================

@router.get("/loginByXz")
async def login_by_xz(
    request: Request,
    token: Optional[str] = None
):
    """
    Bayi mode authentication endpoint

    Authentication methods (in priority order):
    1. IP Whitelist: If client IP is whitelisted, grant immediate access
       - No token required
       - No session limits
       - Simple IP check → grant access
    2. Token Authentication: If IP not whitelisted, require encrypted token
       - Token must be valid and within 5 minutes
       - Full decryption and validation required

    URL formats:
    - IP Whitelist: /loginByXz (no token parameter)
    - Token Auth: /loginByXz?token=...

    Behavior:
    - If IP whitelisted: Grant access immediately (no token needed)
    - If token valid: Redirects to /editor with JWT token set as cookie
    - If both fail: Redirects to /demo (demo passkey page)

    Note: Uses manual session management to release DB connections immediately
    after authentication, before returning the redirect response.
    """
    try:
        # Verify AUTH_MODE is set to bayi
        if AUTH_MODE != "bayi":
            logger.warning(f"/loginByXz accessed but AUTH_MODE is '{AUTH_MODE}', not 'bayi' - redirecting to /demo")
            return RedirectResponse(url="/demo", status_code=303)

        # Extract client IP
        client_ip = get_client_ip(request)
        logger.info(f"Bayi authentication attempt from IP: {client_ip}")

        # Priority 1: Check IP whitelist (skip token if whitelisted)
        if is_ip_whitelisted(client_ip):
            # IP is whitelisted - grant immediate access, no token needed
            logger.info(f"IP {client_ip} is whitelisted, granting immediate access (skipping token verification)")

            # Use manual session management - close immediately after DB operations
            db = SessionLocal()
            try:
                # Get or create organization (same as token flow)
                org = db.query(Organization).filter(
                    Organization.code == BAYI_DEFAULT_ORG_CODE
                ).first()

                if not org:
                    try:
                        org = Organization(
                            code=BAYI_DEFAULT_ORG_CODE,
                            name="Bayi School",
                            invitation_code="BAYI2024",
                            created_at=datetime.utcnow()
                        )
                        db.add(org)
                        db.commit()
                        db.refresh(org)
                        logger.info(f"Created bayi organization: {BAYI_DEFAULT_ORG_CODE}")
                        # Cache the newly created org (non-blocking)
                        try:
                            from services.redis.redis_org_cache import org_cache
                            org_cache.cache_org(org)
                        except Exception as e:
                            logger.warning(f"Failed to cache bayi org: {e}")
                    except IntegrityError as e:
                        # Organization created by another request (race condition)
                        db.rollback()
                        logger.debug(f"Organization creation race condition (expected): {e}")
                        org = db.query(Organization).filter(
                            Organization.code == BAYI_DEFAULT_ORG_CODE
                        ).first()
                        if not org:
                            logger.error("Failed to create or retrieve bayi organization")
                            return RedirectResponse(url="/demo", status_code=303)
                        # Cache the org that was created by another request (race condition)
                        try:
                            from services.redis.redis_org_cache import org_cache
                            org_cache.cache_org(org)
                        except Exception as e:
                            logger.debug(f"Failed to cache org after race condition: {e}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to create bayi organization: {e}")
                        return RedirectResponse(url="/demo", status_code=303)

                # Check organization status (locked or expired) - CRITICAL SECURITY CHECK
                if org:
                    # Check if organization is locked
                    is_active = org.is_active if hasattr(org, 'is_active') else True
                    if not is_active:
                        logger.warning(f"IP whitelist blocked: Organization {org.code} is locked")
                        return RedirectResponse(url="/demo", status_code=303)

                    # Check if organization subscription has expired
                    if hasattr(org, 'expires_at') and org.expires_at:
                        if org.expires_at < datetime.utcnow():
                            logger.warning(f"IP whitelist blocked: Organization {org.code} expired on {org.expires_at}")
                            return RedirectResponse(url="/demo", status_code=303)

                # Use single shared user for all IP whitelist authentications
                user_phone = "bayi-ip@system.com"
                user_name = "Bayi IP User"

                bayi_user = db.query(User).filter(User.phone == user_phone).first()

                if not bayi_user:
                    try:
                        bayi_user = User(
                            phone=user_phone,
                            password_hash=hash_password("bayi-no-pwd"),
                            name=user_name,
                            organization_id=org.id,
                            created_at=datetime.utcnow()
                        )
                        db.add(bayi_user)
                        db.commit()
                        db.refresh(bayi_user)
                        logger.info(f"Created shared bayi IP user: {user_phone}")
                        # Cache the newly created user (non-blocking)
                        try:
                            from services.redis.redis_user_cache import user_cache
                            user_cache.cache_user(bayi_user)
                        except Exception as e:
                            logger.warning(f"Failed to cache bayi user: {e}")
                    except IntegrityError as e:
                        # Handle race condition: user created by another request
                        db.rollback()
                        logger.debug(f"User creation race condition (expected): {e}")
                        bayi_user = db.query(User).filter(User.phone == user_phone).first()
                        if not bayi_user:
                            logger.error("Failed to create or retrieve bayi IP user after race condition")
                            return RedirectResponse(url="/demo", status_code=303)
                        # Cache the user that was created by another request (race condition)
                        try:
                            from services.redis.redis_user_cache import user_cache
                            user_cache.cache_user(bayi_user)
                        except Exception as e:
                            logger.debug(f"Failed to cache user after race condition: {e}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to create bayi IP user: {e}")
                        bayi_user = db.query(User).filter(User.phone == user_phone).first()
                        if not bayi_user:
                            return RedirectResponse(url="/demo", status_code=303)
                        # Cache the user if it exists after error recovery
                        if bayi_user:
                            try:
                                from services.redis.redis_user_cache import user_cache
                                user_cache.cache_user(bayi_user)
                            except Exception as cache_err:
                                logger.debug(f"Failed to cache user after error recovery: {cache_err}")

                # Session management: For IP whitelist users, allow multiple concurrent sessions
                # (50 teachers can all be logged in simultaneously from whitelisted IP)
                # We don't invalidate old sessions for shared bayi-ip@system.com account
                session_manager = get_session_manager()

                # Generate JWT token (user object is still valid after expunge)
                jwt_token = create_access_token(bayi_user)

                # Compute device hash for session tracking
                device_hash = compute_device_hash(request)

                # Store new session in Redis (allow_multiple=True for shared account)
                # This allows multiple teachers to use the system simultaneously
                session_manager.store_session(bayi_user.id, jwt_token, device_hash=device_hash, allow_multiple=True)

                logger.info(f"Bayi IP whitelist authentication successful: {client_ip}")
            finally:
                db.close()  # ✅ Connection released BEFORE redirect

            # Redirect to editor with cookie
            redirect_response = RedirectResponse(url="/editor", status_code=303)
            redirect_response.set_cookie(
                key="access_token",
                value=jwt_token,
                httponly=True,
                secure=is_https(request),  # SECURITY: Auto-detect HTTPS
                samesite="lax",
                max_age=7 * 24 * 60 * 60  # 7 days
            )
            # Set flag cookie to indicate new login session (for AI disclaimer notification)
            redirect_response.set_cookie(
                key="show_ai_disclaimer",
                value="true",
                httponly=False,  # Allow JavaScript to read it
                secure=is_https(request),
                samesite="lax",
                max_age=60 * 60  # 1 hour (should be cleared after showing notification)
            )
            return redirect_response

        # Priority 2: Token authentication (existing flow)
        if not token:
            logger.warning(f"IP {client_ip} not whitelisted and no token provided - redirecting to /demo")
            return RedirectResponse(url="/demo", status_code=303)

        # Log token receipt (without exposing full token in logs)
        token_preview = token[:20] + "..." if len(token) > 20 else token
        logger.info(f"Bayi token authentication attempt - IP: {client_ip}, token length: {len(token)}, preview: {token_preview}")

        # Rate limiting: Prevent brute force attacks (10 attempts per 5 minutes per IP)
        try:
            from services.redis.redis_bayi_token import get_bayi_token_tracker
            token_tracker = get_bayi_token_tracker()
            is_allowed, attempt_count, error_msg = token_tracker.check_rate_limit(client_ip)
            if not is_allowed:
                logger.warning(f"Bayi token rate limit exceeded for IP {client_ip}: {attempt_count} attempts")
                return RedirectResponse(url="/demo", status_code=303)
        except Exception as e:
            logger.warning(f"Rate limit check failed (allowing request): {e}")
            # Fail-open: if rate limiting fails, allow request (backward compatibility)

        # Replay attack prevention: Check if token was already used
        try:
            from services.redis.redis_bayi_token import get_bayi_token_tracker
            token_tracker = get_bayi_token_tracker()
            if token_tracker.is_token_used(token):
                logger.warning(f"Bayi token replay attack detected for IP {client_ip} - token already used")
                return RedirectResponse(url="/demo", status_code=303)
        except Exception as e:
            logger.debug(f"Token usage check failed (allowing request): {e}")
            # Fail-open: if check fails, allow request (backward compatibility)

        # Decrypt token (no DB needed for this)
        try:
            logger.info(f"Attempting to decrypt token with key length: {len(BAYI_DECRYPTION_KEY)}")
            body = decrypt_bayi_token(token, BAYI_DECRYPTION_KEY)
            logger.info(f"Bayi token decrypted successfully - body keys: {list(body.keys())}, body content: {body}")
        except ValueError as e:
            logger.error(f"Bayi token decryption failed: {e} - redirecting to /demo", exc_info=True)
            # Invalid token: redirect to demo passkey page
            return RedirectResponse(url="/demo", status_code=303)
        except Exception as e:
            logger.error(f"Unexpected error during token decryption: {e} - redirecting to /demo", exc_info=True)
            return RedirectResponse(url="/demo", status_code=303)

        # Validate token body (no DB needed for this)
        logger.info(f"Validating token body - from: {body.get('from')}, timestamp: {body.get('timestamp')}")
        validation_result = validate_bayi_token_body(body)
        if not validation_result:
            logger.error(f"Bayi token validation failed - body: {body}, from field: '{body.get('from')}', timestamp: {body.get('timestamp')} - redirecting to /demo")
            # Cache invalid result (performance optimization)
            try:
                from services.redis.redis_bayi_token import get_bayi_token_tracker
                token_tracker = get_bayi_token_tracker()
                token_tracker.cache_token_validation(token, False)
            except Exception as e:
                logger.debug(f"Failed to cache invalid token: {e}")
            # Invalid or expired token: redirect to demo passkey page
            return RedirectResponse(url="/demo", status_code=303)

        logger.info("Token validation passed - proceeding with user creation/retrieval")

        # Mark token as used (replay attack prevention) and cache validation result
        try:
            from services.redis.redis_bayi_token import get_bayi_token_tracker
            token_tracker = get_bayi_token_tracker()
            token_tracker.mark_token_used(token)  # Prevent replay attacks
            token_tracker.cache_token_validation(token, True)  # Cache valid result
            token_tracker.clear_rate_limit(client_ip)  # Clear rate limit on success (better UX)
        except Exception as e:
            logger.debug(f"Failed to mark token as used/cache result: {e}")
            # Non-critical - continue with authentication

        # Use manual session management - close immediately after DB operations
        db = SessionLocal()
        try:
            # Get or create organization
            org = db.query(Organization).filter(
                Organization.code == BAYI_DEFAULT_ORG_CODE
            ).first()

            if not org:
                # Create bayi organization if it doesn't exist
                org = Organization(
                    code=BAYI_DEFAULT_ORG_CODE,
                    name="Bayi School",
                    invitation_code="BAYI2024",
                    created_at=datetime.utcnow()
                )
                db.add(org)
                db.commit()
                db.refresh(org)
                logger.info(f"Created bayi organization: {BAYI_DEFAULT_ORG_CODE}")
                # Cache the newly created org (non-blocking)
                try:
                    from services.redis.redis_org_cache import org_cache
                    org_cache.cache_org(org)
                except Exception as e:
                    logger.warning(f"Failed to cache bayi org: {e}")

            # Extract user info from token body (if available)
            # Default to a generic bayi user if not specified
            user_phone = body.get('phone') or body.get('user') or "bayi@system.com"
            user_name = body.get('name') or "Bayi User"

            # Get or create user
            bayi_user = db.query(User).filter(User.phone == user_phone).first()

            if not bayi_user:
                try:
                    bayi_user = User(
                        phone=user_phone,
                        password_hash=hash_password("bayi-no-pwd"),
                        name=user_name,
                        organization_id=org.id,
                        created_at=datetime.utcnow()
                    )
                    db.add(bayi_user)
                    db.commit()
                    db.refresh(bayi_user)
                    logger.info(f"Created bayi user: {user_phone}")
                    # Cache the newly created user (non-blocking)
                    try:
                        from services.redis.redis_user_cache import user_cache
                        user_cache.cache_user(bayi_user)
                    except Exception as e:
                        logger.warning(f"Failed to cache bayi user: {e}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to create bayi user: {e}")
                    # Try to get user again in case it was created by another request
                    bayi_user = db.query(User).filter(User.phone == user_phone).first()
                    if not bayi_user:
                        logger.error(f"Failed to create bayi user after retry: {e}")
                        return RedirectResponse(url="/demo", status_code=303)
                    else:
                        # Cache the user if it exists after error recovery
                        try:
                            from services.redis.redis_user_cache import user_cache
                            user_cache.cache_user(bayi_user)
                        except Exception as cache_err:
                            logger.debug(f"Failed to cache user after error recovery: {cache_err}")

            # Session management: Invalidate old sessions before creating new one
            session_manager = get_session_manager()
            old_token_hash = session_manager.get_session_token(bayi_user.id)
            session_manager.invalidate_user_sessions(bayi_user.id, old_token_hash=old_token_hash, ip_address=client_ip)

            # Generate JWT token (user object is still valid after session close)
            jwt_token = create_access_token(bayi_user)

            # Compute device hash for session tracking
            device_hash = compute_device_hash(request)

            # Store new session in Redis
            session_manager.store_session(bayi_user.id, jwt_token, device_hash=device_hash)

            logger.info(f"Bayi mode authentication successful: {user_phone}")
        finally:
            db.close()  # ✅ Connection released BEFORE redirect

        # Valid token: redirect to editor with cookie set on redirect response
        redirect_response = RedirectResponse(url="/editor", status_code=303)
        redirect_response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            secure=is_https(request),  # SECURITY: Auto-detect HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        # Set flag cookie to indicate new login session (for AI disclaimer notification)
        redirect_response.set_cookie(
            key="show_ai_disclaimer",
            value="true",
            httponly=False,  # Allow JavaScript to read it
            secure=is_https(request),
            samesite="lax",
            max_age=60 * 60  # 1 hour (should be cleared after showing notification)
        )
        return redirect_response

    except Exception as e:
        # Any other error: redirect to demo passkey page
        logger.error(f"Bayi authentication error: {e} - redirecting to /demo", exc_info=True)
        return RedirectResponse(url="/demo", status_code=303)


# ============================================================================
# STATIC ASSETS
# ============================================================================

@router.get("/favicon.ico")
async def favicon():
    """
    Serve favicon.ico

    Checks multiple locations:
    1. Vue SPA dist folder (frontend/dist/favicon.ico or .svg)
    2. Legacy static folder (static/favicon.svg)
    """
    # Check Vue SPA dist folder first
    vue_favicon_ico = Path("frontend/dist/favicon.ico")
    vue_favicon_svg = Path("frontend/dist/favicon.svg")
    legacy_favicon = Path("static/favicon.svg")

    if vue_favicon_ico.exists():
        return FileResponse(vue_favicon_ico, media_type="image/x-icon")
    elif vue_favicon_svg.exists():
        return FileResponse(vue_favicon_svg, media_type="image/svg+xml")
    elif legacy_favicon.exists():
        return FileResponse(legacy_favicon, media_type="image/svg+xml")

    # Return 404 if favicon doesn't exist
    raise HTTPException(status_code=404, detail="Favicon not found")


# Only log from main worker to avoid duplicate messages
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Authentication routes initialized: 2 routes registered (/loginByXz, /favicon.ico)")
