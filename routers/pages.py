"""
MindGraph Template Rendering Routes
====================================

FastAPI routes for serving HTML templates.

All template routes are async for consistency, though they perform minimal I/O.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Response, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import config
from config.database import get_db, SessionLocal

def get_app_version():
    """Read version from VERSION file for .mg export metadata"""
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"
from utils.auth import (
    AUTH_MODE, 
    get_user_from_cookie, 
    is_admin,
    get_client_ip,
    is_https,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    ENTERPRISE_DEFAULT_USER_PHONE,
    decrypt_bayi_token,
    validate_bayi_token_body,
    is_ip_whitelisted,
    create_access_token,
    hash_password
)
from services.redis_session_manager import get_session_manager
from models.auth import User, Organization
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["Pages"])

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# ============================================================================
# TEMPLATE ROUTES (11 routes from web_pages.py)
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page - redirects based on AUTH_MODE"""
    try:
        # Standard mode: redirect to /auth for login/register
        if AUTH_MODE == "standard":
            auth_cookie = request.cookies.get("access_token")
            if auth_cookie:
                # Use manual session management - close immediately after auth check
                db = SessionLocal()
                try:
                    user = get_user_from_cookie(auth_cookie, db)
                    if user:
                        # Detach user from session if it's attached (cache users are already detached)
                        if user in db:
                            db.expunge(user)
                        # Already authenticated, go to editor
                        logger.debug("Standard mode: Authenticated user, redirecting / to /editor")
                        return RedirectResponse(url="/editor", status_code=303)
                    else:
                        # Token is invalid or expired - clear cookie before redirecting to /auth
                        logger.debug("Invalid or expired token cookie detected on /, clearing cookie")
                        response = RedirectResponse(url="/auth", status_code=303)
                        response.delete_cookie(key="access_token", httponly=True, samesite="lax")
                        return response
                finally:
                    db.close()  # ✅ Connection released BEFORE redirect
            
            # Not authenticated, go to auth page
            logger.debug("Standard mode: Redirecting / to /auth")
            return RedirectResponse(url="/auth", status_code=303)
        
        # Demo mode: redirect to /demo
        elif AUTH_MODE == "demo":
            logger.debug("Demo mode: Redirecting / to /demo")
            return RedirectResponse(url="/demo", status_code=303)
        
        # Enterprise mode: go directly to editor (no auth)
        elif AUTH_MODE == "enterprise":
            logger.debug("Enterprise mode: Redirecting / to /editor")
            return RedirectResponse(url="/editor", status_code=303)
        
        # Bayi mode: go directly to editor (token-based auth via /loginByXz)
        elif AUTH_MODE == "bayi":
            logger.debug("Bayi mode: Redirecting / to /editor")
            return RedirectResponse(url="/editor", status_code=303)
        
        # Fallback: show API docs (index.html)
        else:
            logger.warning(f"Unknown AUTH_MODE: {AUTH_MODE}, serving index.html")
            return templates.TemplateResponse("index.html", {"request": request})
            
    except Exception as e:
        logger.error(f"/ route failed: {e}", exc_info=True)
        raise

@router.get("/debug", response_class=HTMLResponse)
async def debug(request: Request):
    """
    Debug page - debug.html
    
    Security: Only accessible in DEBUG mode OR by authenticated admin users.
    Non-admin users and unauthenticated requests in production are redirected.
    """
    try:
        # Allow access in DEBUG mode (development environment)
        if config.DEBUG:
            return templates.TemplateResponse("debug.html", {"request": request, "version": get_app_version()})
        
        # In production, require admin authentication - use manual session management
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            db = SessionLocal()
            try:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Detach user from session if it's attached (cache users are already detached)
                    if user in db:
                        db.expunge(user)
                    if is_admin(user):
                        logger.debug(f"Admin {user.phone} accessing /debug in production mode")
                        # Store admin status before closing session
                        is_admin_user = True
                    else:
                        is_admin_user = False
                else:
                    is_admin_user = False
            finally:
                db.close()  # ✅ Connection released BEFORE template rendering
            
            if is_admin_user:
                return templates.TemplateResponse("debug.html", {"request": request, "version": get_app_version()})
        
        # Not authorized - redirect to appropriate page based on AUTH_MODE
        logger.warning(f"Unauthorized /debug access attempt from {request.client.host}")
        if AUTH_MODE in ["demo", "bayi"]:
            return RedirectResponse(url="/demo", status_code=303)
        elif AUTH_MODE == "standard":
            return RedirectResponse(url="/auth", status_code=303)
        else:
            return RedirectResponse(url="/editor", status_code=303)
    except Exception as e:
        logger.error(f"/debug route failed: {e}", exc_info=True)
        raise

