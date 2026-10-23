"""
Add and list the teachers inside a school seminar group.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_collab.group_members import (
    actor_is_seminar_leader,
    closed_group_allows,
    list_group_member_ids,
    list_group_member_roles,
    list_member_acceptance,
    list_pending_seminar_invites,
    remove_group_member,
    repair_seminar_leader_roles,
    user_observes_seminar,
    respond_seminar_invite,
    seed_closed_group,
    set_group_member_role,
)
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.poke_notify import send_seminar_member_poke
from services.features.mindmate_collab.seminar_roles import (
    LEADER_ASSIGNABLE_SEMINAR_ROLES,
    SEMINAR_ROLE_LEADER,
    normalize_seminar_role,
    resolve_seminar_leader_id,
)
from services.features.mindmate_collab.visibility import user_may_join_mindmate_collab
from services.features.org_member_roster import fetch_session_participants_page
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()


class AddSeminarMembersRequest(BaseModel):
    """Body for POST /mindmate/collab/members."""

    session_id: str
    user_ids: List[int] = Field(default_factory=list, max_length=50)
    roles: dict[str, str] = Field(default_factory=dict)


class UpdateSeminarMemberRoleRequest(BaseModel):
    """Body for PATCH /mindmate/collab/members/role."""

    session_id: str
    user_id: int
    role: str = Field(min_length=1, max_length=32)


class RemoveSeminarMemberRequest(BaseModel):
    """Body for DELETE /mindmate/collab/members."""

    session_id: str
    user_id: int


class RespondSeminarInviteRequest(BaseModel):
    """Body for POST /mindmate/collab/members/respond."""

    session_id: str = Field(min_length=8, max_length=36)
    accept: bool


@router.get("/group-members")
async def list_seminar_group_members(
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    q: str = "",
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """List teachers invited into this seminar, including people who are offline."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_group_members",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    mgr = get_mindmate_collab_manager()
    session = await mgr.load_session_by_id(session_id)
    if not session or session.ended_at is not None:
        raise HTTPException(status_code=404, detail="Room not found")
    member_ids = await list_group_member_ids(session.id)
    if not closed_group_allows(member_ids, current_user.id, session.owner_user_id):
        raise HTTPException(status_code=403, detail="Not a member of this seminar")
    if not member_ids:
        member_ids = [int(session.owner_user_id)]
    page = await fetch_session_participants_page(
        db,
        member_ids,
        q=q or "",
        limit=limit,
        offset=offset,
    )
    if member_ids:
        leader_id = await repair_seminar_leader_roles(session.id, int(session.owner_user_id))
        roles = await list_group_member_roles(session.id)
    else:
        roles = {}
        leader_id = int(session.owner_user_id)
    online_ids = set(await mgr.list_participant_user_ids(session.code))
    payload = page.model_dump(mode="json")
    items = []
    acceptance = await list_member_acceptance(session.id)
    for item in payload.get("items") or []:
        user_id = int(item.get("id") or 0)
        role = roles.get(user_id)
        if user_id == leader_id and normalize_seminar_role(role) != SEMINAR_ROLE_LEADER:
            role = SEMINAR_ROLE_LEADER
        items.append(
            {
                **item,
                "role": normalize_seminar_role(role),
                "online": user_id in online_ids,
                "is_owner": user_id == int(session.owner_user_id),
                "is_leader": user_id == leader_id,
                "pending": acceptance.get(user_id) is False,
            }
        )
    payload["items"] = items
    payload["closed"] = bool(await list_group_member_ids(session.id))
    payload["owner_user_id"] = int(session.owner_user_id)
    payload["leader_user_id"] = leader_id
    payload["brief_topic"] = (session.brief_topic or "").strip() or None
    goals: list[str] = []
    if session.brief_goals:
        try:
            parsed = json.loads(session.brief_goals)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if isinstance(parsed, list):
            goals = [str(row).strip() for row in parsed if str(row).strip()]
    payload["brief_goals"] = goals
    payload["title"] = session.title
    return payload


