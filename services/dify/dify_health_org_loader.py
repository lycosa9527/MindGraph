"""
Load organizations that contribute Dify credentials to platform health checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import List

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from services.dify.dify_global_servers import global_dify_pair_ready
from services.dify.dify_server_schema import organization_dify_server_slots, server_slot_field_names


def organization_has_dify_credentials_clause():
    """SQL filter: org row has at least one complete Dify URL + key pair."""
    clauses = []
    for server in organization_dify_server_slots():
        fields = server_slot_field_names(server)
        if fields is None:
            continue
        url_field, key_field = fields
        url_col = getattr(Organization, url_field)
        key_col = getattr(Organization, key_field)
        clauses.append(
            and_(
                url_col.isnot(None),
                url_col != "",
                key_col.isnot(None),
                key_col != "",
            )
        )
    if not clauses:
        return Organization.id.is_(None)
    return or_(*clauses)


async def load_orgs_with_dify_credentials(db: AsyncSession) -> List[Organization]:
    """Return schools with at least one configured Dify server slot (stable id order)."""
    result = await db.execute(
        select(Organization).where(organization_has_dify_credentials_clause()).order_by(Organization.id.asc())
    )
    return list(result.scalars().all())


async def load_orgs_for_dify_health(db: AsyncSession) -> List[Organization]:
    """
    Schools the heartbeat should cover.

    When Dify main and Dify backup are both set, every school is included so a
    blank 主服务器 or 备用服务器 can fail over between those env servers. Otherwise
    only schools that store their own credentials are loaded.
    """
    if global_dify_pair_ready():
        result = await db.execute(select(Organization).order_by(Organization.id.asc()))
        return list(result.scalars().all())
    return await load_orgs_with_dify_credentials(db)
