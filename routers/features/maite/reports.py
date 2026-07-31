"""
Mate Learning session report endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import (
    MAITE_DOMAIN_ERRORS,
    enforce_maite_llm_rate_limit,
    organization_id_for,
    raise_maite_http_error,
)
from services.maite.domain.report_service import ReportService
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports/{session_id}")
async def get_session_report(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return persisted report or build one on first access."""
    await enforce_maite_llm_rate_limit(current_user, request)
    schedule_module_activity(
        user=current_user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details={"action": "report", "session_id": session_id},
        detail=f"report:{session_id}",
        usage_source="mindgraph",
        usage_action="maite_report",
        title=f"maite:report:{session_id}",
        conversation_id=str(session_id),
    )
    service = ReportService(db)
    try:
        existing = await service.get_report(session_id, user_id=current_user.id)
        if existing.get("report_markdown"):
            logger.info(
                "[Maite] Report cache hit user=%s session=%s",
                current_user.id,
                session_id,
            )
            return existing
        report = await service.build_report(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/reports/{session_id}",
        )
        logger.info(
            "[Maite] Report built user=%s session=%s",
            current_user.id,
            session_id,
        )
        return report
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
