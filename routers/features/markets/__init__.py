"""Market (市场) feature router."""

from fastapi import APIRouter

from .admin import router as admin_router
from .router import router as public_router

router = APIRouter(prefix="/api/markets", tags=["Markets"])

router.include_router(public_router)
router.include_router(admin_router)
