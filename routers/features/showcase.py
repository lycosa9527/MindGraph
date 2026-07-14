"""Showcase router — moderated public teaching case gallery."""

from __future__ import annotations

from fastapi import APIRouter

from routers.features.showcase_common import (
    CaseReviewBody,
    _delete_case_post_in_session,
    _format_gallery_items,
    _format_post,
    _load_post_for_format,
    _review_case_post_handler,
)
from routers.features.showcase_routes_actions import router as actions_router
from routers.features.showcase_routes_feed import router as feed_router
from routers.features.showcase_routes_posts import router as posts_router
from routers.features.showcase_routes_uploads import router as uploads_router

router = APIRouter(prefix="/api/showcase", tags=["Showcase"])
router.include_router(feed_router)
router.include_router(posts_router)
router.include_router(actions_router)
router.include_router(uploads_router)

__all__ = [
    "CaseReviewBody",
    "_delete_case_post_in_session",
    "_format_gallery_items",
    "_format_post",
    "_load_post_for_format",
    "_review_case_post_handler",
    "router",
]
