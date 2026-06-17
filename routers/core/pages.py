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

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.domain.auth import Organization, User
from routers.auth.helpers import issue_access_token_with_vpn_geo
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from services.redis.redis_bayi_token import get_bayi_token_tracker
from services.redis.session.redis_session_manager import get_session_manager
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.auth import (
    AUTH_MODE,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    BAYI_DEFAULT_ORG_ID,
    BAYI_SSO_DEFAULT_DISPLAY_NAME,
    compute_device_hash,
    decrypt_bayi_token,
    get_client_ip,
    hash_password,
    is_https,
    validate_bayi_token_body,
)
from utils.auth.org_subscription import ensure_org_subscription_current
from utils.db.session_open import system_rls_session

_issue_bayi_access_token = issue_access_token_with_vpn_geo

logger = logging.getLogger(__name__)

# Where to send users when Bayi SSO cannot complete (stale/replay/decrypt/org errors)
_BAYI_SSO_FALLBACK_REDIRECT = "/auth"

# Initialize router
router = APIRouter(tags=["Authentication"])


# ============================================================================
# BAYI MODE AUTHENTICATION
# ============================================================================


@router.get("/loginByXz")
async def login_by_xz(request: Request, token: Optional[str] = None):
    """
    Bayi mode: passwordless SSO via encrypted vendor token.

    The client must pass ``?token=`` (AES payload from 小致). After decrypt and
    validation (``from``, freshness, ``userId``), the user is found or created
    under the configured Bayi org (``BAYI_DEFAULT_ORG_ID`` row if set, otherwise
    ``BAYI_DEFAULT_ORG_CODE`` with optional auto-create) and receives a JWT cookie.

    On failure (missing or invalid token, org locked, etc.): redirects to ``/auth``.

    Note: Uses manual session management to release DB connections immediately
    after authentication, before returning the redirect response.
    """
    try:
        # Verify AUTH_MODE is set to bayi
        if AUTH_MODE != "bayi":
            logger.warning(
                "/loginByXz accessed but AUTH_MODE is '%s', not 'bayi' - redirecting to %s",
                AUTH_MODE,
                _BAYI_SSO_FALLBACK_REDIRECT,
            )
            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

        # Extract client IP
        client_ip = get_client_ip(request)
        logger.info("Bayi authentication attempt from IP: %s", client_ip)

        if not token:
            logger.warning(
                "Bayi SSO: no token provided from IP %s - redirecting to %s",
                client_ip,
                _BAYI_SSO_FALLBACK_REDIRECT,
            )
            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

        # Log token receipt (without exposing full token in logs)
        token_preview = token[:20] + "..." if len(token) > 20 else token
        logger.info(
            "Bayi token authentication attempt - IP: %s, token length: %s, preview: %s",
            client_ip,
            len(token),
            token_preview,
        )

        # Rate limiting: Prevent brute force attacks (10 attempts per 5 minutes per IP)
        try:
            token_tracker = get_bayi_token_tracker()
            is_allowed, attempt_count, _ = await token_tracker.check_rate_limit(client_ip)
            if not is_allowed:
                logger.warning(
                    "Bayi token rate limit exceeded for IP %s: %s attempts",
                    client_ip,
                    attempt_count,
                )
                return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
        except BACKGROUND_INFRA_ERRORS as e:
            logger.warning("Rate limit check failed (allowing request): %s", e)
            # Fail-open: if rate limiting fails, allow request (backward compatibility)

        # Replay attack prevention: Check if token was already used
        try:
            token_tracker = get_bayi_token_tracker()
            if await token_tracker.is_token_used(token):
                logger.warning(
                    "Bayi token replay attack detected for IP %s - token already used",
                    client_ip,
                )
                return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
        except BACKGROUND_INFRA_ERRORS as e:
            logger.debug("Token usage check failed (allowing request): %s", e)
            # Fail-open: if check fails, allow request (backward compatibility)

        # Decrypt token (no DB needed for this)
        try:
            logger.info(
                "Attempting to decrypt token with key length: %s",
                len(BAYI_DECRYPTION_KEY),
            )
            body = decrypt_bayi_token(token, BAYI_DECRYPTION_KEY)
            logger.info(
                "Bayi token decrypted successfully - body keys: %s",
                list(body.keys()),
            )
            logger.debug("Bayi token decrypted payload: %s", body)
        except ValueError as e:
            logger.error(
                "Bayi token decryption failed: %s - redirecting to %s",
                e,
                _BAYI_SSO_FALLBACK_REDIRECT,
                exc_info=True,
            )
            # Invalid token: fallback to standard auth UI
            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
        except BACKGROUND_INFRA_ERRORS as e:
            logger.error(
                "Unexpected error during token decryption: %s - redirecting to %s",
                e,
                _BAYI_SSO_FALLBACK_REDIRECT,
                exc_info=True,
            )
            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

        # Validate token body (no DB needed for this)
        logger.info(
            "Validating token body - from: %s, timestamp: %s, userId present: %s",
            body.get("from"),
            body.get("timestamp"),
            body.get("userId") is not None,
        )
        validation_result = validate_bayi_token_body(body)
        if not validation_result:
            logger.error(
                "Bayi token validation failed - body: %s, from field: '%s', timestamp: %s - redirecting to %s",
                body,
                body.get("from"),
                body.get("timestamp"),
                _BAYI_SSO_FALLBACK_REDIRECT,
            )
            # Cache invalid result (performance optimization)
            try:
                token_tracker = get_bayi_token_tracker()
                await token_tracker.cache_token_validation(token, False)
            except BACKGROUND_INFRA_ERRORS as e:
                logger.debug("Failed to cache invalid token: %s", e)
            # Invalid or expired token: fallback to standard auth UI
            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

        logger.info("Token validation passed - proceeding with user creation/retrieval")

        # Mark token as used (replay attack prevention) and cache validation result
        try:
            token_tracker = get_bayi_token_tracker()
            await token_tracker.mark_token_used(token)
            await token_tracker.cache_token_validation(token, True)
            await token_tracker.clear_rate_limit(client_ip)
        except DATABASE_ERRORS as e:
            logger.debug("Failed to mark token as used/cache result: %s", e)
            # Non-critical - continue with authentication

        user_phone = str(body["userId"]).strip()

        async with system_rls_session() as db:
            org: Optional[Organization] = None

            if BAYI_DEFAULT_ORG_ID is not None:
                result = await db.execute(select(Organization).where(Organization.id == BAYI_DEFAULT_ORG_ID))
                org = result.scalar_one_or_none()
                if not org:
                    logger.error(
                        "Bayi SSO: organization id %s (BAYI_DEFAULT_ORG_ID) not found",
                        BAYI_DEFAULT_ORG_ID,
                    )
                    return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
            else:
                result = await db.execute(select(Organization).where(Organization.code == BAYI_DEFAULT_ORG_CODE))
                org = result.scalar_one_or_none()

                if not org:
                    try:
                        org = Organization(
                            code=BAYI_DEFAULT_ORG_CODE,
                            name="Bayi School",
                            invitation_code="BAYI2024",
                            created_at=datetime.now(UTC),
                        )
                        db.add(org)
                        await db.commit()
                        await db.refresh(org)
                        logger.info("Created bayi organization: %s", BAYI_DEFAULT_ORG_CODE)
                        try:
                            await org_cache.cache_org(org)
                        except DATABASE_ERRORS as e:
                            logger.warning("Failed to cache bayi org: %s", e)
                    except IntegrityError:
                        await db.rollback()
                        result = await db.execute(
                            select(Organization).where(Organization.code == BAYI_DEFAULT_ORG_CODE)
                        )
                        org = result.scalar_one_or_none()
                        if not org:
                            logger.error("Failed to create or retrieve bayi organization after race")
                            return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
                        try:
                            await org_cache.cache_org(org)
                        except DATABASE_ERRORS as cache_err:
                            logger.debug("Failed to cache org after race: %s", cache_err)
                    except DATABASE_ERRORS:
                        await db.rollback()
                        raise

            if org is None:
                logger.error("Bayi SSO: organization resolution failed unexpectedly")
                return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

            is_active = cast(bool, getattr(org, "is_active", True))
            if not is_active:
                logger.warning("Bayi SSO blocked: Organization %s is locked", org.code)
                return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)

            org = await ensure_org_subscription_current(org) or org

            result = await db.execute(select(User).where(User.phone == user_phone))
            bayi_user = result.scalar_one_or_none()

            if not bayi_user:
                try:
                    bayi_user = User(
                        phone=user_phone,
                        password_hash=hash_password("bayi-no-pwd"),
                        name=BAYI_SSO_DEFAULT_DISPLAY_NAME,
                        organization_id=org.id,
                        created_at=datetime.now(UTC),
                    )
                    db.add(bayi_user)
                    await db.commit()
                    await db.refresh(bayi_user)
                    logger.info("Created bayi user: %s", user_phone)
                    try:
                        await user_cache.cache_user(bayi_user)
                    except REDIS_ERRORS as e:
                        logger.warning("Failed to cache bayi user: %s", e)
                except REDIS_ERRORS as e:
                    await db.rollback()
                    logger.error("Failed to create bayi user: %s", e)
                    result = await db.execute(select(User).where(User.phone == user_phone))
                    bayi_user = result.scalar_one_or_none()
                    if not bayi_user:
                        logger.error("Failed to create bayi user after retry: %s", e)
                        return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)
                    try:
                        await user_cache.cache_user(bayi_user)
                    except REDIS_ERRORS as cache_err:
                        logger.debug(
                            "Failed to cache user after error recovery: %s",
                            cache_err,
                        )

            session_manager = get_session_manager()
            old_token_hash = await session_manager.get_session_token(bayi_user.id)
            await session_manager.invalidate_user_sessions(
                bayi_user.id,
                old_token_hash=old_token_hash,
                ip_address=client_ip,
            )

            jwt_token = await _issue_bayi_access_token(bayi_user, request)
            device_hash = compute_device_hash(request)
            await session_manager.store_session(bayi_user.id, jwt_token, device_hash=device_hash)

            logger.info("Bayi mode authentication successful: %s", user_phone)

        # Valid token: redirect to app home with cookie set on redirect response
        redirect_response = RedirectResponse(url="/", status_code=303)
        redirect_response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            secure=is_https(request),  # SECURITY: Auto-detect HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        # Set flag cookie to indicate new login session (for AI disclaimer notification)
        redirect_response.set_cookie(
            key="show_ai_disclaimer",
            value="true",
            httponly=False,  # Allow JavaScript to read it
            secure=is_https(request),
            samesite="lax",
            max_age=60 * 60,  # 1 hour (should be cleared after showing notification)
        )
        return redirect_response

    except BACKGROUND_INFRA_ERRORS as e:
        # Any other error: redirect to fallback auth route
        logger.error(
            "Bayi authentication error: %s - redirecting to %s",
            e,
            _BAYI_SSO_FALLBACK_REDIRECT,
            exc_info=True,
        )
        return RedirectResponse(url=_BAYI_SSO_FALLBACK_REDIRECT, status_code=303)


# ============================================================================
# STATIC ASSETS
# ============================================================================


@router.get("/favicon.ico")
def favicon():
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
    if vue_favicon_svg.exists():
        return FileResponse(vue_favicon_svg, media_type="image/svg+xml")
    if legacy_favicon.exists():
        return FileResponse(legacy_favicon, media_type="image/svg+xml")

    # Return 404 if favicon doesn't exist
    raise HTTPException(status_code=404, detail="Favicon not found")


# Only log from main worker to avoid duplicate messages
if os.getenv("UVICORN_WORKER_ID") is None or os.getenv("UVICORN_WORKER_ID") == "0":
    logger.debug("Authentication routes initialized: 2 routes registered (/loginByXz, /favicon.ico)")
