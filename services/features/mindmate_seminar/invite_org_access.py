"""
Cross-org seminar invite roster access for platform-tier accounts.

Superadmin, teaching researcher (platform_bd), and expert may browse other
schools and multi-select teachers to invite. Teachers stay on their home org.

Org and cross-school roster reads use the system RLS session so platform-tier
accounts are not limited to their home-school row visibility.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from services.auth.expert_school_binding import list_bound_org_ids
from services.features.org_member_models import OrgMembersPage
from services.features.org_member_roster import fetch_org_members_page
from utils.auth.roles import is_admin, is_expert, is_platform_level
from utils.db.session_open import system_rls_session


@dataclass(frozen=True, slots=True)
class SeminarInviteOrgRow:
    """One school option for the seminar invite org filter."""

    id: int
    name: str
    display_name: str


def can_browse_seminar_invite_orgs(current_user: User) -> bool:
    """True when the account may pick teachers from another school."""
    return is_platform_level(current_user)


async def resolve_seminar_roster_org_id(
    db: AsyncSession,
    current_user: User,
    requested_org_id: int | None,
) -> int:
    """Resolve which school roster the seminar member picker may load.

    Platform-tier roles may request any organization id. Everyone else uses home
    school or an expert-bound school.
    """
    if requested_org_id is not None and can_browse_seminar_invite_orgs(current_user):
        org_id = int(requested_org_id)
        async with system_rls_session() as system_db:
            exists = (
                await system_db.execute(select(Organization.id).where(Organization.id == org_id))
            ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        return org_id

    if requested_org_id is not None and is_admin(current_user):
        return int(requested_org_id)

    home = current_user.organization_id
    if home is not None and (requested_org_id is None or requested_org_id == home):
        return int(home)

    if is_expert(current_user):
        bound = await list_bound_org_ids(db, int(current_user.id))
        if requested_org_id is not None and requested_org_id in bound:
            return requested_org_id
        if requested_org_id is None and bound:
            return bound[0]

    if home is not None:
        return int(home)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="User is not part of an organization",
    )


async def list_seminar_invite_organizations(
    current_user: User,
) -> list[SeminarInviteOrgRow]:
    """Schools shown in the platform-tier org filter. Empty for teachers."""
    if not can_browse_seminar_invite_orgs(current_user):
        return []
    async with system_rls_session() as db:
        rows = (
            await db.execute(
                select(Organization.id, Organization.name, Organization.display_name).order_by(
                    Organization.display_name.nulls_last(),
                    Organization.name,
                    Organization.id,
                )
            )
        ).all()
    items: list[SeminarInviteOrgRow] = []
    for org_id, name, display_name in rows:
        label = str(display_name or name or "").strip() or f"Org {org_id}"
        items.append(
            SeminarInviteOrgRow(
                id=int(org_id),
                name=str(name or "").strip() or label,
                display_name=label,
            )
        )
    return items


async def fetch_seminar_invite_roster_page(
    db: AsyncSession,
    current_user: User,
    org_id: int,
    *,
    q: str = "",
    limit: int = 200,
    offset: int = 0,
) -> OrgMembersPage:
    """Load a school roster; platform-tier cross-org reads bypass user RLS."""
    if can_browse_seminar_invite_orgs(current_user):
        async with system_rls_session() as system_db:
            return await fetch_org_members_page(
                system_db,
                org_id,
                q=q,
                limit=limit,
                offset=offset,
            )
    return await fetch_org_members_page(
        db,
        org_id,
        q=q,
        limit=limit,
        offset=offset,
    )
