"""Tencent Cloud VOD (云点播) admin catalog API."""

from fastapi import APIRouter

from routers.features.vod.routes import router as vod_routes

router = APIRouter(prefix="/api/vod", tags=["VOD"])
router.include_router(vod_routes)
