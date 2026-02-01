"""
Router Registration Module

Centralized router registration for all FastAPI routes.
This module handles the registration order and conditional feature flags.
"""
import logging

from fastapi import FastAPI

from config.settings import config
from routers import (
    api, node_palette, auth, public_dashboard
)
from routers.admin import env_router as admin_env, logs_router as admin_logs, realtime_router as admin_realtime
from routers.core import pages, cache, update_notification
from routers.core.vue_spa import router as vue_spa
from routers.core.health import router as health_router
from routers.features import voice, tab_mode, school_zone, askonce, gewe

logger = logging.getLogger(__name__)

# Conditionally import feature routers based on feature flags
LIBRARY_MODULE = None
if config.FEATURE_LIBRARY:
    try:
        from routers.features import library as LIBRARY_MODULE
    except Exception as e:
        LIBRARY_MODULE = None
        logger.debug("[RouterRegistration] Failed to import library router: %s", e, exc_info=True)
else:
    logger.debug("[RouterRegistration] Library feature disabled via FEATURE_LIBRARY flag")

DEBATEVERSE_MODULE = None
if config.FEATURE_DEBATEVERSE:
    try:
        from routers.features import debateverse as DEBATEVERSE_MODULE
    except Exception as e:
        DEBATEVERSE_MODULE = None
        logger.debug("[RouterRegistration] Failed to import debateverse router: %s", e, exc_info=True)
else:
    logger.debug("[RouterRegistration] DebateVerse feature disabled via FEATURE_DEBATEVERSE flag")


def register_routers(app: FastAPI) -> None:
    """
    Register all FastAPI routers in the correct order.
    
    Router registration order is critical:
    1. Health check endpoints (no prefix)
    2. Core API routes (must be before vue_spa catch-all)
    3. Feature routers with feature flags (must be before vue_spa)
    4. Vue SPA catch-all route (must be last)
    5. Other feature routers (after vue_spa)
    
    Args:
        app: FastAPI application instance
    """
    # Health check endpoints
    app.include_router(health_router)

    # API routes must be registered BEFORE vue_spa catch-all route
    # Authentication & utility routes (loginByXz, favicon)
    app.include_router(pages)
    app.include_router(cache)
    app.include_router(api.router)
    app.include_router(node_palette.router)  # Node Palette endpoints
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])  # Authentication system

    # Feature routers that must be registered BEFORE vue_spa catch-all
    # Library (图书馆) - PDF viewing with danmaku comments
    if LIBRARY_MODULE is not None:
        app.include_router(LIBRARY_MODULE)
        logger.info("[RouterRegistration] Library router registered at /api/library")
    else:
        if config.FEATURE_LIBRARY:
            logger.warning(
                "[RouterRegistration] Library router NOT registered - import failed or router is None. "
                "Check DEBUG logs for details."
            )
        else:
            logger.debug("[RouterRegistration] Library feature disabled via FEATURE_LIBRARY flag")

    # Gewe WeChat integration (admin only) - must be before vue_spa
    app.include_router(gewe)

    # Vue SPA handles all page routes (v5.0.0+) - MUST be registered AFTER API routes
    app.include_router(vue_spa)

    # Feature routers registered after vue_spa
    app.include_router(admin_env)  # Admin environment settings management
    app.include_router(admin_logs)  # Admin log streaming
    app.include_router(admin_realtime)  # Admin realtime user activity monitoring
    app.include_router(voice)  # VoiceAgent (real-time voice conversation)
    app.include_router(update_notification)  # Update notification system
    app.include_router(tab_mode)  # Tab Mode (autocomplete and expansion)
    # Public dashboard endpoints
    app.include_router(public_dashboard.router, prefix="/api/public", tags=["Public Dashboard"])
    app.include_router(school_zone)  # School Zone (organization-scoped sharing)
    app.include_router(askonce)  # AskOnce (多应) - Multi-LLM streaming chat

    # DebateVerse (论境) - US-style debate system
    if DEBATEVERSE_MODULE is not None:
        app.include_router(DEBATEVERSE_MODULE)
        logger.info("[RouterRegistration] DebateVerse router registered at /api/debateverse")
    else:
        if config.FEATURE_DEBATEVERSE:
            logger.warning(
                "[RouterRegistration] DebateVerse router NOT registered - import failed or router is None. "
                "Check DEBUG logs for details."
            )
        else:
            logger.debug("[RouterRegistration] DebateVerse feature disabled via FEATURE_DEBATEVERSE flag")
