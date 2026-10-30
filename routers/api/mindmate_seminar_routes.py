"""
MindMate collab REST routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.mindmate_seminar_library_mutations import router as saved_seminar_mutation_router
from routers.api.mindmate_seminar_background_files import router as seminar_files_router
from routers.api.mindmate_seminar_face_chat import router as seminar_face_chat_router
from routers.api.mindmate_seminar_reply_artifacts import router as seminar_reply_artifacts_router
from routers.api.mindmate_seminar_share_canvas import router as seminar_share_router
from routers.api.mindmate_seminar_members import router as seminar_members_router
from routers.api.mindmate_seminar_messages import router as seminar_messages_router
from routers.auth.dependencies import get_language_dependency
from routers.features.workshop_chat.dependencies import resolve_social_org_id
from routers.features.workshop_chat.schemas import OrgMembersPage
from services.auth.thinking_coin.client_event_service import load_user_org
from services.auth.thinking_coin.event_hub import mutation_to_footer, track_client_event
from services.features.mindmate_seminar.config import MINDMATE_COLLAB_DEFAULT_DURATION
from services.features.mindmate_seminar.diagram_library import (
    COPY_FAILED,
    COPY_FORBIDDEN,
    COPY_LIMIT,
    COPY_NOT_FOUND,
    COPY_NO_SPEC,
    save_collab_diagram_for_user,
)
from services.features.mindmate_seminar.brief_edit import update_seminar_brief
from services.features.mindmate_seminar.group_members import list_group_member_ids
from services.features.mindmate_seminar.library_archive import (
    list_saved_seminars,
    load_saved_seminar,
    save_finished_seminar_for_owner,
)
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.poke_notify import send_seminar_member_poke
from services.features.mindmate_seminar.reopen_session import reopen_saved_seminar
from services.features.mindmate_seminar.seminar_leave import leave_live_seminar
from services.features.mindmate_seminar.visibility import user_may_join_mindmate_seminar
from services.features.org_member_roster import (
    fetch_org_members_page,
    fetch_session_participants_page,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from utils.auth import get_current_user, user_has_feature_access
from utils.auth.school_tier import (
    TIER_FEATURE_ONLINE_COLLAB,
    assert_user_has_school_tier_feature,
)
from utils.auth.thinking_coin_config import EVENT_WORKSHOP_JOIN
from utils.db.session_open import actor_rls_session, system_rls_session

logger = logging.getLogger(__name__)


async def _require_mindmate_seminar_access(
    current_user: User = Depends(get_current_user),
) -> None:
    """Return 404 when collab is off globally or the user lacks org/user grants."""
    if not await user_has_feature_access(current_user, "feature_mindmate_seminar"):
        raise HTTPException(status_code=404, detail="Feature is disabled")


router = APIRouter(
    prefix="/mindmate/seminar",
    tags=["mindmate-seminar"],
    dependencies=[Depends(_require_mindmate_seminar_access)],
)
router.include_router(saved_seminar_mutation_router)
router.include_router(seminar_members_router)
router.include_router(seminar_messages_router)
router.include_router(seminar_files_router)
router.include_router(seminar_reply_artifacts_router)
router.include_router(seminar_face_chat_router)
router.include_router(seminar_share_router)


class CollabSeedMessage(BaseModel):
    """One message copied into a new collab room from the host's MindMate thread."""

    role: str = Field(default="user")
    content: str = Field(default="")


class StartCollabRequest(BaseModel):
    """Body for POST /mindmate/seminar/start."""

    visibility: str = Field(default="organization")
    title: Optional[str] = None
    duration: str = Field(default=MINDMATE_COLLAB_DEFAULT_DURATION)
    seed_messages: List[CollabSeedMessage] = Field(default_factory=list)
    member_user_ids: List[int] = Field(default_factory=list, max_length=50)
    member_roles: dict[str, str] = Field(default_factory=dict)
    brief_topic: Optional[str] = None
    brief_goals: List[str] = Field(default_factory=list)
    close_group: bool = False


class RenameCollabRequest(BaseModel):
    """Body for PATCH /mindmate/seminar/title."""

    session_id: str
    title: str = Field(min_length=1, max_length=200)


class UpdateCollabBriefRequest(BaseModel):
    """Body for PATCH /mindmate/seminar/brief. Goals are optional. Topic may change."""

    session_id: str
    topic: Optional[str] = Field(default=None, max_length=200)
    goals: List[str] = Field(default_factory=list, max_length=12)
    resources: Optional[List[str]] = Field(default=None, max_length=30)


