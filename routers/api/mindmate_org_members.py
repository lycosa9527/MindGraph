"""
School roster for MindMate seminar member pickers.

This path is intentionally outside ``/api/mindmate/seminar`` and ``/api/chat``.
Those prefixes are feature-gated, so a signed-in teacher with colleagues could
not open the seminar member dialog while collab or workshop chat was off.

Platform-tier accounts (superadmin / platform_bd / expert) may pass ``org_id``
to browse another school when inviting cross-school seminar members.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.features.mindmate_seminar.invite_org_access import (
    can_browse_seminar_invite_orgs,
    fetch_seminar_invite_roster_page,
    list_seminar_invite_organizations,
    resolve_seminar_roster_org_id,
)
from services.features.org_member_models import OrgMembersPage
from utils.auth import get_current_user

router = APIRouter(tags=["mindmate"])


class SeminarInviteOrgItem(BaseModel):
    """One school in the platform-tier seminar invite filter."""

    id: int
    name: str
    display_name: str


class SeminarInviteOrgsResponse(BaseModel):
    """Org filter options for seminar invites."""

    items: list[SeminarInviteOrgItem]
    can_browse: bool


@router.get("/mindmate/org-members", response_model=OrgMembersPage)
async def list_mindmate_org_members(
    request: Request,
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    org_id: Optional[int] = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> OrgMembersPage:
    """List school colleagues for the seminar picker, including the caller."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_org_members",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    effective_org_id = await resolve_seminar_roster_org_id(db, current_user, org_id)
    return await fetch_seminar_invite_roster_page(
        db,
        current_user,
        effective_org_id,
        q=q or "",
        limit=limit,
        offset=offset,
    )


@router.get("/mindmate/invite-organizations", response_model=SeminarInviteOrgsResponse)
async def list_mindmate_invite_organizations(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> SeminarInviteOrgsResponse:
    """List schools for the platform-tier cross-org seminar invite filter."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_invite_organizations",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    can_browse = can_browse_seminar_invite_orgs(current_user)
    rows = await list_seminar_invite_organizations(current_user) if can_browse else []
    return SeminarInviteOrgsResponse(
        items=[SeminarInviteOrgItem(id=row.id, name=row.name, display_name=row.display_name) for row in rows],
        can_browse=can_browse,
    )
