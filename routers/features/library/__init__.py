"""Library Router Module.

API endpoints for public library feature with image-based viewing and danmaku comments.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from fastapi import APIRouter

from .documents import router as documents_router
from .danmaku import router as danmaku_router
from .bookmarks import router as bookmarks_router


router = APIRouter(prefix="/api/library", tags=["Library"])

# Include all sub-routers
router.include_router(documents_router)
router.include_router(danmaku_router)
router.include_router(bookmarks_router)
