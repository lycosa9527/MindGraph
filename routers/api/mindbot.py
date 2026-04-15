"""MindBot: DingTalk HTTP webhooks and admin CRUD for per-organization config.

This module aggregates the callback and admin sub-routers into a single
``router`` instance registered by ``routers.api.__init__``.

Backward-compatible re-exports keep existing test imports working.
"""

from __future__ import annotations

from fastapi import APIRouter

from routers.api.mindbot_callback import router as _callback_router
from routers.api.mindbot_admin import router as _admin_router
from routers.api.mindbot_helpers import _callback_metrics_snapshot_for_user
from routers.api.mindbot_models import MindbotUsageEventItem

router = APIRouter(prefix="/mindbot", tags=["mindbot"])
router.include_router(_callback_router)
router.include_router(_admin_router)

__all__ = [
    "router",
    "_callback_metrics_snapshot_for_user",
    "MindbotUsageEventItem",
]
