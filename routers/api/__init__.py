"""
API Router Module
=================

Main API router that combines all sub-routers for the application.

This module imports and registers all API endpoint routers, including:
- Diagram generation and management
- File operations
- Frontend logging
- Knowledge Space operations
- And other feature-specific routers
"""
import logging

from fastapi import APIRouter

from config.settings import config as app_config

from . import (
    diagram_generation,
    png_export,
    sse_streaming,
    llm_operations,
    frontend_logging,
    layout,
    feedback,
    dify_files,
    dify_conversations,
    image_proxy,
    diagrams,
    workshop_ws,
)
from . import config

logger = logging.getLogger(__name__)

KNOWLEDGE_SPACE_MODULE = None
if app_config.FEATURE_KNOWLEDGE_SPACE:
    try:
        from . import knowledge_space as KNOWLEDGE_SPACE_MODULE
    except Exception as e:
        KNOWLEDGE_SPACE_MODULE = None
        logger.debug("[API] Failed to import knowledge_space router: %s", e, exc_info=True)
else:
    logger.debug("[API] Knowledge Space feature disabled via FEATURE_KNOWLEDGE_SPACE flag")

# Create main router with prefix and tags
router = APIRouter(prefix="/api", tags=["api"])

# Include all sub-routers
router.include_router(config.router)
router.include_router(diagram_generation.router)
router.include_router(png_export.router)
router.include_router(sse_streaming.router)
router.include_router(llm_operations.router)
router.include_router(frontend_logging.router)
router.include_router(layout.router)
router.include_router(feedback.router)
router.include_router(dify_files.router)
router.include_router(dify_conversations.router)
router.include_router(image_proxy.router)
router.include_router(diagrams.router)
router.include_router(workshop_ws.router)

# Knowledge Space router (has its own prefix)
if KNOWLEDGE_SPACE_MODULE is not None:
    router.include_router(KNOWLEDGE_SPACE_MODULE.router)
    logger.info("[API] Knowledge Space router registered at /api/knowledge-space")
else:
    if app_config.FEATURE_KNOWLEDGE_SPACE:
        logger.warning(
            "[API] Knowledge Space router NOT registered - import failed or router is None. "
            "Check DEBUG logs for details. This may be due to missing dependencies (Qdrant, Celery)."
        )
    else:
        logger.debug("[API] Knowledge Space router NOT registered - feature disabled")

__all__ = ["router"]
