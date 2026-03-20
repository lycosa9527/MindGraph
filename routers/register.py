"""
Router Registration Module

Centralized router registration for all FastAPI routes.
This module handles the registration order and conditional feature flags.
"""
import logging

from fastapi import FastAPI

from config.settings import config
from routers import (
    api,
    concept_map_focus,
    node_palette,
    relationship_labels,
    inline_recommendations,
    auth,
    public_dashboard,
)
from routers.admin import env_router as admin_env, logs_router as admin_logs, realtime_router as admin_realtime
from routers.core import pages, cache, update_notification
from routers.core.vue_spa import router as vue_spa
from routers.core.health import router as health_router
from routers.features import voice, school_zone, askonce

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

COMMUNITY_MODULE = None
if config.FEATURE_COMMUNITY:
    try:
        from routers.features.community import router as COMMUNITY_MODULE
    except Exception as e:
        COMMUNITY_MODULE = None
        logger.debug("[RouterRegistration] Failed to import community router: %s", e, exc_info=True)
else:
    logger.debug("[RouterRegistration] Community feature disabled via FEATURE_COMMUNITY flag")

GEWE_MODULE = None
if config.FEATURE_GEWE:
    try:
        from routers.features.gewe import router as GEWE_MODULE
    except Exception as e:
        GEWE_MODULE = None
        logger.debug("[RouterRegistration] Failed to import gewe router: %s", e, exc_info=True)
else:
    logger.debug("[RouterRegistration] Gewe feature disabled via FEATURE_GEWE flag")

WORKSHOP_CHAT_MODULE = None
WORKSHOP_CHAT_WS_MODULE = None
if config.FEATURE_WORKSHOP_CHAT:
    try:
        from routers.features import workshop_chat as _wc_mod
        from routers.features import workshop_chat_ws as _wc_ws_mod
        WORKSHOP_CHAT_MODULE = _wc_mod.router
        WORKSHOP_CHAT_WS_MODULE = _wc_ws_mod.router
    except Exception as e:
        WORKSHOP_CHAT_MODULE = None
        WORKSHOP_CHAT_WS_MODULE = None
        logger.warning(
            "[RouterRegistration] Failed to import workshop chat routers: %s. "
            "Workshop Chat API (/api/chat/*) will not be available. Fix the error and restart.",
            e,
            exc_info=True,
        )
else:
    logger.debug("[RouterRegistration] Workshop Chat feature disabled via FEATURE_WORKSHOP_CHAT flag")


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
    app.include_router(relationship_labels.router)  # Relationship labels (concept map)
    app.include_router(inline_recommendations.router)  # Inline recommendations (mindmap, flow, etc.)
    app.include_router(
        concept_map_focus.router,
        prefix="/api",
    )  # Concept map focus question (standard mode)
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

    # Community (社区分享) - global diagram sharing
    if COMMUNITY_MODULE is not None:
        app.include_router(COMMUNITY_MODULE)
        logger.info("[RouterRegistration] Community router registered at /api/community")
    else:
        if config.FEATURE_COMMUNITY:
            logger.warning(
                "[RouterRegistration] Community router NOT registered - import failed or router is None. "
                "Check DEBUG logs for details."
            )
        else:
            logger.debug("[RouterRegistration] Community feature disabled via FEATURE_COMMUNITY flag")

    # Gewe WeChat integration (admin only) - must be before vue_spa
    if GEWE_MODULE is not None:
        app.include_router(GEWE_MODULE)
        logger.info("[RouterRegistration] Gewe router registered at /api/gewe")
    else:
        if config.FEATURE_GEWE:
            logger.warning(
                "[RouterRegistration] Gewe router NOT registered - import failed or router is None. "
                "Check DEBUG logs for details."
            )
        else:
            logger.debug("[RouterRegistration] Gewe feature disabled via FEATURE_GEWE flag")

    # Workshop Chat (工作坊) - school-scoped communication
    if WORKSHOP_CHAT_MODULE is not None:
        app.include_router(WORKSHOP_CHAT_MODULE)
        logger.info("[RouterRegistration] Workshop Chat REST router registered at /api/chat")
    else:
        if config.FEATURE_WORKSHOP_CHAT:
            logger.warning(
                "[RouterRegistration] Workshop Chat REST router NOT registered - import failed. "
                "Check DEBUG logs for details."
            )
        else:
            logger.debug("[RouterRegistration] Workshop Chat feature disabled via FEATURE_WORKSHOP_CHAT flag")

    # Vue SPA handles all page routes (v5.0.0+) - MUST be registered AFTER API routes
    app.include_router(vue_spa)

    # Feature routers registered after vue_spa
    app.include_router(admin_env)  # Admin environment settings management
    app.include_router(admin_logs)  # Admin log streaming
    app.include_router(admin_realtime)  # Admin realtime user activity monitoring
    app.include_router(voice)  # VoiceAgent (real-time voice conversation)
    app.include_router(update_notification)  # Update notification system
    # Public dashboard endpoints
    app.include_router(public_dashboard.router, prefix="/api/public", tags=["Public Dashboard"])
    app.include_router(school_zone)  # School Zone (organization-scoped sharing)
    app.include_router(askonce)  # AskOnce (多应) - Multi-LLM streaming chat

    # Workshop Chat WebSocket
    if WORKSHOP_CHAT_WS_MODULE is not None:
        app.include_router(WORKSHOP_CHAT_WS_MODULE)
        logger.info("[RouterRegistration] Workshop Chat WS router registered at /api/ws/chat")

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
