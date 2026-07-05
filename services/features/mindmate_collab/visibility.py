"""
Join authorization for MindMate collab rooms.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from utils.auth.role_constants import (
    ROLE_EXPERT,
    SCHOOL_ADMIN_ROLES,
    SUPERADMIN_ROLES,
)


async def user_may_join_mindmate_collab(
    db: AsyncSession,
    *,
    visibility: str,
    owner_user_id: int,
    owner_org_id: int | None,
    joiner_id: int,
) -> bool:
    """Return True when joiner may enter an org- or network-visible room."""
    if joiner_id == owner_user_id:
        return True
    if visibility == ONLINE_COLLAB_VISIBILITY_NETWORK:
        return True

    ids = {joiner_id, owner_user_id}
    result = await db.execute(
        select(User.id, User.role, User.organization_id).where(User.id.in_(ids)),
    )
    rows = result.all()
    joiner_row = None
    owner_row = None
    for row in rows:
        if row.id == joiner_id:
            joiner_row = row
        if row.id == owner_user_id:
            owner_row = row
    if joiner_row is None or owner_row is None:
        return False

    role = joiner_row.role or ""
    if role in SUPERADMIN_ROLES or role == ROLE_EXPERT:
        return True
    if role in SCHOOL_ADMIN_ROLES:
        return True

    org_joiner = joiner_row.organization_id
    org_owner = owner_row.organization_id if owner_row else owner_org_id
    if visibility != ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return False
    if org_joiner is not None and org_owner is not None and org_joiner == org_owner:
        return True
    if org_owner is None and org_joiner is not None:
        return True
    return False
