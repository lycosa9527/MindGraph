

from fastapi import APIRouter
import logging
import sys

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
)

logger = logging.getLogger(__name__)
# Ensure logger has at least a basic handler for early import errors
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)  # Only show warnings/errors during import
    import traceback
    traceback.print_exc(file=sys.stderr)
    knowledge_space = None

# Create main router with prefix and tags
router = APIRouter(prefix="/api", tags=["api"])

# Include all sub-routers
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
    success_msg = "Knowledge Space router registered at /api/knowledge-space"
    logger.info(success_msg)
    print(f"INFO: {success_msg}", file=sys.stderr)  # Fallback to stderr
else:
    warning_msg = "Knowledge Space router NOT registered - import failed or router is None"
    logger.warning(warning_msg)
    print(f"WARNING: {warning_msg}", file=sys.stderr)  # Fallback to stderr

__all__ = ["router"]

