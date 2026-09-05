"""
Org training follow REST + SSE routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.api.training_asset_routes import router as training_asset_router
from routers.api.training_course_routes import router as training_course_router
from routers.api.training_play_routes import router as training_play_router
from services.features.training.activity_store import (
    activity_summary,
    clear_activity,
    list_activity,
    touch_activity,
)
from services.features.training.constants import (
    GENERATE_STATES,
    MAX_TOPIC_OPTIONS,
    ROSTER_PAGE_MAX,
    STATE_ENDED,
    STATE_LIVE,
    VALID_DIAGRAM_TYPES,
)
from services.features.training.orgs import count_org_teachers, list_leadable_orgs
from services.features.training.payloads import (
    ActivityBody,
    NavigateBody,
    OptionsBody,
    StartSessionBody,
    command_etag,
    snapshot_from_session,
)
from services.features.training.permissions import (
    can_lead_any_training,
    can_lead_training,
    is_org_teacher_target,
)
from services.features.training.session_store import (
    TrainingSessionError,
    bump_and_save,
    end_session,
    get_instructor_pointer,
    get_session,
    heartbeat,
    maybe_auto_pause,
    pause_session,
    require_owner_active,
    resume_session,
    start_session,
    takeover_session,
)
from services.features.training.sse import iter_org_events, publish_event
from utils.auth import get_current_user
from utils.auth.roles import is_superadmin
from utils.db.session_open import system_rls_session

router = APIRouter(prefix="/training", tags=["training"])
router.include_router(training_course_router)
router.include_router(training_asset_router)
router.include_router(training_play_router)


def _snapshot(session, user: User):
    """Command snapshot with speaker notes only for the session instructor."""
    return snapshot_from_session(session, viewer_user_id=int(user.id))


def _http_for_session_error(exc: TrainingSessionError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message, **exc.extras}
    if exc.code in {"org_busy", "instructor_busy"}:
        return HTTPException(status_code=409, detail=detail)
    if exc.code == "rate_limited":
        return HTTPException(status_code=429, detail=detail)
    if exc.code == "not_owner":
        return HTTPException(status_code=403, detail=detail)
    if exc.code == "not_found":
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=503, detail=detail)


async def _require_leader(user: User, org_id: int) -> None:
    if not await can_lead_training(user, org_id):
        raise HTTPException(status_code=403, detail="Training lead access required")


async def _publish_seq(org_id: int, session: dict) -> None:
    event = "ended" if session.get("state") == STATE_ENDED else "seq"
    await publish_event(org_id, event, {"seq": int(session.get("seq") or 0)})


def _display_name(user: User) -> str:
    return str(getattr(user, "name", None) or f"User {user.id}")


@router.get("/orgs")
async def list_training_orgs(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Organizations the caller may lead."""
    if not can_lead_any_training(current_user):
        raise HTTPException(status_code=403, detail="Training lead access required")
    async with system_rls_session() as db:
        rows, total = await list_leadable_orgs(db, current_user, q=q, limit=limit, offset=offset)
    return {
        "items": [{"id": org.id, "name": org.name, "code": org.code} for org in rows],
        "total": total,
        "limit": min(max(limit, 1), 100),
        "offset": max(offset, 0),
    }


@router.get("/orgs/{org_id}/ready")
async def org_ready(
    org_id: int,
    current_user: User = Depends(get_current_user),
):
    """Teacher totals shown before start confirm."""
    await _require_leader(current_user, org_id)
    async with system_rls_session() as db:
        teacher_total = await count_org_teachers(db, org_id)
    summary = await activity_summary(org_id)
    return {
        "org_id": org_id,
        "teacher_total": teacher_total,
        "online_now": summary["online"],
    }


@router.post("/sessions")
async def create_session(
    body: StartSessionBody,
    current_user: User = Depends(get_current_user),
):
    """Start a live session after confirming the teacher count."""
    await _require_leader(current_user, body.org_id)
    async with system_rls_session() as db:
        teacher_total = await count_org_teachers(db, body.org_id)
    if int(body.confirm_teacher_total) != int(teacher_total):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "confirm_mismatch",
                "message": "Teacher count changed; refresh and confirm again",
                "teacher_total": teacher_total,
            },
        )
    try:
        session = await start_session(
            org_id=body.org_id,
            instructor_id=int(current_user.id),
            instructor_name=_display_name(current_user),
            confirm_teacher_total=teacher_total,
        )
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(body.org_id, session)
    return _snapshot(session, current_user)


