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
from routers.register import register_routers
from services.infrastructure.lifecycle.startup import setup_early_configuration
from services.infrastructure.utils.logging_config import setup_logging
from services.infrastructure.lifecycle.lifespan import lifespan
from services.infrastructure.http.middleware import setup_middleware
from services.infrastructure.http.exception_handlers import setup_exception_handlers
from services.infrastructure.utils.spa_handler import setup_vue_spa, is_dev_mode
from services.infrastructure.process.server_launcher import run_server

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

register_routers(app)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    run_server()