@router.get("/editor", response_class=HTMLResponse)
async def editor(request: Request):
    """Interactive editor - editor.html"""
    # Use manual session management - close immediately after database operations
    db = SessionLocal()
    try:
        # Demo mode: verify authentication
        if AUTH_MODE == "demo":
            auth_cookie = request.cookies.get("access_token")
            user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
            
            if not user:
                logger.debug("Demo mode: Redirecting unauthenticated /editor access to /demo")
                db.close()
                return RedirectResponse(url="/demo", status_code=303)
            
            # Detach user from session so it can be used after closing
            db.expunge(user)
            logger.debug(f"Demo mode: User {user.phone} accessing /editor")
        
        # Bayi mode: verify authentication (token via /loginByXz or passkey via /demo)
        elif AUTH_MODE == "bayi":
            auth_cookie = request.cookies.get("access_token")
            user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
            if user:
                # Detach user from session so it can be used after closing
                db.expunge(user)
            
            if not user:
                # Check IP whitelist for passkey-free access
                client_ip = get_client_ip(request)
                if is_ip_whitelisted(client_ip):
                    # IP is whitelisted - auto-login without passkey
                    logger.info(f"Bayi mode: IP {client_ip} is whitelisted, granting passkey-free access")
                    
                    # Get or create bayi organization
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
                                from services.redis_org_cache import org_cache
                                org_cache.cache_org(org)
                            except Exception as e:
                                logger.warning(f"Failed to cache bayi org: {e}")
                        except IntegrityError:
                            db.rollback()
                            org = db.query(Organization).filter(
                                Organization.code == BAYI_DEFAULT_ORG_CODE
                            ).first()
                            # Cache the org that was created by another request (race condition)
                            if org:
                                try:
                                    from services.redis_org_cache import org_cache
                                    org_cache.cache_org(org)
                                except Exception as e:
                                    logger.debug(f"Failed to cache org after race condition: {e}")
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Failed to create bayi organization: {e}")
                            db.close()
                            return RedirectResponse(url="/demo", status_code=303)
                    
                    # Check organization status
                    if org:
                        is_active = org.is_active if hasattr(org, 'is_active') else True
                        if not is_active:
                            logger.warning(f"IP whitelist blocked: Organization {org.code} is locked")
                            db.close()
                            return RedirectResponse(url="/demo", status_code=303)
                        if hasattr(org, 'expires_at') and org.expires_at:
                            if org.expires_at < datetime.utcnow():
                                logger.warning(f"IP whitelist blocked: Organization {org.code} expired")
                                db.close()
                                return RedirectResponse(url="/demo", status_code=303)
                    
                    # Get or create shared bayi IP user
                    user_phone = "bayi-ip@system.com"
                    bayi_user = db.query(User).filter(User.phone == user_phone).first()
                    
                    if not bayi_user:
                        try:
                            bayi_user = User(
                                phone=user_phone,
                                password_hash=hash_password("bayi-no-pwd"),
                                name="Bayi IP User",
                                organization_id=org.id if org else None,
                                created_at=datetime.utcnow()
                            )
                            db.add(bayi_user)
                            db.commit()
                            db.refresh(bayi_user)
                            logger.info(f"Created shared bayi IP user: {user_phone}")
                            # Cache the newly created user (non-blocking)
                            try:
                                from services.redis_user_cache import user_cache
                                user_cache.cache_user(bayi_user)
                            except Exception as e:
                                logger.warning(f"Failed to cache bayi user: {e}")
                        except IntegrityError:
                            db.rollback()
                            bayi_user = db.query(User).filter(User.phone == user_phone).first()
                            # Cache the user that was created by another request (race condition)
                            if bayi_user:
                                try:
                                    from services.redis_user_cache import user_cache
                                    user_cache.cache_user(bayi_user)
                                except Exception as e:
                                    logger.debug(f"Failed to cache user after race condition: {e}")
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Failed to create bayi IP user: {e}")
                            db.close()
                            return RedirectResponse(url="/demo", status_code=303)
                    
                    if not bayi_user:
                        logger.error("Failed to get or create bayi IP user")
                        db.close()
                        return RedirectResponse(url="/demo", status_code=303)
                    
                    # Generate JWT token and check admin status BEFORE closing session
                    # Detach bayi_user from session so it can be used after closing
                    db.expunge(bayi_user)
                    jwt_token = create_access_token(bayi_user)
                    user_is_admin = is_admin(bayi_user) if bayi_user else False
                    logger.info(f"Bayi IP whitelist auto-login successful: {client_ip}")
                    
                    # Close session BEFORE template rendering
                    db.close()
                    
                    # Serve editor with JWT cookie
                    response = templates.TemplateResponse(
                        "editor.html",
                        {
                            "request": request,
                            "version": get_app_version(),
                            "feature_mindmate": config.FEATURE_MINDMATE,
                            "feature_voice_agent": config.FEATURE_VOICE_AGENT,
                            "feature_drag_and_drop": config.FEATURE_DRAG_AND_DROP,
                            "feature_tab_mode": config.FEATURE_TAB_MODE,
                            "verbose_logging": config.VERBOSE_LOGGING,
                            "ai_assistant_name": config.AI_ASSISTANT_NAME,
                            "default_language": config.DEFAULT_LANGUAGE,
                            "wechat_qr_image": config.WECHAT_QR_IMAGE,
                            "user_is_admin": user_is_admin  # SECURITY: Server-side admin flag
                        }
                    )
                    response.set_cookie(
                        key="access_token",
                        value=jwt_token,
                        httponly=True,
                        secure=is_https(request),  # SECURITY: Auto-detect HTTPS
                        samesite="lax",
                        max_age=86400
                    )
                    return response
                
                # IP not whitelisted, redirect to passkey page
                logger.debug(f"Bayi mode: IP {client_ip} not whitelisted, redirecting to /demo")
                db.close()
                return RedirectResponse(url="/demo", status_code=303)
            
            logger.debug(f"Bayi mode: User {user.phone} accessing /editor")
        
        # SECURITY: Check if user is admin for server-side button rendering (defense-in-depth)
        # Note: Client-side check still runs for additional security
        user_is_admin = False
        try:
            # Enterprise mode: get enterprise user directly (network-level auth, no cookies)
            if AUTH_MODE == "enterprise":
                from services.redis_user_cache import user_cache
                enterprise_user = user_cache.get_by_phone(ENTERPRISE_DEFAULT_USER_PHONE)
                if enterprise_user:
                    # Detach user from session if it's attached (cache users are already detached)
                    if enterprise_user in db:
                        db.expunge(enterprise_user)
                    if is_admin(enterprise_user):
                        user_is_admin = True
            else:
                # Standard/Demo/Bayi modes: check cookie
                auth_cookie = request.cookies.get("access_token")
                if auth_cookie:
                    cookie_user = get_user_from_cookie(auth_cookie, db)
                    if cookie_user:
                        # Detach user from session if it's attached (cache users are already detached)
                        if cookie_user in db:
                            db.expunge(cookie_user)
                        # Log admin check for debugging (especially in bayi mode)
                        admin_status = is_admin(cookie_user)
                        if AUTH_MODE == "bayi":
                            logger.debug(f"Bayi mode admin check: user={cookie_user.phone}, is_admin={admin_status}")
                        if admin_status:
                            user_is_admin = True
        except Exception as e:
            # Fail secure - don't show admin button if check fails
            logger.error(f"Error checking admin status: {e}", exc_info=True)
            user_is_admin = False
        
        # Close session BEFORE template rendering
        db.close()
        
        return templates.TemplateResponse(
            "editor.html",
            {
                "request": request,
                "version": get_app_version(),
                "feature_mindmate": config.FEATURE_MINDMATE,
                "feature_voice_agent": config.FEATURE_VOICE_AGENT,
                "feature_drag_and_drop": config.FEATURE_DRAG_AND_DROP,
                "feature_tab_mode": config.FEATURE_TAB_MODE,
                "verbose_logging": config.VERBOSE_LOGGING,
                "ai_assistant_name": config.AI_ASSISTANT_NAME,
                "default_language": config.DEFAULT_LANGUAGE,
                "wechat_qr_image": config.WECHAT_QR_IMAGE,
                "user_is_admin": user_is_admin  # SECURITY: Server-side admin flag
            }
        )
    except Exception as e:
        logger.error(f"/editor route failed: {e}", exc_info=True)
        raise
    finally:
        # Ensure session is closed even if exception occurs
        try:
            db.close()
        except:
            pass

