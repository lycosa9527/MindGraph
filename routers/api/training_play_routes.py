"""Play and step a persisted training course on a live session."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain.auth import User
from services.features.training.courses.repository import get_course
from services.features.training.courses.seed import ensure_double_bubble_seed
from services.features.training.courses.serialize import serialize_course, snapshot_step_payload
from services.features.training.payloads import FreeBody, PlayBody, StepBody, snapshot_from_session
from services.features.training.play_advance import resolve_play_cursor
from services.features.training.permissions import can_lead_training
from services.features.training.session_store import (
    TrainingSessionError,
    bump_and_save,
    require_owner_active,
)
from services.features.training.sse import publish_event
from utils.auth import get_current_user
from utils.db.session_open import system_rls_session

router = APIRouter()


def _http_for_session_error(exc: TrainingSessionError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message, **exc.extras}
    if exc.code == "rate_limited":
        return HTTPException(status_code=429, detail=detail)
    if exc.code == "not_owner":
        return HTTPException(status_code=403, detail=detail)
    if exc.code == "not_found":
        return HTTPException(status_code=404, detail=detail)
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
        "diagram_type": diagram,
        "topic_options": options,
        "pull_users": True,
    }


async def _load_serialized_steps(course_id: str) -> list[dict]:
    async with system_rls_session() as db:
        await ensure_double_bubble_seed(db)
        await db.commit()
        course = await get_course(db, course_id)
        if course is None:
            return []
        return serialize_course(course, include_steps=True).get("steps") or []


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
    try:
        updated = await bump_and_save(session, extra=extras, rate_limit_steer=True)
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
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
    try:
        updated = await bump_and_save(session, extra=extras, rate_limit_steer=True)
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
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
    try:
        updated = await bump_and_save(
            session,
            extra={"pull_users": not body.free},
            rate_limit_steer=True,
        )
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await publish_event(org_id, "seq", {"seq": int(updated.get("seq") or 0)})
    return snapshot_from_session(updated, viewer_user_id=int(current_user.id))
