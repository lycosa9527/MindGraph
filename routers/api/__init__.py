"""
API Router Package
==================

Aggregates all API route modules into a single router.

Usage:
    from routers import api
    app.include_router(api.router)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

# Import all sub-routers
from . import (
    diagram_generation,
    png_export,
    sse_streaming,
    llm_operations,
    frontend_logging,
    layout,
    feedback,
)

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

__all__ = ["router"]


