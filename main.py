"""
MindGraph - AI-Powered Graph Generation Application (FastAPI)
==============================================================

Modern async web application for AI-powered diagram generation.

Version: See VERSION file (centralized version management)
Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License

Features:
- Full async/await support for 4,000+ concurrent SSE connections
- FastAPI with Pydantic models for type safety
- Uvicorn ASGI server (Windows + Ubuntu compatible)
- Auto-generated OpenAPI documentation at /docs
- Comprehensive logging, middleware, and business logic

Status: Production Ready
"""

# Third-party imports
from fastapi import FastAPI

# First-party imports
from config.settings import config
from routers import (
    api, node_palette, auth, public_dashboard
)
from routers.admin import env_router as admin_env, logs_router as admin_logs, realtime_router as admin_realtime
from routers.features import voice, tab_mode, school_zone, askonce
from routers.core import pages, cache, update_notification
from routers.core.vue_spa import router as vue_spa
from routers.core.health import router as health_router
from services.infrastructure.lifecycle.startup import setup_early_configuration
from services.infrastructure.utils.logging_config import setup_logging
from services.infrastructure.lifecycle.lifespan import lifespan
from services.infrastructure.http.middleware import setup_middleware
from services.infrastructure.http.exception_handlers import setup_exception_handlers
from services.infrastructure.utils.spa_handler import setup_vue_spa, is_dev_mode

# Early configuration setup (must happen before logging)
setup_early_configuration()

# Setup logging (must happen early, before other modules use logger)
logger = setup_logging()

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="MindGraph API",
    description="AI-Powered Graph Generation with FastAPI + Uvicorn",
    version=config.version,
    # Disable Swagger UI in production for security (only enable in DEBUG mode)
    docs_url="/docs" if config.debug else None,
    redoc_url="/redoc" if config.debug else None,
    lifespan=lifespan
)

# ============================================================================
# MIDDLEWARE & EXCEPTION HANDLERS
# ============================================================================

setup_middleware(app)
setup_exception_handlers(app)

# ============================================================================
# STATIC FILES AND VUE SPA
# ============================================================================

# Vue SPA setup (v5.0.0+)
# In production: Serve Vue app from frontend/dist/
# In development: Vite dev server handles frontend on port 3000

# Setup Vue SPA - mounts /assets from frontend/dist/assets/
_VUE_SPA_ENABLED = setup_vue_spa(app)

if _VUE_SPA_ENABLED:
    logger.info("Vue SPA mode: Frontend served from frontend/dist/")
elif not is_dev_mode():
    # Only warn in production - in dev mode, Vite handles frontend
    logger.warning("Vue SPA not available - run 'npm run build' in frontend/ directory")

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

# Health check endpoints
app.include_router(health_router)

# API routes must be registered BEFORE vue_spa catch-all route
# Authentication & utility routes (loginByXz, favicon)
app.include_router(pages)
app.include_router(cache)
app.include_router(api.router)
app.include_router(node_palette.router)  # Node Palette endpoints
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])  # Authentication system

# Vue SPA handles all page routes (v5.0.0+) - MUST be registered AFTER API routes
app.include_router(vue_spa)
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
debateverse_router = None
if config.FEATURE_DEBATEVERSE:
    try:
        from routers.features import debateverse
        debateverse_router = debateverse
        app.include_router(debateverse_router)
        logger.info("[Main] DebateVerse router registered at /api/debateverse")
    except Exception as e:
        logger.warning("[Main] Failed to register DebateVerse router: %s", e, exc_info=True)
else:
    logger.debug("[Main] DebateVerse feature disabled via FEATURE_DEBATEVERSE flag")

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    from services.infrastructure.process.server_launcher import run_server
    run_server()