class StopCollabRequest(BaseModel):
    """Body for POST /mindmate/seminar/stop."""

    session_id: str


class ReopenCollabRequest(BaseModel):
    """Body for POST /mindmate/seminar/reopen."""

    session_id: str


class JoinOrganizationRequest(BaseModel):
    """Body for POST /mindmate/seminar/join-organization."""

    session_id: str


class PokeCollabRequest(BaseModel):
    """Body for POST /mindmate/seminar/poke."""

    session_id: str
    target_user_id: int


class SaveCollabDiagramRequest(BaseModel):
    """Body for POST /mindmate/seminar/{session_id}/diagram-library."""

    preview_id: str = Field(min_length=8, max_length=8)


async def _require_collab_tier(user: User, lang: Language) -> None:
    """Ensure the caller has the online_collab school tier feature."""
    async with actor_rls_session(user) as db:
        await assert_user_has_school_tier_feature(
            db,
            user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )


@router.post("/start")
async def start_collab_room(
    request: Request,
    body: StartCollabRequest = Body(default_factory=StartCollabRequest),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Start a MindMate collab room (org or network visibility)."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_start", identifier, max_requests=10, window_seconds=60)

    if body.visibility not in (
        ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        ONLINE_COLLAB_VISIBILITY_NETWORK,
    ):
        raise HTTPException(status_code=400, detail="Invalid visibility mode")

    role_map: dict[int, str] = {}
    for raw_id, raw_role in body.member_roles.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id > 0:
            role_map[user_id] = str(raw_role or "").strip()

    payload, error = await get_mindmate_seminar_manager().start_session(
        current_user.id,
        visibility=body.visibility,
        title=body.title,
        duration=body.duration,
        seed_messages=[item.model_dump() for item in body.seed_messages],
        member_user_ids=body.member_user_ids,
        member_roles=role_map,
        brief_topic=body.brief_topic,
        brief_goals=body.brief_goals,
        close_group=body.close_group or bool(body.member_user_ids) or bool(body.member_roles),
    )
    if not payload:
        raise HTTPException(status_code=400, detail=error or "Failed to start room")
    return {"success": True, **payload}


