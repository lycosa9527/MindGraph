"""
Maite Learning targeted remedy endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import MAITE_DOMAIN_ERRORS, organization_id_for, raise_maite_http_error
from services.maite.domain.remedy_service import RemedyService
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class RemedySubmissionCreate(BaseModel):
    """Student remedy task submission."""

    student_response: str = Field(min_length=1)
    student_confidence: Literal["unclear", "partial", "clear"] = "partial"


def _schedule_remedy(user: User, request: Request, session_id: int, action: str, task_id: int | None = None) -> None:
    details: dict[str, Any] = {"action": action, "session_id": session_id}
    if task_id is not None:
        details["task_id"] = task_id
    schedule_module_activity(
        user=user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details=details,
        detail=f"remedy:{action}:{session_id}",
        usage_source="mindgraph",
        usage_action="maite_remedy",
        title=f"maite:remedy:{action}",
        conversation_id=str(session_id),
    )


@router.post("/inquiry/{session_id}/remedy")
async def generate_remedy_tasks(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Create remedy tasks from the finalized diagnosis block report."""
    _schedule_remedy(current_user, request, session_id, "generate")
    service = RemedyService(db)
    try:
        return await service.create_overview_from_report(session_id, user_id=current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/remedy/{task_id}/prepare")
async def prepare_remedy_task(
    session_id: int,
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Prepare LLM remedy prompt material for a task."""
    _schedule_remedy(current_user, request, session_id, "prepare", task_id)
    service = RemedyService(db)
    try:
        return await service.prepare_task(
            task_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/inquiry/{session_id}/remedy/{task_id}/prepare",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/remedy/{task_id}/material")
async def generate_remedy_material(
    session_id: int,
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate supplemental remedy material (reuses prepare pipeline)."""
    _schedule_remedy(current_user, request, session_id, "material", task_id)
    service = RemedyService(db)
    try:
        return await service.prepare_task(
            task_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/inquiry/{session_id}/remedy/{task_id}/material",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/remedy/{task_id}/submit")
async def submit_remedy_task(
    session_id: int,
    task_id: int,
    payload: RemedySubmissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit student remedy response and receive AI feedback."""
    _schedule_remedy(current_user, request, session_id, "submit", task_id)
    service = RemedyService(db)
    try:
        return await service.submit_task(
            task_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_response=payload.student_response,
            student_confidence=payload.student_confidence,
            endpoint_path=f"/api/maite/inquiry/{session_id}/remedy/{task_id}/submit",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/remedy/{task_id}/reevaluate")
async def reevaluate_remedy_task(
    session_id: int,
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Re-run remedy preparation/feedback for legacy clients."""
    _schedule_remedy(current_user, request, session_id, "reevaluate", task_id)
    service = RemedyService(db)
    try:
        return await service.prepare_task(
            task_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/inquiry/{session_id}/remedy/{task_id}/reevaluate",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