@router.post("/members")
async def add_seminar_group_members(
    request: Request,
    body: AddSeminarMembersRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Invite more colleagues into a school seminar and nudge them to open it."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_add_members",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    session = await get_mindmate_collab_manager().load_session_by_id(body.session_id)
    if not session or session.ended_at is not None:
        raise HTTPException(status_code=404, detail="Room not found")
    if session.visibility not in (
        ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        ONLINE_COLLAB_VISIBILITY_NETWORK,
    ):
        raise HTTPException(status_code=400, detail="Unsupported seminar visibility")
    member_ids = await list_group_member_ids(session.id)
    if member_ids and not closed_group_allows(member_ids, current_user.id, session.owner_user_id):
        raise HTTPException(status_code=403, detail="Join the seminar before inviting others")
    if await user_observes_seminar(session.id, int(current_user.id)):
        raise HTTPException(status_code=403, detail="observer_readonly")

    # Any member may invite. School roster + phone lookup both land in the closed group,
    # including cross-school teachers for organization seminars.
    allowed: list[int] = []
    async with actor_rls_session(current_user) as db:
        for user_id in body.user_ids:
            if user_id == current_user.id:
                continue
            if user_id <= 0:
                continue
            exists = (await db.execute(select(User.id).where(User.id == int(user_id)))).scalar_one_or_none()
            if exists is None:
                continue
            may_join = await user_may_join_mindmate_collab(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )
            # Org rooms still accept explicit phone invites from outside the school.
            if may_join or session.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
                allowed.append(user_id)
    role_map = {int(raw_id): str(raw_role) for raw_id, raw_role in body.roles.items() if str(raw_id).isdigit()}
    inserted = await seed_closed_group(
        session.id,
        session.owner_user_id,
        allowed,
        roles_by_user=role_map,
        organization_id=session.organization_id,
    )
    poked = [user_id for user_id in inserted if user_id != current_user.id]
    from_name = getattr(current_user, "name", None) or getattr(current_user, "username", None) or "Teacher"
    for user_id in poked:
        await send_seminar_member_poke(
            session=session,
            target_user_id=user_id,
            from_user_id=current_user.id,
            from_name=str(from_name),
        )
    return {"success": True, "added_user_ids": poked}


@router.patch("/members/role")
async def update_seminar_member_role(
    request: Request,
    body: UpdateSeminarMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Leader-only: change a member's seminar role (leader transfers leadership)."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_member_role",
        identifier,
        max_requests=40,
        window_seconds=60,
    )
    session = await get_mindmate_collab_manager().load_session_by_id(body.session_id)
    if not session or session.ended_at is not None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not await actor_is_seminar_leader(session.id, session.owner_user_id, current_user.id):
        raise HTTPException(status_code=403, detail="Only the seminar leader can change roles")
    if int(body.user_id) == int(current_user.id):
        raise HTTPException(status_code=400, detail="Transfer leadership to another member")
    role = normalize_seminar_role(body.role)
    if role not in LEADER_ASSIGNABLE_SEMINAR_ROLES:
        raise HTTPException(status_code=400, detail="Invalid seminar role")
    ok = await set_group_member_role(session.id, body.user_id, role)
    if not ok:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"success": True, "user_id": body.user_id, "role": role}


@router.delete("/members")
async def remove_seminar_group_member(
    request: Request,
    body: RemoveSeminarMemberRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Leader-only: remove a member from the seminar group."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_remove_member",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    session = await get_mindmate_collab_manager().load_session_by_id(body.session_id)
    if not session or session.ended_at is not None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not await actor_is_seminar_leader(session.id, session.owner_user_id, current_user.id):
        raise HTTPException(status_code=403, detail="Only the seminar leader can remove members")
    roles = await list_group_member_roles(session.id)
    leader_id = resolve_seminar_leader_id(roles, int(session.owner_user_id))
    if int(body.user_id) == leader_id:
        raise HTTPException(status_code=400, detail="Cannot remove the seminar leader")
    ok = await remove_group_member(session.id, body.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"success": True, "user_id": body.user_id}


@router.get("/members/invites")
async def list_my_seminar_invites(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Pending cross-school invites for the signed-in teacher."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_member_invites",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    invites = await list_pending_seminar_invites(current_user.id)
    return {"invites": invites}


@router.post("/members/respond")
async def respond_my_seminar_invite(
    request: Request,
    body: RespondSeminarInviteRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Agree or decline a cross-school seminar invite."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_member_respond",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    result = await respond_seminar_invite(current_user.id, body.session_id, body.accept)
    if result is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return result


async def _require_collab_tier(user: User, lang: Language) -> None:
    """Ensure the caller has the online_collab school tier feature."""
    async with actor_rls_session(user) as db:
        await assert_user_has_school_tier_feature(
            db,
            user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )
