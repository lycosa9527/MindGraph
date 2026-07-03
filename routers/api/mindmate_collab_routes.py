"""
MindMate collab REST routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from routers.features.workshop_chat.schemas import OrgMembersPage
from services.auth.thinking_coin.event_hub import mutation_to_footer, track_client_event
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.poke_notify import send_mindmate_collab_poke
from services.features.mindmate_collab.visibility import user_may_join_mindmate_collab
from services.features.org_member_roster import fetch_org_members_page
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
)
from utils.auth import get_current_user
from utils.auth.school_tier import (
    TIER_FEATURE_ONLINE_COLLAB,
    assert_user_has_school_tier_feature,
)
from utils.auth.thinking_coin_config import EVENT_WORKSHOP_JOIN
from utils.db.session_open import actor_rls_session

logger = logging.getLogger(__name__)


async def _require_mindmate_collab_feature() -> None:
    """Return 404 when MindMate collab is disabled via FEATURE_MINDMATE_COLLAB."""
    if not config.FEATURE_MINDMATE_COLLAB:
        raise HTTPException(status_code=404, detail="Feature is disabled")


router = APIRouter(
    prefix="/mindmate/collab",
    tags=["mindmate-collab"],
    dependencies=[Depends(_require_mindmate_collab_feature)],
)


class StartCollabRequest(BaseModel):
    """Body for POST /mindmate/collab/start."""

    visibility: str = Field(default="organization")
    title: Optional[str] = None
    duration: str = Field(default="today")


class StopCollabRequest(BaseModel):
    """Body for POST /mindmate/collab/stop."""

    session_id: str


class JoinOrganizationRequest(BaseModel):
    """Body for POST /mindmate/collab/join-organization."""

    session_id: str


class PokeCollabRequest(BaseModel):
    """Body for POST /mindmate/collab/poke."""

    session_id: str
    target_user_id: int


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
    await check_endpoint_rate_limit("mindmate_collab_start", identifier, max_requests=10, window_seconds=60)

    payload, error = await get_mindmate_collab_manager().start_session(
        current_user.id,
        visibility=body.visibility,
        title=body.title,
        duration=body.duration,
    )
    if not payload:
        raise HTTPException(status_code=400, detail=error or "Failed to start room")
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
    await check_endpoint_rate_limit("mindmate_collab_stop", identifier, max_requests=10, window_seconds=60)

    ok = await get_mindmate_collab_manager().stop_session(body.session_id, current_user.id, reason="owner")
    if not ok:
        raise HTTPException(status_code=404, detail="Room not found or not authorized")
    return {"success": True}


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
    await check_endpoint_rate_limit("mindmate_collab_join", identifier, max_requests=20, window_seconds=60)

    payload = await get_mindmate_collab_manager().join_by_code(current_user.id, code)
    if not payload:
        raise HTTPException(status_code=404, detail="Invalid or inaccessible room code")

    thinking_footer = None
    async with actor_rls_session(current_user) as db:
        org = await track_client_event(db, current_user, None, EVENT_WORKSHOP_JOIN)
        thinking_footer = mutation_to_footer(org)
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
    await check_endpoint_rate_limit("mindmate_collab_join", identifier, max_requests=20, window_seconds=60)

    payload = await get_mindmate_collab_manager().join_by_session_id(current_user.id, body.session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Room not found or access denied")

    thinking_footer = None
    async with actor_rls_session(current_user) as db:
        org = await track_client_event(db, current_user, None, EVENT_WORKSHOP_JOIN)
        thinking_footer = mutation_to_footer(org)
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
        "mindmate_collab_poke",
        identifier,
        max_requests=20,
        window_seconds=60,
    )

    if body.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot poke yourself")

    mgr = get_mindmate_collab_manager()
    session = await mgr.load_session_by_id(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")

    is_host = session.owner_user_id == current_user.id
    if not is_host and not await mgr.is_participant(session.code, current_user.id):
        raise HTTPException(status_code=403, detail="Join the room before poking others")

    async with actor_rls_session(current_user) as db:
        target_may_join = await user_may_join_mindmate_collab(
            db,
            visibility=session.visibility,
            owner_user_id=session.owner_user_id,
            owner_org_id=session.organization_id,
            joiner_id=body.target_user_id,
        )
    if not target_may_join:
        raise HTTPException(status_code=403, detail="Target cannot join this room")

    from_name = getattr(current_user, "name", None) or getattr(current_user, "username", None) or "Teacher"
    delivered = await send_mindmate_collab_poke(
        target_user_id=body.target_user_id,
        from_user_id=current_user.id,
        from_name=str(from_name),
        session_id=session.id,
        room_code=session.code,
        room_title=session.title or "MindMate Collab",
        visibility=session.visibility,
    )
    return {"success": True, "delivered": delivered}


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
    await check_endpoint_rate_limit("mindmate_collab_org_members", identifier, max_requests=60, window_seconds=60)

    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User is not part of an organization")

    return await fetch_org_members_page(
        db,
        int(current_user.organization_id),
        q=q or "",
        limit=limit,
        offset=offset,
    )


@router.get("/organization/sessions")
async def list_organization_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List active org-visible MindMate collab rooms for the viewer's school."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_collab_list", identifier, max_requests=30, window_seconds=60)

    sessions = await get_mindmate_collab_manager().list_org_sessions(current_user.id)
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
        "mindmate_collab_status",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    mgr = get_mindmate_collab_manager()
    session = await mgr.load_session_by_code(code)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")
    if session.visibility != ONLINE_COLLAB_VISIBILITY_NETWORK:
        async with actor_rls_session(current_user) as db:
            allowed = await user_may_join_mindmate_collab(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=current_user.id,
            )
        if not allowed:
            raise HTTPException(status_code=404, detail="Room not found")
    status = await mgr.get_status(code)
    if not status:
        raise HTTPException(status_code=404, detail="Room not found")
    return status


@router.get("/my/hosted")
async def my_hosted_session(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return the caller's currently hosted MindMate collab session, if any."""
    await _require_collab_tier(current_user, lang)
    hosted = await get_mindmate_collab_manager().get_hosted_session(current_user.id)
    return {"session": hosted}


@router.get("/{session_id}/history")
async def collab_history(
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Paginated message history for reconnecting or auditing a room."""
    await _require_collab_tier(current_user, lang)
    mgr = get_mindmate_collab_manager()
    session = await mgr.load_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")
    async with actor_rls_session(current_user) as db:
        allowed = await user_may_join_mindmate_collab(
            db,
            visibility=session.visibility,
            owner_user_id=session.owner_user_id,
            owner_org_id=session.organization_id,
            joiner_id=current_user.id,
        )
    if not allowed and session.visibility != "network":
        raise HTTPException(status_code=403, detail="Access denied")
    messages = await mgr.fetch_message_history(session_id, limit=limit)
    return {"messages": messages}
