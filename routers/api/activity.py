"""User Activity Logging API Router.

API endpoints for logging user activities (teacher usage tracking):
- POST /api/activity/diagram_export - Log diagram export event

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from services.auth.thinking_coin.client_event_service import load_user_org
from services.auth.thinking_coin.event_hub import mutation_to_footer, track_client_event
from services.monitoring.module_activity import schedule_module_activity
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user, is_teacher
from utils.auth.thinking_coin_config import EVENT_DIAGRAM_EXPORT

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


class DiagramExportLogRequest(BaseModel):
    """Request body for diagram export log."""

    format: str = "png"  # png, svg, pdf, json


@router.post("/activity/diagram_export")
async def log_diagram_export(
    req: DiagramExportLogRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Log diagram export event for teacher usage analytics.

    Called by frontend after successful client-side export (PNG/SVG/PDF/JSON).
    """
    status = "skipped"
    reason: str | None = None
    export_format = (req.format or "png").strip().lower() or "png"

    schedule_module_activity(
        user=current_user,
        module="canvas",
        redis_activity_type="export_png",
        request=request,
        details={"format": export_format},
        detail=f"export={export_format}",
        usage_source="mindgraph",
        usage_action="export_diagram",
        title=f"export_{export_format}",
        prompt_preview=f"format={export_format}",
    )

    if is_teacher(current_user):
        try:
            log_entry = UserActivityLog(
                user_id=current_user.id,
                activity_type="diagram_export",
                created_at=datetime.now(UTC),
            )
            db.add(log_entry)
            await db.commit()
            status = "logged"
        except DATABASE_ERRORS as exc:
            logger.debug("Failed to log diagram_export: %s", exc)
            try:
                await db.rollback()
            except DATABASE_ERRORS as rollback_exc:
                logger.debug("Rollback after export log failure: %s", rollback_exc)
            status = "error"
    else:
        reason = "not_teacher"

    thinking_coins: dict[str, Any] = {}
    try:
        org = await load_user_org(current_user)
        mutation = await track_client_event(db, current_user, org, EVENT_DIAGRAM_EXPORT)
        thinking_coins = mutation_to_footer(mutation)
        if mutation.credited > 0 and status == "skipped":
            status = "rewarded"
    except DATABASE_ERRORS as exc:
        logger.debug("Failed to claim diagram_export thinking coins: %s", exc)

    payload: dict[str, Any] = {"status": status}
    if reason is not None:
        payload["reason"] = reason
    if thinking_coins.get("eligible"):
        payload["thinking_coins"] = thinking_coins
    return payload
