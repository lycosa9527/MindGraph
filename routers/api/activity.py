"""User Activity Logging API Router.

API endpoints for logging user activities (teacher usage tracking):
- POST /api/activity/diagram_export - Log diagram export event

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


class DiagramExportLogRequest(BaseModel):
    """Request body for diagram export log."""

    format: str = "png"  # png, svg, pdf, json


@router.post("/activity/diagram_export")
async def log_diagram_export(
    _req: DiagramExportLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Log diagram export event for teacher usage analytics.

    Called by frontend after successful client-side export (PNG/SVG/PDF/JSON).
    """
    if getattr(current_user, "role", None) != "user":
        return {"status": "skipped", "reason": "not_teacher"}

    try:
        log_entry = UserActivityLog(
            user_id=current_user.id,
            activity_type="diagram_export",
            created_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()
        return {"status": "logged"}
    except Exception as e:
        logger.debug("Failed to log diagram_export: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "error"}
