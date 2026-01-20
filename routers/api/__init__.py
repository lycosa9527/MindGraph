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
import sys

from fastapi import APIRouter

from . import (
    config,
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
)

try:
    from . import knowledge_space
except Exception:
    knowledge_space = None

logger = logging.getLogger(__name__)

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

# Knowledge Space router (has its own prefix)
if knowledge_space is not None:
    router.include_router(knowledge_space.router)
    logger.info("Knowledge Space router registered at /api/knowledge-space")
    print("INFO: Knowledge Space router registered at /api/knowledge-space", file=sys.stderr)
else:
    logger.warning("Knowledge Space router NOT registered - import failed or router is None")
    print("WARNING: Knowledge Space router NOT registered - import failed or router is None", file=sys.stderr)

__all__ = ["router"]