@router.get("/sessions/active")
async def active_session(
    org_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """Resume payload for the instructor console."""
    target = org_id
    if target is None:
        pointer = await get_instructor_pointer(int(current_user.id))
        if pointer is None:
            return snapshot_from_session(None)
        target = int(pointer.get("org_id") or 0)
    if not target:
        return snapshot_from_session(None)
    if not await can_lead_training(current_user, target):
        if not is_org_teacher_target(current_user, target):
            raise HTTPException(status_code=403, detail="Training access required")
    session = await get_session(target)
    if session is not None:
        session = await maybe_auto_pause(session)
    return _snapshot(session, current_user)


@router.post("/sessions/{session_id}/heartbeat")
async def session_heartbeat(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Keep the instructor lock alive."""
    await _require_leader(current_user, org_id)
    session = await get_session(org_id)
    if session is None or str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        updated = await heartbeat(org_id, int(current_user.id))
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    return _snapshot(updated, current_user)


async def _owner_session(org_id: int, session_id: str, user: User) -> dict:
    await _require_leader(user, org_id)
    try:
        session = await require_owner_active(org_id, int(user.id))
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    if str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/navigate")
async def navigate_session(
    session_id: str,
    body: NavigateBody,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Steer all org teachers to an allowlisted diagram type."""
    if body.diagram_type not in VALID_DIAGRAM_TYPES:
        raise HTTPException(status_code=400, detail="Diagram type is not allowed")
    session = await _owner_session(org_id, session_id, current_user)
    try:
        updated = await bump_and_save(
            session,
            extra={"diagram_type": body.diagram_type},
            rate_limit_steer=True,
        )
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(org_id, updated)
    return _snapshot(updated, current_user)


@router.post("/sessions/{session_id}/options")
async def set_options(
    session_id: str,
    body: OptionsBody,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Replace topic chips."""
    if len(body.options) > MAX_TOPIC_OPTIONS:
        raise HTTPException(status_code=400, detail="Too many topic options")
    session = await _owner_session(org_id, session_id, current_user)
    options = [item.model_dump() for item in body.options]
    try:
        updated = await bump_and_save(session, extra={"topic_options": options}, rate_limit_steer=True)
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(org_id, updated)
    return _snapshot(updated, current_user)


@router.post("/sessions/{session_id}/pause")
async def pause(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Freeze pull without ending the session."""
    await _owner_session(org_id, session_id, current_user)
    try:
        updated = await pause_session(org_id, int(current_user.id))
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(org_id, updated)
    return _snapshot(updated, current_user)


@router.post("/sessions/{session_id}/resume")
async def resume(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused session."""
    await _owner_session(org_id, session_id, current_user)
    try:
        updated = await resume_session(org_id, int(current_user.id))
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(org_id, updated)
    return _snapshot(updated, current_user)


@router.post("/sessions/{session_id}/end")
async def end(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """End the session. Superadmin may end any session."""
    await _require_leader(current_user, org_id)
    session = await get_session(org_id)
    if session is None or str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    owner_id = int(session.get("instructor_id") or 0)
    if owner_id != int(current_user.id) and not is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Only the instructor or superadmin may end")
    ended = await end_session(org_id, tombstone=True)
    await clear_activity(org_id)
    if ended is not None:
        await _publish_seq(org_id, ended)
    return _snapshot(ended, current_user)


@router.post("/sessions/{session_id}/takeover")
async def takeover(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Transfer control to the caller."""
    await _require_leader(current_user, org_id)
    session = await get_session(org_id)
    if session is None or str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        updated = await takeover_session(
            org_id,
            int(current_user.id),
            _display_name(current_user),
        )
    except TrainingSessionError as exc:
        raise _http_for_session_error(exc) from exc
    await _publish_seq(org_id, updated)
    return _snapshot(updated, current_user)


@router.get("/command")
async def get_command(
    org_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    if_none_match: Optional[str] = Header(default=None, alias="If-None-Match"),
):
    """Current snapshot. Teachers use their org; instructors pass org_id."""
    target = _resolve_command_org(current_user, org_id)
    if target is None:
        body = snapshot_from_session(None)
        return JSONResponse(body, headers={"ETag": command_etag(None, 0)})
    if not is_org_teacher_target(current_user, target):
        if not await can_lead_training(current_user, target):
            raise HTTPException(status_code=403, detail="Training access required")
    session = await get_session(target)
    if session is not None:
        before = int(session.get("seq") or 0)
        session = await maybe_auto_pause(session)
        if int(session.get("seq") or 0) != before:
            await _publish_seq(target, session)
    body = _snapshot(session, current_user)
    etag = command_etag(body.get("session_id"), body.get("seq"))
    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(body, headers={"ETag": etag})


@router.get("/events")
async def training_events(
    request: Request,
    org_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """SSE doorbell. Cookie-authenticated same-origin EventSource."""
    target = _resolve_command_org(current_user, org_id)
    if target is None:
        raise HTTPException(status_code=400, detail="org_id is required")
    if not is_org_teacher_target(current_user, target):
        if not await can_lead_training(current_user, target):
            raise HTTPException(status_code=403, detail="Training access required")

    async def _stream():
        async for chunk in iter_org_events(target):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/activity")
async def post_activity(
    body: ActivityBody,
    current_user: User = Depends(get_current_user),
):
    """Teacher heartbeat for the instructor rail."""
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None or not is_org_teacher_target(current_user, int(org_id)):
        raise HTTPException(status_code=403, detail="Teachers in an org may report activity")
    generate_state = body.generate_state if body.generate_state in GENERATE_STATES else "idle"
    await touch_activity(
        int(org_id),
        int(current_user.id),
        {
            "diagram_type": body.diagram_type,
            "option_id": body.option_id,
            "option_label": body.option_label,
            "generate_state": generate_state,
            "name": _display_name(current_user),
        },
    )
    session = await get_session(int(org_id))
    if session is not None and session.get("state") == STATE_LIVE:
        await publish_event(int(org_id), "activity", {"seq": int(session.get("seq") or 0)})
    return {"ok": True}


@router.get("/sessions/{session_id}/roster")
async def session_roster(
    session_id: str,
    org_id: int = Query(...),
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Instructor-only paged activity roster."""
    await _require_leader(current_user, org_id)
    session = await get_session(org_id)
    if session is None or str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = await list_activity(org_id)
    needle = (q or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in str(row.get("name") or "").lower()]
    async with system_rls_session() as db:
        await _fill_missing_names(db, rows)
    lim = min(max(limit, 1), ROSTER_PAGE_MAX)
    off = max(offset, 0)
    page = rows[off : off + lim]
    return {
        "items": page,
        "total": len(rows),
        "limit": lim,
        "offset": off,
    }


@router.get("/sessions/{session_id}/roster/summary")
async def session_roster_summary(
    session_id: str,
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Online / generating / done counts."""
    await _require_leader(current_user, org_id)
    session = await get_session(org_id)
    if session is None or str(session.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return await activity_summary(org_id)


def _resolve_command_org(user: User, org_id: Optional[int]) -> Optional[int]:
    if org_id is not None:
        return int(org_id)
    user_org = getattr(user, "organization_id", None)
    if user_org is not None:
        return int(user_org)
    return None


async def _fill_missing_names(db: AsyncSession, rows: list[dict]) -> None:
    missing_ids = [int(row["user_id"]) for row in rows if not row.get("name") and row.get("user_id")]
    if not missing_ids:
        return
    result = await db.execute(select(User).where(User.id.in_(missing_ids)))
    names = {int(user.id): (user.name or f"User {user.id}") for user in result.scalars().all()}
    for row in rows:
        uid = int(row.get("user_id") or 0)
        if not row.get("name") and uid in names:
            row["name"] = names[uid]
