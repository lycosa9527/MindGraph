"""Admin scan that stores missing Learning Space card thumbnails on COS."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth.dependencies import get_async_db_with_request_rls, require_panel_capability
from routers.features.learning_space.schemas import ThumbnailBackfillRequest
from services.learning_space.thumbnail_backfill_scan import backfill_missing_card_thumbnails
from utils.auth.admin_panel_permissions import CAP_TAB_LEARNING_SPACE_EDIT
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter()

_require_ls_edit = require_panel_capability(CAP_TAB_LEARNING_SPACE_EDIT)


@router.post("/admin/thumbnails/backfill")
async def admin_backfill_thumbnails(
    body: ThumbnailBackfillRequest,
    scope: AdminScope = Depends(_require_ls_edit),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
):
    """Scan cards with no COS thumbnail, generate one when needed, and store it."""
    result = await backfill_missing_card_thumbnails(db, skip=set(body.skip))
    logger.info(
        "[LearningSpace] Thumbnail scan actor=%s stored=%s generated=%s remaining=%s",
        scope.actor.id,
        result["stored"],
        result["generated"],
        result["remaining"],
    )
    return result
