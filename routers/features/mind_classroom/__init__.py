"""Mind Classroom lecture job routes."""

from __future__ import annotations

from fastapi import APIRouter

from routers.features.mind_classroom.assets import router as assets_router
from routers.features.mind_classroom.routes import router as job_routes

router = APIRouter(prefix="/api/mind-classroom", tags=["MindClassroom"])
router.include_router(job_routes)
router.include_router(assets_router)

__all__ = ["router"]
