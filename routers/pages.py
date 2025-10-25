"""
MindGraph Template Rendering Routes
====================================

FastAPI routes for serving HTML templates.

All template routes are async for consistency, though they perform minimal I/O.

Author: lycosa9527
Made by: MindSpring Team
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

from config.settings import config
from config.database import get_db
from utils.auth import AUTH_MODE, get_user_from_cookie, is_admin
from sqlalchemy.orm import Session

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
    """Landing page - index.html"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"/ route failed: {e}", exc_info=True)
        raise

@router.get("/debug", response_class=HTMLResponse)
async def debug(request: Request):
    """Debug page - debug.html"""
    try:
        return templates.TemplateResponse("debug.html", {"request": request})
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
        
        return templates.TemplateResponse(
            "editor.html",
            {
                "request": request,
                "feature_learning_mode": config.FEATURE_LEARNING_MODE,
                "feature_thinkguide": config.FEATURE_THINKGUIDE,
                "feature_mindmate": config.FEATURE_MINDMATE,
                "feature_voice_agent": config.FEATURE_VOICE_AGENT,
                "verbose_logging": config.VERBOSE_LOGGING,
                "ai_assistant_name": config.AI_ASSISTANT_NAME
            }
        )
    except Exception as e:
        logger.error(f"/editor route failed: {e}", exc_info=True)
        raise

@router.get("/style-demo", response_class=HTMLResponse)
async def style_demo(request: Request):
    """Style demonstration - style-demo.html"""
    try:
        return templates.TemplateResponse("style-demo.html", {"request": request})
    except Exception as e:
        logger.error(f"/style-demo route failed: {e}", exc_info=True)
        raise

@router.get("/test_style_manager", response_class=HTMLResponse)
async def test_style_manager(request: Request):
    """Test style manager - test_style_manager.html"""
    try:
        return templates.TemplateResponse("test_style_manager.html", {"request": request})
    except Exception as e:
        logger.error(f"/test_style_manager route failed: {e}", exc_info=True)
        raise

@router.get("/test_png_generation", response_class=HTMLResponse)
async def test_png_generation(request: Request):
    """Test PNG generation - test_png_generation.html"""
    try:
        return templates.TemplateResponse("test_png_generation.html", {"request": request})
    except Exception as e:
        logger.error(f"/test_png_generation route failed: {e}", exc_info=True)
        raise

@router.get("/simple_test", response_class=HTMLResponse)
async def simple_test(request: Request):
    """Simple test page - simple_test.html"""
    try:
        return templates.TemplateResponse("simple_test.html", {"request": request})
    except Exception as e:
        logger.error(f"/simple_test route failed: {e}", exc_info=True)
        raise

@router.get("/test_browser", response_class=HTMLResponse)
async def browser_test(request: Request):
    """Browser rendering test - test_browser_rendering.html"""
    try:
        return templates.TemplateResponse("test_browser_rendering.html", {"request": request})
    except Exception as e:
        logger.error(f"/test_browser route failed: {e}", exc_info=True)
        raise

@router.get("/test_bubble_map", response_class=HTMLResponse)
async def bubble_map_test(request: Request):
    """Bubble map styling test - test_bubble_map_styling.html"""
    try:
        return templates.TemplateResponse("test_bubble_map_styling.html", {"request": request})
    except Exception as e:
        logger.error(f"/test_bubble_map route failed: {e}", exc_info=True)
        raise

@router.get("/debug_theme_conversion", response_class=HTMLResponse)
async def debug_theme_conversion(request: Request):
    """Debug theme conversion - debug_theme_conversion.html"""
    try:
        return templates.TemplateResponse("debug_theme_conversion.html", {"request": request})
    except Exception as e:
        logger.error(f"/debug_theme_conversion route failed: {e}", exc_info=True)
        raise

@router.get("/timing_stats", response_class=HTMLResponse)
async def timing_stats(request: Request):
    """Timing statistics - timing_stats.html"""
    try:
        return templates.TemplateResponse("timing_stats.html", {"request": request})
    except Exception as e:
        logger.error(f"/timing_stats route failed: {e}", exc_info=True)
        raise

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@router.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request, db: Session = Depends(get_db)):
    """Authentication page - login/register"""
    try:
        # Demo mode: /auth doesn't make sense, redirect to /demo
        if AUTH_MODE == "demo":
            logger.debug("Demo mode: Redirecting /auth access to /demo")
            return RedirectResponse(url="/demo", status_code=303)
        
        # If already authenticated, redirect to editor
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie:
            user = get_user_from_cookie(auth_cookie, db)
            if user:
                logger.debug("User already authenticated, redirecting to /editor")
                return RedirectResponse(url="/editor", status_code=303)
        
        return templates.TemplateResponse("auth.html", {"request": request})
    except Exception as e:
        logger.error(f"/auth route failed: {e}", exc_info=True)
        raise

@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request, db: Session = Depends(get_db)):
    """Demo mode passkey page"""
    try:
        # If user is already authenticated via cookie, redirect based on role
        if AUTH_MODE == "demo":
            auth_cookie = request.cookies.get("access_token")
            if auth_cookie:
                user = get_user_from_cookie(auth_cookie, db)
                if user:
                    # Redirect based on admin status
                    if is_admin(user):
                        logger.debug(f"Demo mode: Admin {user.phone} already authenticated, redirecting to /admin")
                        return RedirectResponse(url="/admin", status_code=303)
                    else:
                        logger.debug(f"Demo mode: User {user.phone} already authenticated, redirecting to /editor")
                        return RedirectResponse(url="/editor", status_code=303)
        
        return templates.TemplateResponse("demo-login.html", {"request": request})
    except Exception as e:
        logger.error(f"/demo route failed: {e}", exc_info=True)
        raise

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    """Admin management panel"""
    try:
        # Demo mode: verify authentication and admin status
        if AUTH_MODE == "demo":
            auth_cookie = request.cookies.get("access_token")
            user = get_user_from_cookie(auth_cookie, db) if auth_cookie else None
            
            if not user:
                logger.debug("Demo mode: Redirecting unauthenticated /admin access to /demo")
                return RedirectResponse(url="/demo", status_code=303)
            
            # Check if user is admin
            if not is_admin(user):
                logger.warning(f"Demo mode: Non-admin user {user.phone} attempted to access /admin, redirecting to /editor")
                return RedirectResponse(url="/editor", status_code=303)
            
            logger.debug(f"Demo mode: Admin {user.phone} accessing /admin")
        
        return templates.TemplateResponse("admin.html", {"request": request})
    except Exception as e:
        logger.error(f"/admin route failed: {e}", exc_info=True)
        raise

# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Page routes initialized: 14 routes registered (11 legacy + 3 auth)")

