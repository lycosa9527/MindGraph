"""
Mate Learning inquiry session endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import (
    MAITE_DOMAIN_ERRORS,
    enforce_maite_llm_rate_limit,
    organization_id_for,
    raise_maite_http_error,
)
from services.maite.domain.analysis_service import AnalysisService
from services.maite.domain.assessment_service import AssessmentService
from services.maite.domain.decompose_service import DecomposeService
from services.maite.domain.inquiry_service import InquiryService
from services.maite.schemas.inquiry import SessionCreate, SessionRead, SnapshotRead
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class SelfAssessmentItem(BaseModel):
    """Single mastery self-assessment row."""

    name: str
    category: str
    mastered: bool
    note: str = ""
    student_added: bool = False


class SelfAssessmentCreate(BaseModel):
    """Batch self-assessment submission."""

    items: list[SelfAssessmentItem] = Field(default_factory=list)


class DecomposeSubmissionCreate(BaseModel):
    """Three-table decompose submission."""

    condition_table: list[dict[str, Any]] = Field(default_factory=list)
    step_table: list[dict[str, Any]] = Field(default_factory=list)
    model_table: list[dict[str, Any]] = Field(default_factory=list)


def _schedule_inquiry_activity(user: User, request: Request, action: str, session_id: Optional[int] = None) -> None:
    details: dict[str, Any] = {"action": action}
    if session_id is not None:
        details["session_id"] = session_id
    schedule_module_activity(
        user=user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details=details,
        detail=f"{action}:{session_id}" if session_id else action,
        usage_source="mindgraph",
        usage_action="maite_inquiry",
        title=f"maite:{action}",
        conversation_id=str(session_id) if session_id is not None else None,
    )


@router.post("/inquiry/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_inquiry_session(
    payload: SessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Create a new inquiry session for an owned problem."""
    service = InquiryService(db)
    try:
        created = await service.create_session(
            payload,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
        )
        logger.info(
            "[Maite] User %s created session %s problem=%s mode=%s",
            current_user.id,
            created.id,
            payload.problem_id,
            payload.mode,
        )
        _schedule_inquiry_activity(current_user, request, "create_session", created.id)
        return created
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/inquiry/sessions", response_model=list[SessionRead])
async def list_inquiry_sessions(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionRead]:
    """List inquiry sessions for the authenticated user."""
    service = InquiryService(db)
    try:
        return await service.list_sessions(current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/practice/recent", response_model=list[SessionRead])
async def list_recent_practice(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionRead]:
    """Return recent practice sessions (Redis-cached list)."""
    service = InquiryService(db)
    try:
        return await service.list_sessions(current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/inquiry/sessions/{session_id}", response_model=SessionRead)
async def get_inquiry_session(
    session_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Fetch one inquiry session owned by the caller."""
    service = InquiryService(db)
    try:
        return await service.get_session(session_id, user_id=current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/inquiry/sessions/{session_id}/snapshot", response_model=SnapshotRead)
async def get_inquiry_snapshot(
    session_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> SnapshotRead:
    """Return aggregated session snapshot for the UI."""
    service = InquiryService(db)
    try:
        return await service.get_snapshot(session_id, user_id=current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/sessions/{session_id}/redo", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def redo_inquiry_session(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Start a new version of an existing inquiry session."""
    service = InquiryService(db)
    try:
        created = await service.redo_session(session_id, user_id=current_user.id)
        logger.info(
            "[Maite] User %s redid session %s -> %s",
            current_user.id,
            session_id,
            created.id,
        )
        _schedule_inquiry_activity(current_user, request, "redo_session", created.id)
        return created
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/complete", response_model=SessionRead)
async def complete_inquiry_session(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Mark session complete after required variant submissions."""
    service = InquiryService(db)
    try:
        completed = await service.complete_session(session_id, user_id=current_user.id)
        logger.info(
            "[Maite] User %s completed session %s",
            current_user.id,
            session_id,
        )
        _schedule_inquiry_activity(current_user, request, "complete_session", session_id)
        return completed
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/analysis")
async def analyze_inquiry_session(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run LLM problem analysis for the session problem."""
    await enforce_maite_llm_rate_limit(current_user, request)
    _schedule_inquiry_activity(current_user, request, "analysis", session_id)
    service = AnalysisService(db)
    try:
        return await service.analyze_session(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=f"/api/maite/inquiry/{session_id}/analysis",
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/self-assessment")
async def save_self_assessment(
    session_id: int,
    payload: SelfAssessmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Persist student mastery self-assessment items."""
    _schedule_inquiry_activity(current_user, request, "self_assessment", session_id)
    service = AssessmentService(db)
    try:
        return await service.save_assessment(
            session_id,
            items=[item.model_dump() for item in payload.items],
            user_id=current_user.id,
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/inquiry/{session_id}/decompose-template")
async def get_decompose_template(
    session_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return static three-table decompose template metadata."""
    service = DecomposeService(db)
    try:
        return await service.get_template(session_id, user_id=current_user.id)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/decompose-submission")
async def submit_decompose_tables(
    session_id: int,
    payload: DecomposeSubmissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit reverse-decompose tables for a session."""
    _schedule_inquiry_activity(current_user, request, "decompose_submission", session_id)
    service = InquiryService(db)
    try:
        result = await service.submit_decompose(
            session_id,
            user_id=current_user.id,
            condition_table=payload.condition_table,
            step_table=payload.step_table,
            model_table=payload.model_table,
        )
        logger.info(
            "[Maite] User %s submitted decompose for session %s",
            current_user.id,
            session_id,
        )
        return result
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
