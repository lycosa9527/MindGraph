"""Mind Classroom job enqueue, SSE watch, cancel, and by-diagram lookup."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.celery import celery_app
from models.domain.auth import User
from models.domain.mind_classroom import MindClassroomJob
from repositories.mind_classroom_repo import MindClassroomJobRepository, MindClassroomSlideRepository
from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from routers.auth.dependencies import get_async_db_with_request_rls, get_current_user
from routers.features.zhihui.routes import _conversation_list_item, _generation_payload
from services.mind_classroom.celery_log import log_classroom_celery
from services.mind_classroom.diagram_spec import load_owned_diagram_spec
from services.mind_classroom.enqueue import ClassroomJobsBusy, create_and_enqueue_job
from services.mind_classroom.job_events import publish_classroom_job_snapshot
from services.mind_classroom.job_payload import job_payload
from services.mind_classroom.job_stream import classroom_job_stream_response
from services.mind_classroom.progress_log import job_elapsed_seconds, log_job_poll
from services.mind_classroom.queue_dispatch import ensure_queued_dispatch, task_name_for_settings
from services.mind_classroom.storage import delete_key
from services.mind_classroom.transcript_persist import (
    ensure_transcript_on_server,
    transcript_key_from_result,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

router = APIRouter()

_MODES = frozenset({"canvas_tour", "slide_deck"})
_MASTERY = frozenset({"first_look", "review", "teach"})
_TONES = frozenset(
    {
        "classroom",
        "story",
        "dialogue",
        "socratic",
        "fast",
        "close_read",
        "examples",
        "exam_outline",
    }
)
_SCOPES = frozenset({"main_branch", "each_node"})
_STYLES = frozenset({"general", "chalkboard", "comic", "handdrawn"})
_AUDIENCE = frozenset({"general", "primary", "junior", "senior", "university", "adult", "expert"})
_STALE_MINUTES = 15


class ClassroomJobRequest(BaseModel):
    """Start a canvas-tour or slide-deck lecture job."""

    mode: str = Field(..., min_length=1, max_length=32)
    spec_snapshot: dict[str, Any] = Field(default_factory=dict)
    diagram_id: Optional[str] = Field(default=None, max_length=36)
    mastery: str = Field(default="first_look", max_length=32)
    tone: str = Field(default="classroom", max_length=32)
    tour_scope: str = Field(default="main_branch", max_length=32)
    slide_style: str = Field(default="general", max_length=32)
    audience_level: str = Field(default="", max_length=64)
    audience_title: str = Field(default="", max_length=128)
    language: str = Field(default="zh", max_length=16)
    llm_model: str = Field(default="", max_length=64)
    reuse: bool = True


def _normalize_settings(body: ClassroomJobRequest) -> dict[str, Any]:
    mode = body.mode.strip()
    if mode not in _MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mode")
    mastery = body.mastery.strip() if body.mastery in _MASTERY else "first_look"
    tone = body.tone.strip() if body.tone in _TONES else "classroom"
    scope = body.tour_scope.strip() if body.tour_scope in _SCOPES else "main_branch"
    style = body.slide_style.strip() if body.slide_style in _STYLES else "general"
    audience = body.audience_level.strip() if body.audience_level in _AUDIENCE else "general"
    return {
        "mode": mode,
        "mastery": mastery,
        "tone": tone,
        "tour_scope": scope,
        "slide_style": style,
        "audience_level": audience,
        "audience_title": (body.audience_title or "").strip()[:128],
        "language": (body.language or "zh").strip() or "zh",
        "llm_model": (body.llm_model or "").strip()[:64],
    }


async def _sweep_stale(user_id: int) -> None:
    try:
        async with system_rls_session() as db:
            repo = MindClassroomJobRepository(db)
            marked, task_ids, job_ids = await repo.mark_stale_active_jobs(
                max_age_minutes=_STALE_MINUTES,
                user_id=user_id,
            )
        if marked:
            logger.info("[MindClassroom] Marked %s stale job(s) user=%s", marked, user_id)
        for job_id in job_ids:
            await publish_classroom_job_snapshot(job_id)
        for task_id in task_ids:
            try:
                await asyncio.to_thread(celery_app.control.revoke, task_id, terminate=False)
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.warning("[MindClassroom] Stale revoke failed task=%s err=%s", task_id, exc)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindClassroom] Stale sweep failed user=%s: %s", user_id, exc)


async def _refresh_queued_job(row: MindClassroomJob, db: AsyncSession) -> MindClassroomJob:
    if row.status != "queued":
        return row
    await ensure_queued_dispatch(row.id, task_name_for_settings(row.settings))
    await db.refresh(row)
    return row


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def start_classroom_job(
    body: ClassroomJobRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a lecture job and enqueue Celery."""
    user_id = int(current_user.id)
    await _sweep_stale(user_id)
    spec = body.spec_snapshot if isinstance(body.spec_snapshot, dict) else {}
    if not spec.get("nodes"):
        diagram_id = (body.diagram_id or "").strip()
        if not diagram_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec_snapshot.nodes required")
        try:
            spec = await load_owned_diagram_spec(diagram_id, user_id)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    settings = _normalize_settings(body)
    org_id = getattr(current_user, "organization_id", None)
    try:
        result = await create_and_enqueue_job(
            user_id=user_id,
            spec_snapshot=spec,
            settings=settings,
            organization_id=int(org_id) if org_id is not None else None,
            diagram_id=(body.diagram_id or "").strip() or None,
            reuse=body.reuse,
        )
    except ClassroomJobsBusy as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        if exc.job_id:
            detail["job_id"] = exc.job_id
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/jobs/by-diagram/{diagram_id}")
async def get_job_by_diagram(
    diagram_id: str,
    request: Request,
    mode: Optional[str] = Query(default=None, max_length=32),
    llm_model: Optional[str] = Query(default=None, max_length=64),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """Latest classroom job for a diagram. Default mode is slide_deck (ZhiHui)."""
    cleaned = diagram_id.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    user_id = int(current_user.id)
    repo = MindClassroomJobRepository(db)
    wanted = mode.strip() if mode and mode.strip() in _MODES else "slide_deck"
    row = await repo.latest_job_for_diagram(
        user_id=user_id,
        diagram_id=cleaned,
        mode=wanted,
        llm_model=(llm_model or "").strip() or None,
    )
    if row is not None:
        row = await _refresh_queued_job(row, db)
        await ensure_transcript_on_server(row.result_json)
        slides = list(await MindClassroomSlideRepository(db).list_by_job(row.id))
        return job_payload(row, request, slides=slides)

    conv_repo = ZhihuiConversationRepository(db)
    legacy = await conv_repo.get_latest_diagram_conversation(user_id=user_id, diagram_id=cleaned)
    if legacy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    gen_repo = ZhihuiGenerationRepository(db)
    gens = list(await gen_repo.list_by_conversation(legacy.id))
    cover = gens[0].cos_logical_key if gens else None
    payload = _conversation_list_item(legacy, request, cover_key=cover, slide_count=len(gens))
    payload["legacy_zhihui"] = True
    payload["lesson_plan_json"] = getattr(legacy, "lesson_plan_json", None)
    payload["generations"] = [_generation_payload(gen, request) for gen in gens]
    return payload


@router.get("/jobs/{job_id}/stream")
async def stream_classroom_job(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> Any:
    """SSE progress for one classroom job. Redis pub/sub; no poll loop."""
    return await classroom_job_stream_response(request, db, job_id, current_user)


@router.get("/jobs/{job_id}")
async def get_classroom_job(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """Poll job status, steps, and slides."""
    repo = MindClassroomJobRepository(db)
    row = await repo.get_by_uuid(job_id)
    if row is None or row.user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row = await _refresh_queued_job(row, db)
    await ensure_transcript_on_server(row.result_json)
    slides = list(await MindClassroomSlideRepository(db).list_by_job(job_id))
    progress = row.progress if isinstance(row.progress, dict) else None
    log_job_poll(
        row.id,
        status=str(row.status or ""),
        progress=progress,
        elapsed_s=job_elapsed_seconds(row),
    )
    return job_payload(row, request, slides=slides)


@router.post("/jobs/{job_id}/cancel")
async def cancel_classroom_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, Any]:
    """Cancel an in-flight job and revoke Celery."""
    repo = MindClassroomJobRepository(db)
    row = await repo.get_by_uuid(job_id)
    if row is None or row.user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    task_id = row.celery_task_id
    did_cancel = row.status in ("queued", "planning", "generating")
    if did_cancel:
        await repo.update_job(
            job_id,
            status="cancelled",
            current_stage="cancelled",
            progress={"phase": "cancelled"},
            error_message="Cancelled by user",
            finished=True,
            commit=True,
        )
    if task_id:
        try:
            await asyncio.to_thread(celery_app.control.revoke, task_id, terminate=False)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[MindClassroom] Cancel revoke failed task=%s err=%s", task_id, exc)
    if did_cancel or task_id:
        log_classroom_celery(
            "revoke",
            job_id=job_id,
            celery_task_id=task_id,
            status="cancelled" if did_cancel else row.status,
            detail="reason=user",
        )
    if did_cancel:
        await publish_classroom_job_snapshot(job_id)
    return {"id": job_id, "status": "cancelled"}


@router.delete("/jobs/{job_id}")
async def delete_classroom_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict[str, str]:
    """Cancel if active, then delete job and slides."""
    await cancel_classroom_job(job_id, current_user=current_user, db=db)
    repo = MindClassroomJobRepository(db)
    slide_repo = MindClassroomSlideRepository(db)
    row = await repo.get_by_uuid(job_id)
    transcript_key = transcript_key_from_result(getattr(row, "result_json", None) if row else None)
    keep_shared_transcript = False
    if transcript_key and row is not None and row.diagram_id:
        row_mode = (row.settings or {}).get("mode")
        row_llm = (row.settings or {}).get("llm_model")
        siblings = await repo.list_jobs_for_diagram(
            user_id=int(row.user_id),
            diagram_id=str(row.diagram_id),
            mode=str(row_mode) if row_mode else None,
            llm_model=str(row_llm).strip() if row_llm else None,
        )
        keep_shared_transcript = any(
            sibling.id != job_id and transcript_key_from_result(sibling.result_json) == transcript_key
            for sibling in siblings
        )
    keys = await slide_repo.delete_by_job(job_id, commit=False)
    deleted = await repo.delete_job(job_id, commit=True)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if transcript_key and not keep_shared_transcript:
        keys.append(transcript_key)
    for key in keys:
        await delete_key(key)
    return {"id": job_id, "status": "deleted"}
