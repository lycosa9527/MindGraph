"""
Repository for UserUsageActivity admin timeline rows.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.user_usage_activity import UserUsageActivity

_VALID_SOURCES = frozenset({"mindgraph", "mindmate", "dingtalk"})


class UserUsageActivityRepository:
    """List and insert curated user activity events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, row: UserUsageActivity) -> UserUsageActivity:
        """Persist one activity row."""
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_user(
        self,
        *,
        user_id: int,
        limit: int,
        before_id: Optional[int],
        source: Optional[str],
    ) -> list[UserUsageActivity]:
        """Newest-first cursor pagination for one user."""
        q = select(UserUsageActivity).where(UserUsageActivity.user_id == int(user_id))
        if source is not None and source.strip() in _VALID_SOURCES:
            q = q.where(UserUsageActivity.source == source.strip())
        if before_id is not None:
            q = q.where(UserUsageActivity.id < int(before_id))
        q = q.order_by(UserUsageActivity.id.desc()).limit(min(max(limit, 1), 100))
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_for_organization(
        self,
        *,
        organization_id: int,
        limit: int,
        before_id: Optional[int],
        source: Optional[str],
    ) -> list[UserUsageActivity]:
        """Newest-first cursor pagination for one organization."""
        q = select(UserUsageActivity).where(UserUsageActivity.organization_id == int(organization_id))
        if source is not None and source.strip() in _VALID_SOURCES:
            q = q.where(UserUsageActivity.source == source.strip())
        if before_id is not None:
            q = q.where(UserUsageActivity.id < int(before_id))
        q = q.order_by(UserUsageActivity.id.desc()).limit(min(max(limit, 1), 100))
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def exists_diagram_action(
        self,
        *,
        user_id: int,
        action: str,
        diagram_id: str,
    ) -> bool:
        """Backfill idempotency: skip duplicate diagram rows."""
        q = (
            select(UserUsageActivity.id)
            .where(
                UserUsageActivity.user_id == int(user_id),
                UserUsageActivity.action == action,
                UserUsageActivity.diagram_id == diagram_id,
            )
            .limit(1)
        )
        return (await self._session.execute(q)).scalar_one_or_none() is not None