# ============================================================================
# REMOVED TEST ROUTES (Templates no longer exist)
# ============================================================================
# The following test routes were removed as their templates no longer exist:
# - /style-demo (style-demo.html)
# - /test_style_manager (test_style_manager.html)
# - /test_png_generation (test_png_generation.html)
# - /simple_test (simple_test.html)
# - /test_browser (test_browser_rendering.html)
# - /test_bubble_map (test_bubble_map_styling.html)
# - /debug_theme_conversion (debug_theme_conversion.html)
# - /timing_stats (timing_stats.html)
# These were development-only routes that are no longer needed.

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@router.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request):
    """Authentication page - login/register"""
    try:
        # Demo/Bayi mode: /auth doesn't make sense, redirect to /demo
        if AUTH_MODE in ["demo", "bayi"]:
            logger.debug(f"{AUTH_MODE.capitalize()} mode: Redirecting /auth access to /demo")
            return RedirectResponse(url="/demo", status_code=303)
        
        # If already authenticated, redirect to editor - use manual session management
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            db = SessionLocal()
            try:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Detach user from session if it's attached (cache users are already detached)
                    if user in db:
                        db.expunge(user)
                    logger.debug("User already authenticated, redirecting to /editor")
                    return RedirectResponse(url="/editor", status_code=303)
                else:
                    # Token is invalid or expired - clear the cookie to prevent redirect loops
                    logger.debug("Invalid or expired token cookie detected, clearing cookie")
                    response = templates.TemplateResponse("auth.html", {"request": request, "version": get_app_version()})
                    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
                    return response
            finally:
                db.close()  # ✅ Connection released BEFORE template rendering
        
        return templates.TemplateResponse("auth.html", {"request": request, "version": get_app_version()})
    except Exception as e:
        logger.error(f"/auth route failed: {e}", exc_info=True)
        raise

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
                            from services.redis_org_cache import org_cache
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
                            logger.error(f"Failed to create or retrieve bayi organization")
                            return RedirectResponse(url="/demo", status_code=303)
                        # Cache the org that was created by another request (race condition)
                        try:
                            from services.redis_org_cache import org_cache
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
                            from services.redis_user_cache import user_cache
                            user_cache.cache_user(bayi_user)
                        except Exception as e:
                            logger.warning(f"Failed to cache bayi user: {e}")
                    except IntegrityError as e:
                        # Handle race condition: user created by another request
                        db.rollback()
                        logger.debug(f"User creation race condition (expected): {e}")
                        bayi_user = db.query(User).filter(User.phone == user_phone).first()
                        if not bayi_user:
                            logger.error(f"Failed to create or retrieve bayi IP user after race condition")
                            return RedirectResponse(url="/demo", status_code=303)
                        # Cache the user that was created by another request (race condition)
                        try:
                            from services.redis_user_cache import user_cache
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
                                from services.redis_user_cache import user_cache
                                user_cache.cache_user(bayi_user)
                            except Exception as cache_err:
                                logger.debug(f"Failed to cache user after error recovery: {cache_err}")
                
                # Session management: For IP whitelist users, allow multiple concurrent sessions
                # (50 teachers can all be logged in simultaneously from whitelisted IP)
                # We don't invalidate old sessions for shared bayi-ip@system.com account
                session_manager = get_session_manager()
                
                # Generate JWT token (user object is still valid after expunge)
                jwt_token = create_access_token(bayi_user)
                
                # Store new session in Redis (allow_multiple=True for shared account)
                # This allows multiple teachers to use the system simultaneously
                session_manager.store_session(bayi_user.id, jwt_token, allow_multiple=True)
                
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
            from services.redis_bayi_token import get_bayi_token_tracker
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
            from services.redis_bayi_token import get_bayi_token_tracker
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
                from services.redis_bayi_token import get_bayi_token_tracker
                token_tracker = get_bayi_token_tracker()
                token_tracker.cache_token_validation(token, False)
            except Exception as e:
                logger.debug(f"Failed to cache invalid token: {e}")
            # Invalid or expired token: redirect to demo passkey page
            return RedirectResponse(url="/demo", status_code=303)
        
        logger.info(f"Token validation passed - proceeding with user creation/retrieval")
        
        # Mark token as used (replay attack prevention) and cache validation result
        try:
            from services.redis_bayi_token import get_bayi_token_tracker
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
                    from services.redis_org_cache import org_cache
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
                        from services.redis_user_cache import user_cache
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
                        # Redirect to demo instead of showing error
                    else:
                        # Cache the user if it exists after error recovery
                        try:
                            from services.redis_user_cache import user_cache
                            user_cache.cache_user(bayi_user)
                        except Exception as cache_err:
                            logger.debug(f"Failed to cache user after error recovery: {cache_err}")
                        return RedirectResponse(url="/demo", status_code=303)
            
            # Session management: Invalidate old sessions before creating new one
            session_manager = get_session_manager()
            old_token_hash = session_manager.get_session_token(bayi_user.id)
            session_manager.invalidate_user_sessions(bayi_user.id, old_token_hash=old_token_hash, ip_address=client_ip)
            
            # Generate JWT token (user object is still valid after session close)
            jwt_token = create_access_token(bayi_user)
            
            # Store new session in Redis
            session_manager.store_session(bayi_user.id, jwt_token)
            
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


