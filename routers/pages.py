"""
MindGraph Template Rendering Routes
====================================

FastAPI routes for serving HTML templates.

All template routes are async for consistency, though they perform minimal I/O.

Author: lycosa9527
Made by: MindSpring Team
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging

from config.settings import config

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
async def editor(request: Request):
    """Interactive editor - editor.html"""
    try:
        return templates.TemplateResponse(
            "editor.html",
            {
                "request": request,
                "feature_learning_mode": config.FEATURE_LEARNING_MODE,
                "feature_thinkguide": config.FEATURE_THINKGUIDE,
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

# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Page routes initialized: 11 routes registered")

