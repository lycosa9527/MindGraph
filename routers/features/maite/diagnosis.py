"""
Maite Learning four-stage diagnosis endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.features.maite.helpers import MAITE_DOMAIN_ERRORS, organization_id_for, raise_maite_http_error
from services.maite.domain.diagnosis_service import DiagnosisService
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class DiagnosisStageInput(BaseModel):
    """Student input for a diagnosis stage."""

    student_input: str = ""


class DiagnosisInteractionInput(BaseModel):
    """Stage interaction payload."""

    selected_source_rows: list[str] = Field(default_factory=list)
    student_input: str = ""


class DiagnosisFinalizeInput(BaseModel):
    """Optional explicit block report on finalize."""

    final_block_report: list[dict[str, Any]] = Field(default_factory=list)


class DiagnosisStageFourEvaluateInput(BaseModel):
    """Stage-four evaluation payload."""

    student_input: str = ""
    variant_text: str = ""


def _endpoint(session_id: int, suffix: str) -> str:
    return f"/api/maite/inquiry/{session_id}/diagnose{suffix}"


def _schedule_diagnosis(user: User, request: Request, session_id: int, action: str) -> None:
    schedule_module_activity(
        user=user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details={"action": action, "session_id": session_id},
        detail=f"diagnosis:{action}:{session_id}",
        usage_source="mindgraph",
        usage_action="maite_diagnosis",
        title=f"maite:diagnosis:{action}",
        conversation_id=str(session_id),
    )


def _stage_from_result(result: dict[str, Any], stage_no: int) -> dict[str, Any]:
    stages = result.get("stage_results") or []
    if not isinstance(stages, list):
        return {"stage_no": stage_no, "stage_name": f"stage_{stage_no}", "interactions": []}
    for item in stages:
        if isinstance(item, dict) and item.get("stage") == stage_no:
            return item
    if stages and isinstance(stages[0], dict):
        first = dict(stages[0])
        first["stage"] = stage_no
        return first
    return {"stage_no": stage_no, "stage_name": f"stage_{stage_no}", "interactions": []}


@router.post("/inquiry/{session_id}/diagnose/stage-1")
async def diagnose_stage_1(
    session_id: int,
    payload: DiagnosisStageInput,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run stage-one direction check (via auto diagnosis pipeline)."""
    _schedule_diagnosis(current_user, request, session_id, "stage_1")
    service = DiagnosisService(db)
    try:
        result = await service.auto_diagnose(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_thinking=payload.student_input,
            endpoint_path=_endpoint(session_id, "/stage-1"),
        )
        return _stage_from_result(result, 1)
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/auto")
async def diagnose_auto(
    session_id: int,
    payload: DiagnosisStageInput,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run full auto four-stage diagnosis."""
    _schedule_diagnosis(current_user, request, session_id, "auto")
    service = DiagnosisService(db)
    try:
        return await service.auto_diagnose(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_thinking=payload.student_input,
            endpoint_path=_endpoint(session_id, "/auto"),
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/stage-2/interactions")
async def diagnose_stage_2_interaction(
    session_id: int,
    payload: DiagnosisInteractionInput,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a stage-two knowledge-boundary interaction."""
    _schedule_diagnosis(current_user, request, session_id, "stage_2")
    service = DiagnosisService(db)
    try:
        result = await service.auto_diagnose(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_thinking=payload.student_input,
            endpoint_path=_endpoint(session_id, "/stage-2/interactions"),
        )
        stage = _stage_from_result(result, 2)
        stage["selected_source_rows"] = payload.selected_source_rows
        return stage
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/stage-3/interactions")
async def diagnose_stage_3_interaction(
    session_id: int,
    payload: DiagnosisInteractionInput,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a stage-three step-chain interaction."""
    _schedule_diagnosis(current_user, request, session_id, "stage_3")
    service = DiagnosisService(db)
    try:
        result = await service.auto_diagnose(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_thinking=payload.student_input,
            endpoint_path=_endpoint(session_id, "/stage-3/interactions"),
        )
        stage = _stage_from_result(result, 3)
        stage["selected_source_rows"] = payload.selected_source_rows
        return stage
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/stage-4/generate-variant")
async def diagnose_stage_4_generate_variant(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate the stage-four light variant."""
    _schedule_diagnosis(current_user, request, session_id, "stage_4_generate")
    service = DiagnosisService(db)
    try:
        return await service.generate_stage_four_variant(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=_endpoint(session_id, "/stage-4/generate-variant"),
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/stage-4/evaluate")
async def diagnose_stage_4_evaluate(
    session_id: int,
    payload: DiagnosisStageFourEvaluateInput,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Evaluate student judgement on the stage-four variant."""
    _schedule_diagnosis(current_user, request, session_id, "stage_4_evaluate")
    service = DiagnosisService(db)
    variant_text = payload.variant_text
    if not variant_text:
        prior = await service.generate_stage_four_variant(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path=_endpoint(session_id, "/stage-4/generate-variant"),
        )
        variant_text = str(prior.get("variant_text") or "")
    try:
        return await service.evaluate_stage_four(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            variant_text=variant_text,
            student_judgement=payload.student_input,
            endpoint_path=_endpoint(session_id, "/stage-4/evaluate"),
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/inquiry/{session_id}/diagnose/finalize")
async def diagnose_finalize(
    session_id: int,
    request: Request,
    payload: Optional[DiagnosisFinalizeInput] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Finalize diagnosis block report and advance to remedy."""
    _schedule_diagnosis(current_user, request, session_id, "finalize")
    service = DiagnosisService(db)
    report = payload.final_block_report if payload else []
    if not report:
        existing = await service.auto_diagnose(
            session_id,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            student_thinking="",
            endpoint_path=_endpoint(session_id, "/finalize"),
        )
        report = existing.get("final_block_report") or []
        if not isinstance(report, list):
            report = []
    try:
        return await service.finalize(
            session_id,
            user_id=current_user.id,
            final_block_report=report,
        )
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc
