"""
Leadable organizations and teacher counts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from services.features.training.permissions import teacher_role_filter_values
from utils.auth.expert_invited_org_ids import load_expert_invited_org_ids
from utils.auth.roles import is_expert, is_platform_bd, is_superadmin


async def list_leadable_orgs(
    db: AsyncSession,
    user: object,
    *,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Organization], int]:
    """Orgs the visiting instructor may lead."""
    lim = min(max(limit, 1), 100)
    off = max(offset, 0)
    filters = []
    raw_q = (q or "").strip()
    if raw_q:
        pattern = f"%{raw_q}%"
        filters.append(
            or_(
                Organization.name.ilike(pattern),
                Organization.code.ilike(pattern),
            )
        )
    if is_superadmin(user) or is_platform_bd(user):
        invited = None
    elif is_expert(user):
        invited = await load_expert_invited_org_ids(int(getattr(user, "id")))
        if not invited:
            return [], 0
        filters.append(Organization.id.in_(invited))
    else:
        return [], 0

    count_stmt = select(func.count()).select_from(Organization)
    list_stmt = select(Organization).order_by(Organization.name)
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (await db.execute(list_stmt.offset(off).limit(lim))).scalars().all()
    return list(rows), total


async def count_org_teachers(db: AsyncSession, org_id: int) -> int:
    """Number of teacher-role users in the org."""
    stmt = (
        select(func.count())
        .select_from(User)
        .where(
            User.organization_id == int(org_id),
            User.role.in_(teacher_role_filter_values()),
        )
    )
    return int((await db.execute(stmt)).scalar_one())