@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request):
    """Demo/Bayi mode passkey page - accessible in demo and bayi modes"""
    try:
        # Allow access in demo mode or bayi mode
        if AUTH_MODE not in ["demo", "bayi"]:
            logger.warning(f"/demo accessed in {AUTH_MODE} mode, redirecting to /auth")
            return RedirectResponse(url="/auth" if AUTH_MODE == "standard" else "/editor", status_code=303)
        
        # If user is already authenticated via cookie, redirect based on role - use manual session management
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            db = SessionLocal()
            try:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Detach user from session if it's attached (cache users are already detached)
                    if user in db:
                        db.expunge(user)
                    # Redirect based on admin status
                    if is_admin(user):
                        logger.debug(f"{AUTH_MODE.capitalize()} mode: Admin {user.phone} already authenticated, redirecting to /admin")
                        return RedirectResponse(url="/admin", status_code=303)
                    else:
                        logger.debug(f"{AUTH_MODE.capitalize()} mode: User {user.phone} already authenticated, redirecting to /editor")
                        return RedirectResponse(url="/editor", status_code=303)
            finally:
                db.close()  # ✅ Connection released BEFORE template rendering
        
        return templates.TemplateResponse("demo-login.html", {"request": request, "version": get_app_version()})
    except Exception as e:
        logger.error(f"/demo route failed: {e}", exc_info=True)
        raise

