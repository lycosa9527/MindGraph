"""
MindGraph Template Rendering Routes
====================================

FastAPI routes for serving HTML templates.

All template routes are async for consistency, though they perform minimal I/O.

Author: lycosa9527
Made by: MindSpring Team
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
from config.database import get_db

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
async def index(request: Request, db: Session = Depends(get_db)):
    """Landing page - redirects based on AUTH_MODE"""
    try:
        # Standard mode: redirect to /auth for login/register
        if AUTH_MODE == "standard":
            auth_cookie = request.cookies.get("access_token")
            if auth_cookie:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Already authenticated, go to editor
                    logger.debug("Standard mode: Authenticated user, redirecting / to /editor")
                    return RedirectResponse(url="/editor", status_code=303)
            
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
async def debug(request: Request, db: Session = Depends(get_db)):
    """
    Debug page - debug.html
    
    Security: Only accessible in DEBUG mode OR by authenticated admin users.
    Non-admin users and unauthenticated requests in production are redirected.
    """
    try:
        # Allow access in DEBUG mode (development environment)
        if config.DEBUG:
            return templates.TemplateResponse("debug.html", {"request": request, "version": get_app_version()})
        
        # In production, require admin authentication
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            user = get_user_from_cookie(auth_cookie, db)
            if user and is_admin(user):
                logger.debug(f"Admin {user.phone} accessing /debug in production mode")
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
async def editor(request: Request, db: Session = Depends(get_db)):
    """Interactive editor - editor.html"""
    try:
        # Demo mode: verify authentication
        if AUTH_MODE == "demo":
            auth_cookie = request.cookies.get("access_token")
            user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
            
            if not user:
                logger.debug("Demo mode: Redirecting unauthenticated /editor access to /demo")
                return RedirectResponse(url="/demo", status_code=303)
            
            logger.debug(f"Demo mode: User {user.phone} accessing /editor")
        
        # Bayi mode: verify authentication (token via /loginByXz or passkey via /demo)
        elif AUTH_MODE == "bayi":
            auth_cookie = request.cookies.get("access_token")
            user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
            
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
                        except IntegrityError:
                            db.rollback()
                            org = db.query(Organization).filter(
                                Organization.code == BAYI_DEFAULT_ORG_CODE
                            ).first()
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Failed to create bayi organization: {e}")
                            return RedirectResponse(url="/demo", status_code=303)
                    
                    # Check organization status
                    if org:
                        is_active = org.is_active if hasattr(org, 'is_active') else True
                        if not is_active:
                            logger.warning(f"IP whitelist blocked: Organization {org.code} is locked")
                            return RedirectResponse(url="/demo", status_code=303)
                        if hasattr(org, 'expires_at') and org.expires_at:
                            if org.expires_at < datetime.utcnow():
                                logger.warning(f"IP whitelist blocked: Organization {org.code} expired")
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
                        except IntegrityError:
                            db.rollback()
                            bayi_user = db.query(User).filter(User.phone == user_phone).first()
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Failed to create bayi IP user: {e}")
                            return RedirectResponse(url="/demo", status_code=303)
                    
                    if not bayi_user:
                        logger.error("Failed to get or create bayi IP user")
                        return RedirectResponse(url="/demo", status_code=303)
                    
                    # Generate JWT token and set cookie
                    jwt_token = create_access_token(bayi_user)
                    logger.info(f"Bayi IP whitelist auto-login successful: {client_ip}")
                    
                    # Serve editor with JWT cookie
                    # SECURITY: Check if bayi IP user is admin (unlikely but check anyway)
                    user_is_admin = is_admin(bayi_user) if bayi_user else False
                    
                    response = templates.TemplateResponse(
                        "editor.html",
                        {
                            "request": request,
                            "version": get_app_version(),
                            "feature_learning_mode": config.FEATURE_LEARNING_MODE,
                            "feature_thinkguide": config.FEATURE_THINKGUIDE,
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
                return RedirectResponse(url="/demo", status_code=303)
            
            logger.debug(f"Bayi mode: User {user.phone} accessing /editor")
        
        # SECURITY: Check if user is admin for server-side button rendering (defense-in-depth)
        # Note: Client-side check still runs for additional security
        user_is_admin = False
        try:
            # Enterprise mode: get enterprise user directly (network-level auth, no cookies)
            if AUTH_MODE == "enterprise":
                enterprise_user = db.query(User).filter(User.phone == ENTERPRISE_DEFAULT_USER_PHONE).first()
                if enterprise_user and is_admin(enterprise_user):
                    user_is_admin = True
            else:
                # Standard/Demo/Bayi modes: check cookie
                auth_cookie = request.cookies.get("access_token")
                if auth_cookie:
                    cookie_user = get_user_from_cookie(auth_cookie, db)
                    if cookie_user:
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
        
        return templates.TemplateResponse(
            "editor.html",
            {
                "request": request,
                "version": get_app_version(),
                "feature_learning_mode": config.FEATURE_LEARNING_MODE,
                "feature_thinkguide": config.FEATURE_THINKGUIDE,
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
async def auth_page(request: Request, db: Session = Depends(get_db)):
    """Authentication page - login/register"""
    try:
        # Demo/Bayi mode: /auth doesn't make sense, redirect to /demo
        if AUTH_MODE in ["demo", "bayi"]:
            logger.debug(f"{AUTH_MODE.capitalize()} mode: Redirecting /auth access to /demo")
            return RedirectResponse(url="/demo", status_code=303)
        
        # If already authenticated, redirect to editor
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            user = get_user_from_cookie(auth_cookie, db)
            if user:
                logger.debug("User already authenticated, redirecting to /editor")
                return RedirectResponse(url="/editor", status_code=303)
        
        return templates.TemplateResponse("auth.html", {"request": request, "version": get_app_version()})
    except Exception as e:
        logger.error(f"/auth route failed: {e}", exc_info=True)
        raise

@router.get("/loginByXz")
async def login_by_xz(
    request: Request,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
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
                except IntegrityError as e:
                    # Handle race condition: user created by another request
                    db.rollback()
                    logger.debug(f"User creation race condition (expected): {e}")
                    bayi_user = db.query(User).filter(User.phone == user_phone).first()
                    if not bayi_user:
                        logger.error(f"Failed to create or retrieve bayi IP user after race condition")
                        return RedirectResponse(url="/demo", status_code=303)
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to create bayi IP user: {e}")
                    bayi_user = db.query(User).filter(User.phone == user_phone).first()
                    if not bayi_user:
                        return RedirectResponse(url="/demo", status_code=303)
            
            # Generate JWT token
            jwt_token = create_access_token(bayi_user)
            
            logger.info(f"Bayi IP whitelist authentication successful: {client_ip}")
            
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
        
        # Decrypt token
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
        
        # Validate token body
        logger.info(f"Validating token body - from: {body.get('from')}, timestamp: {body.get('timestamp')}")
        validation_result = validate_bayi_token_body(body)
        if not validation_result:
            logger.error(f"Bayi token validation failed - body: {body}, from field: '{body.get('from')}', timestamp: {body.get('timestamp')} - redirecting to /demo")
            # Invalid or expired token: redirect to demo passkey page
            return RedirectResponse(url="/demo", status_code=303)
        
        logger.info(f"Token validation passed - proceeding with user creation/retrieval")
        
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
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to create bayi user: {e}")
                # Try to get user again in case it was created by another request
                bayi_user = db.query(User).filter(User.phone == user_phone).first()
                if not bayi_user:
                    logger.error(f"Failed to create bayi user after retry: {e}")
                    # Redirect to demo instead of showing error
                    return RedirectResponse(url="/demo", status_code=303)
        
        # Generate JWT token
        jwt_token = create_access_token(bayi_user)
        
        logger.info(f"Bayi mode authentication successful: {user_phone}")
        
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
async def demo_page(request: Request, db: Session = Depends(get_db)):
    """Demo/Bayi mode passkey page - accessible in demo and bayi modes"""
    try:
        # Allow access in demo mode or bayi mode
        if AUTH_MODE not in ["demo", "bayi"]:
            logger.warning(f"/demo accessed in {AUTH_MODE} mode, redirecting to /auth")
            return RedirectResponse(url="/auth" if AUTH_MODE == "standard" else "/editor", status_code=303)
        
        # If user is already authenticated via cookie, redirect based on role
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            user = get_user_from_cookie(auth_cookie, db)
            if user:
                # Redirect based on admin status
                if is_admin(user):
                    logger.debug(f"{AUTH_MODE.capitalize()} mode: Admin {user.phone} already authenticated, redirecting to /admin")
                    return RedirectResponse(url="/admin", status_code=303)
                else:
                    logger.debug(f"{AUTH_MODE.capitalize()} mode: User {user.phone} already authenticated, redirecting to /editor")
                    return RedirectResponse(url="/editor", status_code=303)
        
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
async def admin_page(request: Request, db: Session = Depends(get_db)):
    """Admin management panel - SECURITY: Admin access required in ALL modes"""
    try:
        # SECURITY: Check authentication and admin status in ALL auth modes
        auth_cookie = request.cookies.get("access_token")
        user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
        
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

