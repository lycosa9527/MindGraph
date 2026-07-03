"""
Organization member roster queries (shared by workshop chat and MindMate collab).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from models.domain.auth import User
from routers.features.workshop_chat.schemas import OrgMemberRow, OrgMembersPage

_ORG_MEMBER_Q_MAX_LEN = 100
_ORG_MEMBER_LIMIT_MAX = 200


def escape_ilike_literal(text: str) -> str:
    """Escape ``%``, ``_``, ``\\`` for use in ILIKE with PostgreSQL ESCAPE '\\'."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def fetch_org_members_page(
    db: AsyncSession,
    org_id: int,
    *,
    q: str = "",
    limit: int = 200,
    offset: int = 0,
) -> OrgMembersPage:
    """Paginated org roster for contacts sidebar and collab member panels."""
    lim = min(max(limit, 1), _ORG_MEMBER_LIMIT_MAX)
    off = max(offset, 0)

    raw_q = (q or "").strip()
    if raw_q and len(raw_q) > _ORG_MEMBER_Q_MAX_LEN:
        raw_q = raw_q[:_ORG_MEMBER_Q_MAX_LEN]

    filters = [User.organization_id == org_id]
    if raw_q:
        pattern = f"%{escape_ilike_literal(raw_q)}%"
        filters.append(User.name.ilike(pattern, escape="\\"))

    count_result = await db.execute(select(sa_count()).select_from(User).where(*filters))
    total = count_result.scalar_one()
    users_result = await db.execute(
        select(User).where(*filters).order_by(User.name).offset(off).limit(lim),
    )
    users = users_result.scalars().all()
    items = [
        OrgMemberRow(
            id=u.id,
            name=u.name or f"User {u.id}",
            avatar=u.avatar,
            last_seen_at=u.workshop_last_seen_at,
        )
        for u in users
    ]
    return OrgMembersPage(
        items=items,
        total=int(total),
        limit=lim,
        offset=off,
    )