@router.patch("/title")
async def rename_collab_room(
    request: Request,
    body: RenameCollabRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Rename a live seminar. Host only."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_rename",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    payload = await get_mindmate_seminar_manager().update_session_title(
        body.session_id,
        current_user.id,
        body.title,
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Room not found or not authorized")
    return {"success": True, **payload}


@router.patch("/brief")
async def update_collab_brief(
    request: Request,
    body: UpdateCollabBriefRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Let the host fill in or change goals and materials on the pinned brief."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_brief",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    payload, error = await update_seminar_brief(
        body.session_id,
        current_user.id,
        body.goals,
        body.resources,
        body.topic,
    )
    if error in {"invalid", "too_long"}:
        raise HTTPException(status_code=400, detail="Invalid seminar brief")
    if not payload:
        raise HTTPException(status_code=404, detail="Room not found or not authorized")
    return {"success": True, **payload}


@router.post("/stop")
async def stop_collab_room(
    request: Request,
    body: StopCollabRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Stop a hosted MindMate collab room."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_stop", identifier, max_requests=10, window_seconds=60)

    ok = await get_mindmate_seminar_manager().stop_session(body.session_id, current_user.id, reason="owner")
    if not ok:
        raise HTTPException(status_code=404, detail="Room not found or not authorized")
    return {"success": True}


@router.post("/leave")
async def leave_collab_room(
    request: Request,
    body: StopCollabRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Leave a live seminar. The room stays open for everyone else."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_leave", identifier, max_requests=20, window_seconds=60)
    result = await leave_live_seminar(current_user.id, body.session_id)
    if result == "still_owner":
        raise HTTPException(status_code=409, detail="The seminar leader ends the seminar instead of leaving")
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Seminar not found")
    return {"success": True}


@router.post("/reopen")
async def reopen_collab_room(
    request: Request,
    body: ReopenCollabRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Continue a saved seminar by opening the same room again."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_start", identifier, max_requests=10, window_seconds=60)

    payload, error = await reopen_saved_seminar(body.session_id, current_user.id)
    if not payload:
        if error == "not_owner":
            raise HTTPException(status_code=403, detail="Only the seminar owner can continue this session")
        if error in {"not_found", "not_saved"}:
            raise HTTPException(status_code=404, detail="Saved seminar not found")
        raise HTTPException(status_code=400, detail=error or "Failed to start room")
    return {"success": True, **payload}


@router.post("/join")
async def join_collab_by_code(
    request: Request,
    code: str = Query(..., min_length=7, max_length=7),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Join a MindMate collab room by invite code."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_join", identifier, max_requests=20, window_seconds=60)

    payload, error = await get_mindmate_seminar_manager().join_by_code(current_user.id, code)
    if error == "still_live":
        raise HTTPException(status_code=409, detail="Seminar is still live")
    if error == "forbidden":
        raise HTTPException(status_code=403, detail="Invalid or inaccessible room code")
    if not payload:
        raise HTTPException(status_code=404, detail="Invalid or inaccessible room code")

    thinking_footer = None
    async with actor_rls_session(current_user) as db:
        org = await load_user_org(current_user)
        join_mutation = await track_client_event(db, current_user, org, EVENT_WORKSHOP_JOIN)
        thinking_footer = mutation_to_footer(join_mutation)
    response = {"success": True, **payload}
    if thinking_footer:
        response["thinking_coins"] = thinking_footer
    return response


@router.post("/join-organization")
async def join_collab_organization(
    request: Request,
    body: JoinOrganizationRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Join an org-visible MindMate collab room from the browse list."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_join", identifier, max_requests=20, window_seconds=60)

    payload = await get_mindmate_seminar_manager().join_by_session_id(current_user.id, body.session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Room not found or access denied")

    thinking_footer = None
    async with actor_rls_session(current_user) as db:
        org = await load_user_org(current_user)
        join_mutation = await track_client_event(db, current_user, org, EVENT_WORKSHOP_JOIN)
        thinking_footer = mutation_to_footer(join_mutation)
    response = {"success": True, **payload}
    if thinking_footer:
        response["thinking_coins"] = thinking_footer
    return response


@router.post("/poke")
async def poke_collab_member(
    request: Request,
    body: PokeCollabRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Nudge a colleague to join the MindMate collab seminar (real-time toast)."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_poke",
        identifier,
        max_requests=20,
        window_seconds=60,
    )

    if body.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot poke yourself")

    mgr = get_mindmate_seminar_manager()
    session = await mgr.load_session_by_id(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")

    is_host = session.owner_user_id == current_user.id
    if not is_host and not await mgr.is_participant(session.code, current_user.id):
        raise HTTPException(status_code=403, detail="Join the room before poking others")

    member_ids = {int(item) for item in await list_group_member_ids(session.id)}
    closed = bool(member_ids) or session.visibility == ONLINE_COLLAB_VISIBILITY_NETWORK
    if closed:
        if int(body.target_user_id) not in member_ids:
            raise HTTPException(status_code=403, detail="Target is not a member of this seminar")
    else:
        async with actor_rls_session(current_user) as db:
            target_may_join = await user_may_join_mindmate_seminar(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=body.target_user_id,
            )
        if not target_may_join:
            raise HTTPException(status_code=403, detail="Target cannot join this room")

    from_name = getattr(current_user, "name", None) or getattr(current_user, "username", None) or "Teacher"
    delivered = await send_seminar_member_poke(
        session=session,
        target_user_id=body.target_user_id,
        from_user_id=current_user.id,
        from_name=str(from_name),
    )
    return {"success": True, "delivered": delivered}


@router.get("/session-members", response_model=OrgMembersPage)
async def list_collab_session_members(
    request: Request,
    code: str = Query(..., min_length=7, max_length=7),
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List teachers currently in a network seminar this person may enter."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_session_members",
        identifier,
        max_requests=60,
        window_seconds=60,
    )

    mgr = get_mindmate_seminar_manager()
    session = await mgr.load_session_by_code(code)
    if not session or session.ended_at is not None:
        raise HTTPException(status_code=404, detail="Room not found")
    if session.visibility != ONLINE_COLLAB_VISIBILITY_NETWORK:
        raise HTTPException(status_code=400, detail="Session roster is org-only")

    if not await mgr.user_may_connect(current_user.id, session):
        raise HTTPException(status_code=403, detail="Not allowed to view this room roster")

    participant_ids = await mgr.list_participant_user_ids(code)
    async with system_rls_session() as roster_db:
        return await fetch_session_participants_page(
            roster_db,
            participant_ids,
            q=q or "",
            limit=limit,
            offset=offset,
        )


@router.get("/org-members", response_model=OrgMembersPage)
async def list_collab_org_members(
    request: Request,
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """List school/org colleagues for the MindMate collab member panel."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_org_members", identifier, max_requests=60, window_seconds=60)

    effective_org_id = await resolve_social_org_id(db, current_user, None)
    return await fetch_org_members_page(
        db,
        effective_org_id,
        q=q or "",
        limit=limit,
        offset=offset,
    )


@router.get("/lookup-phone")
async def lookup_collab_user_by_phone(
    request: Request,
    phone: str = Query(..., min_length=11, max_length=11),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Look up a platform account by phone for cross-school seminar invites."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_lookup_phone",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) != 11 or not digits.startswith("1"):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    if digits == (current_user.phone or "").strip():
        raise HTTPException(status_code=400, detail="Cannot invite yourself")

    async with system_rls_session() as db:
        row = (
            await db.execute(
                select(
                    User.id,
                    User.name,
                    User.phone,
                    User.avatar,
                    User.organization_id,
                    Organization.name,
                    Organization.display_name,
                )
                .outerjoin(Organization, Organization.id == User.organization_id)
                .where(User.phone == digits)
                .limit(1)
            )
        ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    user_id, name, user_phone, avatar, org_id, org_name, org_display = row
    masked = f"{digits[:3]}****{digits[-4:]}"
    org_label = (org_display or org_name or "").strip()
    return {
        "id": int(user_id),
        "name": (name or user_phone or masked).strip(),
        "avatar": avatar,
        "org_name": org_label,
        "phone_masked": masked,
        "same_org": bool(current_user.organization_id and org_id and int(current_user.organization_id) == int(org_id)),
    }


@router.get("/organization/sessions")
async def list_organization_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List active org-visible MindMate collab rooms for the viewer's school."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_seminar_list", identifier, max_requests=60, window_seconds=60)

    sessions = await get_mindmate_seminar_manager().list_org_sessions(
        current_user.id,
        organization_id=current_user.organization_id,
    )
    return {"sessions": sessions}


@router.get("/status")
async def collab_status(
    request: Request,
    code: str = Query(..., min_length=7, max_length=7),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return live status for a MindMate collab room code."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_status",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    mgr = get_mindmate_seminar_manager()
    session = await mgr.load_session_by_code(code)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")
    if not await mgr.user_may_connect(current_user.id, session):
        raise HTTPException(status_code=404, detail="Room not found")
    status = await mgr.get_status(code)
    if not status:
        raise HTTPException(status_code=404, detail="Room not found")
    return status


@router.get("/my/hosted")
async def my_hosted_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return live seminars the caller hosts or has agreed to join."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_my_hosted",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    sessions = await get_mindmate_seminar_manager().list_accessible_live_sessions(current_user.id)
    return {"session": sessions[0] if sessions else None, "sessions": sessions}


@router.get("/my/library")
async def list_my_saved_seminars(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List finished seminars the owner saved into their MindMate library."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_library_list",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    seminars = await list_saved_seminars(current_user.id)
    return {"seminars": seminars}


@router.get("/my/library/{session_id}")
async def get_my_saved_seminar(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return one saved seminar and its transcript for the owner."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_library_read",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    payload = await load_saved_seminar(session_id, current_user.id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Saved seminar not found")
    return payload


@router.post("/{session_id}/library")
async def save_collab_seminar_to_library(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Save a finished seminar into the owner's MindMate library."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_library_save",
        identifier,
        max_requests=10,
        window_seconds=60,
    )
    payload, error = await save_finished_seminar_for_owner(session_id, current_user.id)
    if error == "still_live":
        raise HTTPException(status_code=409, detail="Seminar is still live")
    if payload is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"success": True, "seminar": payload}


@router.post("/{session_id}/diagram-library")
async def save_collab_diagram_to_library(
    request: Request,
    session_id: str,
    body: SaveCollabDiagramRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Save a seminar diagram preview into the caller's library, then return its id."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_diagram_library",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    diagram_id, error = await save_collab_diagram_for_user(session_id, body.preview_id, current_user)
    if error == COPY_FORBIDDEN:
        raise HTTPException(status_code=403, detail=COPY_FORBIDDEN)
    if error == COPY_LIMIT:
        raise HTTPException(status_code=409, detail=COPY_LIMIT)
    if error == COPY_NO_SPEC:
        raise HTTPException(status_code=409, detail=COPY_NO_SPEC)
    if error in (COPY_NOT_FOUND, COPY_FAILED) or not diagram_id:
        status = 404 if error == COPY_NOT_FOUND else 500
        raise HTTPException(status_code=status, detail=error or COPY_FAILED)
    return {"diagram_id": diagram_id}
