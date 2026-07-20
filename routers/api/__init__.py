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

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import importlib
import logging

from fastapi import APIRouter

from . import (
    activity,
    asr_realtime_ws,
    canvas_translate,
    client_bundles,
    config,
    diagram_generation,
    diagram_node_ops,
    diagrams,
    diagram_folders,
    dify_conversations,
    dify_files,
    feedback,
    frontend_logging,
    image_proxy,
    live_translate_ws,
    llm_operations,
    mindmate_export,
    mindmate_export_dumps,
    mindmate_export_jobs,
    png_export,
    sse_streaming,
    web_content_generation,
    workshop_ws,
)

logger = logging.getLogger(__name__)

# Always import when possible; feature_flag_gate + per-route checks enforce FEATURE_*.
KNOWLEDGE_SPACE_MODULE = None
try:
    from . import knowledge_space as KNOWLEDGE_SPACE_MODULE
except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as e:
    KNOWLEDGE_SPACE_MODULE = None
    logger.debug("[API] Failed to import knowledge_space router: %s", e, exc_info=True)

DOC_SUMMARY_MODULE = None
try:
    DOC_SUMMARY_MODULE = importlib.import_module("routers.api.doc_summary")
except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as e:
    DOC_SUMMARY_MODULE = None
    logger.debug("[API] Failed to import doc_summary router: %s", e, exc_info=True)

MINDBOT_MODULE = None
try:
    from . import mindbot as MINDBOT_MODULE
except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as e:
    MINDBOT_MODULE = None
    logger.debug("[API] Failed to import mindbot router: %s", e, exc_info=True)

mindmate_collab_routes_module = None
mindmate_collab_ws_module = None
mindmate_notify_ws_module = None
try:
    from . import mindmate_collab_routes as mindmate_collab_routes_module
    from . import mindmate_collab_ws as mindmate_collab_ws_module
    from . import mindmate_notify_ws as mindmate_notify_ws_module
except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as e:
    mindmate_collab_routes_module = None
    mindmate_collab_ws_module = None
    mindmate_notify_ws_module = None
    logger.debug("[API] Failed to import mindmate collab routers: %s", e, exc_info=True)

# Create main router with prefix and tags
router = APIRouter(prefix="/api", tags=["api"])

# Include all sub-routers
router.include_router(config.router)
router.include_router(activity.router)
router.include_router(client_bundles.router)
router.include_router(diagram_generation.router)
router.include_router(canvas_translate.router)
router.include_router(web_content_generation.router)
router.include_router(png_export.router)
router.include_router(sse_streaming.router)
router.include_router(llm_operations.router)
router.include_router(frontend_logging.router)
router.include_router(feedback.router)
router.include_router(dify_files.router)
router.include_router(dify_conversations.router)
router.include_router(image_proxy.router)
router.include_router(mindmate_export.router)
router.include_router(mindmate_export_dumps.router)
router.include_router(mindmate_export_jobs.router)
router.include_router(diagrams.router)
router.include_router(diagram_folders.router)
router.include_router(diagram_node_ops.router)
router.include_router(workshop_ws.router)
if mindmate_collab_routes_module is not None:
    router.include_router(mindmate_collab_routes_module.router)
if mindmate_collab_ws_module is not None:
    router.include_router(mindmate_collab_ws_module.router)
if mindmate_notify_ws_module is not None:
    router.include_router(mindmate_notify_ws_module.router)
router.include_router(asr_realtime_ws.router)
router.include_router(live_translate_ws.router)

# Knowledge Space router (has its own prefix)
if KNOWLEDGE_SPACE_MODULE is not None:
    router.include_router(KNOWLEDGE_SPACE_MODULE.router)
    logger.info("[API] Knowledge Space router registered at /api/knowledge-space")
else:
    logger.warning(
        "[API] Knowledge Space router NOT registered - import failed or router is None. "
        "Check DEBUG logs for details. This may be due to missing dependencies (Qdrant, Celery)."
    )

# Document Summary — short /api/doc-summary/* paths (split from knowledge-space URLs)
if DOC_SUMMARY_MODULE is not None:
    router.include_router(DOC_SUMMARY_MODULE.router)
    logger.info("[API] Document Summary router registered at /api/doc-summary")
else:
    logger.warning("[API] Document Summary router NOT registered - import failed or router is None.")

if MINDBOT_MODULE is not None:
    router.include_router(MINDBOT_MODULE.router)
    logger.info("[API] MindBot router registered at /api/mindbot")
else:
    logger.warning("[API] MindBot router NOT registered - import failed or router is None.")

if mindmate_collab_routes_module is None:
    logger.warning("[API] MindMate collab routers NOT registered - import failed or router is None.")

__all__ = ["router"]
