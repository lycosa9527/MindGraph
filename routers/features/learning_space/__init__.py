"""Learning Space feature router package."""

from fastapi import APIRouter

from routers.features.learning_space.images import router as learning_space_images
from routers.features.learning_space.routes import router as learning_space_routes

router = APIRouter(prefix="/api/learning-space", tags=["Learning Space"])
router.include_router(learning_space_routes)
router.include_router(learning_space_images)
