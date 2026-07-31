"""
Maite Learning variant practice endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import MAITE_DOMAIN_ERRORS, organization_id_for, raise_maite_http_error
from services.maite.domain.variant_service import VariantService
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class VariantSubmissionCreate(BaseModel):
    """Student variant transfer submission."""

    student_answer: str = Field(min_length=1)
    student_strategy: str = Field(min_length=1)


def _schedule_variant(user: User, request: Request, session_id: int, action: str, task_id: int | None = None) -> None:
    details: dict[str, Any] = {"action": action, "session_id": session_id}
    if task_id is not None:
        details["task_id"] = task_id
    schedule_module_activity(
        user=user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details=details,
        detail=f"variant:{action}:{session_id}",
        usage_source="mindgraph",
        usage_action="maite_variant",
        title=f"maite:variant:{action}",
        conversation_id=str(session_id),
    )


@router.post("/inquiry/{session_id}/variants")
async def generate_variant_tasks(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Generate four variant practice tasks for a session."""
    _schedule_variant(current_user, request, session_id, "generate")
    service = VariantService(db)
    try:
        return await service.generate_variants(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/inquiry/{session_id}/variants",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/variants/{task_id}/submit")
async def submit_variant_task(
    session_id: int,
    task_id: int,
    payload: VariantSubmissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit variant answer/strategy and receive transfer feedback."""
    _schedule_variant(current_user, request, session_id, "submit", task_id)
    service = VariantService(db)
    try:
        return await service.submit_feedback(
            task_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_answer=payload.student_answer,
            student_strategy=payload.student_strategy,
            endpoint_path=f"/api/maite/inquiry/{session_id}/variants/{task_id}/submit",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
