"""
Market (市场) feature router.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from .admin import router as admin_router
from .router import router as public_router

router = APIRouter(prefix="/api/markets", tags=["Markets"])

router.include_router(public_router)
router.include_router(admin_router)
