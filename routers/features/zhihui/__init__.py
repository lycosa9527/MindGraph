"""ZhiHui (智绘) history and asset routes."""

from __future__ import annotations

from fastapi import APIRouter

from routers.features.zhihui.routes import router as zhihui_routes

router = APIRouter(prefix="/api/zhihui", tags=["ZhiHui"])
router.include_router(zhihui_routes)

__all__ = ["router"]
