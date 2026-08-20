"""
Admin invite organizations list — scoped rows with invitation codes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime
from typing import Optional, cast

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import coalesce as sa_coalesce
from sqlalchemy.sql.functions import count as sa_count
from sqlalchemy.sql.functions import sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Language

try:
    from models.domain.token_usage import TokenUsage
except ImportError:
    TokenUsage = None

from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_panel_permissions import CAP_TAB_INVITES_VIEW
from utils.auth.admin_scope import AdminScope, invite_org_filter, mobile_created_orgs_filter
from utils.auth.org_privatization import org_privatization_list_field
from utils.auth.role_constants import SCHOOL_ADMIN_ROLES

from ..dependencies import get_language_dependency, require_invite_org_create, require_panel_capability
from ..helpers import utc_to_beijing_iso
from .organization_dify import dify_list_fields
from .organization_mindmate_branding import mindmate_branding_list_fields

logger = logging.getLogger(__name__)

router = APIRouter()


async def _list_invite_organizations(
    db: AsyncSession,
    org_clause: ColumnElement,
    user_org_clause: ColumnElement,
) -> list[dict]:
    """Serialize scoped organizations with invitation codes and member counts."""
    org_rows = await db.execute(select(Organization).where(org_clause).order_by(Organization.id))
    orgs = org_rows.scalars().all()

    user_counts_by_org: dict[int, int] = {}
    user_counts_stmt = (
        select(User.organization_id, sa_count(User.id).label("user_count"))
        .where(User.organization_id.isnot(None), user_org_clause)
        .group_by(User.organization_id)
    )
    for count_result in (await db.execute(user_counts_stmt)).all():
        user_counts_by_org[cast(int, count_result.organization_id)] = count_result.user_count

    managers_by_org: dict[int, list[str]] = {}
    managers_stmt = (
        select(User.organization_id, User.name, User.phone, User.email)
        .where(
            User.organization_id.isnot(None),
            User.role.in_(tuple(SCHOOL_ADMIN_ROLES)),
            user_org_clause,
        )
        .order_by(User.organization_id, User.name)
    )
    for row in (await db.execute(managers_stmt)).all():
        org_id_key = cast(int, row.organization_id)
        display = row.name or row.phone or getattr(row, "email", None) or ""
        managers_by_org.setdefault(org_id_key, []).append(display)

    token_stats_by_org: dict[int, dict[str, int]] = {}
    if TokenUsage is not None:
        try:
            org_token_stmt = (
                select(
                    Organization.id,
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                )
                .outerjoin(
                    TokenUsage,
                    and_(
                        Organization.id == TokenUsage.organization_id,
                        TokenUsage.success,
                    ),
                )
                .where(org_clause)
                .group_by(Organization.id)
            )
            for org_stat in (await db.execute(org_token_stmt)).all():
                token_stats_by_org[cast(int, org_stat.id)] = {
                    "input_tokens": int(org_stat.input_tokens or 0),
                    "output_tokens": int(org_stat.output_tokens or 0),
                    "total_tokens": int(org_stat.total_tokens or 0),
                }
        except DATABASE_ERRORS as exc:
            logger.debug("TokenUsage query failed: %s", exc)

    result = []
    for org in orgs:
        org_id = cast(int, org.id)
        user_count = user_counts_by_org.get(org_id, 0)
        org_managers = managers_by_org.get(org_id, [])
        manager_count = len(org_managers)
        org_token_stats = token_stats_by_org.get(
            org_id,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        expires_at_val = cast(Optional[datetime], org.expires_at)
        created_at_val = cast(Optional[datetime], org.created_at)
        invite_raw = cast(Optional[str], org.invitation_code)
        result.append(
            {
                "id": org_id,
                "code": org.code,
                "name": org.name,
                "display_name": getattr(org, "display_name", None),
                "invitation_code": invite_raw or "",
                "user_count": user_count,
                "manager_count": manager_count,
                "expires_at": utc_to_beijing_iso(expires_at_val),
                "is_active": org.is_active if hasattr(org, "is_active") else True,
                "created_at": utc_to_beijing_iso(created_at_val),
                "token_stats": org_token_stats,
                **dify_list_fields(org),
                **mindmate_branding_list_fields(org),
                **org_privatization_list_field(org),
            }
        )
    return result


def mobile_organization_public_fields(
    org_id: int,
    name: str,
    invitation_code: Optional[str],
    user_count: int,
) -> dict:
    """Fields the phone needs — no token stats, Dify, branding, or manager PII."""
    return {
        "id": org_id,
        "name": name,
        "invitation_code": invitation_code or "",
        "user_count": user_count,
    }


async def _list_mobile_organizations(
    db: AsyncSession,
    org_clause: ColumnElement,
) -> list[dict]:
    """Serialize created-org rows for mobile (invite code + member count only)."""
    org_rows = await db.execute(
        select(Organization.id, Organization.name, Organization.invitation_code)
        .where(org_clause)
        .order_by(Organization.id)
    )
    orgs = org_rows.all()
    org_ids = [cast(int, row.id) for row in orgs]
    user_counts_by_org: dict[int, int] = {}
    if org_ids:
        user_counts_stmt = (
            select(User.organization_id, sa_count(User.id).label("user_count"))
            .where(User.organization_id.in_(org_ids))
            .group_by(User.organization_id)
        )
        for count_result in (await db.execute(user_counts_stmt)).all():
            user_counts_by_org[cast(int, count_result.organization_id)] = count_result.user_count

    result = []
    for row in orgs:
        org_id = cast(int, row.id)
        result.append(
            mobile_organization_public_fields(
                org_id,
                str(row.name or ""),
                cast(Optional[str], row.invitation_code),
                user_counts_by_org.get(org_id, 0),
            )
        )
    return result


@router.get("/admin/invites/organizations")
async def list_invite_organizations_admin(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_INVITES_VIEW)),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """List organizations for the invite-users tab (includes full invitation codes)."""
    return await _list_invite_organizations(
        db,
        invite_org_filter(scope, Organization.id),
        invite_org_filter(scope, User.organization_id),
    )


@router.get("/admin/mobile/organizations")
async def list_mobile_organizations_admin(
    scope: AdminScope = Depends(require_invite_org_create),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """Mobile org management: superadmin sees all; professionals see orgs they created."""
    return await _list_mobile_organizations(db, mobile_created_orgs_filter(scope))
