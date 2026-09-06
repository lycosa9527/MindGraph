"""Play and step a persisted training course on a live session."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain.auth import User
from services.features.training.activity_store import activity_summary
from services.features.training.courses.play_cache import load_serialized_steps
from services.features.training.courses.serialize import snapshot_step_payload
from services.features.training.payloads import FreeBody, PlayBody, StepBody, snapshot_from_session
from services.features.training.play_advance import resolve_play_cursor
from services.features.training.permissions import can_lead_training
from services.features.training.session_store import (
    TrainingSessionError,
    bump_and_save,
    require_owner_active,
)
from services.features.training.sse import publish_event
from services.features.training.training_logger import log_training
from utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _http_for_session_error(exc: TrainingSessionError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message, **exc.extras}
    if exc.code == "rate_limited":
        return HTTPException(status_code=429, detail=detail)
    if exc.code == "not_owner":
        return HTTPException(status_code=403, detail=detail)
    if exc.code == "not_found":
        return HTTPException(status_code=404, detail=detail)
    if exc.code == "seq_conflict":
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=503, detail=detail)


async def _owner_session(org_id: int, session_id: str, user: User) -> dict:
    if not await can_lead_training(user, org_id):
        raise HTTPException(status_code=403, detail="Training lead access required")
    try:
        session = await require_owner_active(org_id, int(user.id))
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    if str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _step_extras(course_id: str, index: int, step_body: dict) -> dict:
    is_canvas = step_body.get("type") == "canvas" or step_body.get("page_key") == "canvas"
    diagram = step_body.get("diagram_type") if is_canvas else None
    options = step_body.get("topic_options") or []
    return {
        "course_id": course_id,
        "step_index": index,
        "step": snapshot_step_payload(step_body),
        "instructor_notes": str(step_body.get("notes") or ""),
        "diagram_type": diagram,
        "topic_options": options,
        "pull_users": True,
    }


async def _load_serialized_steps(course_id: str) -> list[dict]:
    return await load_serialized_steps(course_id)


async def _log_teacher_pull(event: str, session: dict, user: User, **fields: Any) -> None:
    org_id = int(session.get("org_id") or 0)
    summary = await activity_summary(org_id) if org_id else {"online": 0, "generating": 0}
    log_training(
        logger,
        event,
        actor_id=int(user.id),
        org_id=org_id,
        session_id=str(session.get("session_id") or ""),
        course_id=str(session.get("course_id") or ""),
        teachers=int(session.get("confirm_teacher_count") or 0),
        online=int(summary.get("online") or 0),
        generating=int(summary.get("generating") or 0),
        pull_users=bool(session.get("pull_users")),
        seq=int(session.get("seq") or 0),
        **fields,
    )


@router.post("/sessions/{session_id}/play")
async def play_course(
    session_id: str,
    body: PlayBody,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Bind a course and jump to step 0."""
    session = await _owner_session(org_id, session_id, current_user)
    steps = await _load_serialized_steps(body.course_id)
    if not steps:
        raise HTTPException(status_code=404, detail="Course not found or has no steps")
    extras = _step_extras(body.course_id, 0, steps[0])
    extras["step"]["mark_step"] = 1
    extras["step_count"] = len(steps)
    started = time.monotonic()
    try:
        updated = await bump_and_save(session, extra=extras, rate_limit_steer=True)
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
    step = steps[0]
    await _log_teacher_pull(
        "course_play",
        updated,
        current_user,
        step_index=0,
        steps=len(steps),
        step_type=str(step.get("type") or ""),
        page_key=str(step.get("page_key") or ""),
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
    return snapshot_from_session(updated, viewer_user_id=int(current_user.id))


@router.post("/sessions/{session_id}/step")
async def step_course(
    session_id: str,
    body: StepBody,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Jump to an absolute index or apply a delta."""
    session = await _owner_session(org_id, session_id, current_user)
    course_id = str(session.get("course_id") or "")
    if not course_id:
        raise HTTPException(status_code=400, detail="No course is playing")
    steps = await _load_serialized_steps(course_id)
    if not steps:
        raise HTTPException(status_code=404, detail="Course not found or has no steps")
    current = int(session.get("step_index") or 0)
    live_step = session.get("step") if isinstance(session.get("step"), dict) else None
    if body.index is not None:
        target = body.index
        mark_at = 1
    else:
        target, mark_at = resolve_play_cursor(steps, current, live_step, int(body.delta or 0))
    if target < 0 or target >= len(steps):
        raise HTTPException(status_code=400, detail="Step index out of range")
    extras = _step_extras(course_id, target, steps[target])
    extras["step"]["mark_step"] = mark_at
    extras["step_count"] = len(steps)
    started = time.monotonic()
    try:
        updated = await bump_and_save(session, extra=extras, rate_limit_steer=True)
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
    step = steps[target]
    await _log_teacher_pull(
        "course_step",
        updated,
        current_user,
        from_index=current,
        step_index=target,
        mark_step=mark_at,
        steps=len(steps),
        step_type=str(step.get("type") or ""),
        page_key=str(step.get("page_key") or ""),
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
    return snapshot_from_session(updated, viewer_user_id=int(current_user.id))


@router.post("/sessions/{session_id}/free")
async def free_teachers(
    session_id: str,
    body: FreeBody,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Keep teachers on this page and let them work, or pull them back."""
    session = await _owner_session(org_id, session_id, current_user)
    started = time.monotonic()
    try:
        updated = await bump_and_save(
            session,
            extra={"pull_users": not body.free},
            rate_limit_steer=True,
        )
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
    event = "teachers_free" if body.free else "teachers_pull"
    await _log_teacher_pull(
        event,
        updated,
        current_user,
        step_index=updated.get("step_index"),
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
    return snapshot_from_session(updated, viewer_user_id=int(current_user.id))
