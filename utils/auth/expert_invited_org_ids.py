"""
Load expert / teaching-researcher invited organization IDs (leaf DB query module).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select

from models.domain.auth import Organization
from utils.db.session_open import system_rls_session


async def load_expert_invited_org_ids(actor_id: int) -> frozenset[int]:
    """Organization IDs created via invite flow by this expert or teaching researcher."""
    async with system_rls_session() as db:
        rows = (
            await db.execute(select(Organization.id).where(Organization.invited_by_user_id == int(actor_id)))
        ).scalars()
        return frozenset(int(org_id) for org_id in rows)