@router.get("/favicon.ico")
async def favicon():
    """Serve favicon.ico - serves SVG favicon"""
    favicon_path = Path("static/favicon.svg")
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    # Return 404 if favicon doesn't exist
    raise HTTPException(status_code=404, detail="Favicon not found")

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin management panel - SECURITY: Admin access required in ALL modes"""
    try:
        # SECURITY: Check authentication and admin status in ALL auth modes - use manual session management
        auth_cookie = request.cookies.get("access_token")
        user = None
        if auth_cookie:
            db = SessionLocal()
            try:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Detach user from session if it's attached (cache users are already detached)
                    if user in db:
                        db.expunge(user)
            finally:
                db.close()  # ✅ Connection released BEFORE template rendering
        
        if not user:
            # Not authenticated - redirect based on auth mode
            if AUTH_MODE in ["demo", "bayi"]:
                logger.debug(f"{AUTH_MODE.capitalize()} mode: Redirecting unauthenticated /admin access to /demo")
                return RedirectResponse(url="/demo", status_code=303)
            else:
                logger.debug(f"Standard mode: Redirecting unauthenticated /admin access to /auth")
                return RedirectResponse(url="/auth", status_code=303)
        
        # SECURITY: Check if user is admin (required in ALL modes)
        if not is_admin(user):
            logger.warning(f"Non-admin user {user.phone} attempted to access /admin, redirecting to /editor")
            return RedirectResponse(url="/editor", status_code=303)
        
        logger.debug(f"Admin {user.phone} accessing /admin (mode: {AUTH_MODE})")
        
        return templates.TemplateResponse("admin.html", {"request": request, "version": get_app_version()})
    except Exception as e:
        logger.error(f"/admin route failed: {e}", exc_info=True)
        raise

# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Page routes initialized: 6 routes registered")

