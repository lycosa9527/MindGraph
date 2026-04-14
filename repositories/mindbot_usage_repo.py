"""Async repository for MindbotUsageEvent (admin analytics)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_usage import MindbotUsageEvent


class MindbotUsageRepository:
    """List usage events per organization for admin UI."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_events_for_org(
        self,
        *,
        organization_id: int,
        limit: int,
        before_id: int | None,
        dingtalk_staff_id: str | None,
    ) -> list[MindbotUsageEvent]:
        q = select(MindbotUsageEvent).where(
            MindbotUsageEvent.organization_id == organization_id,
        )
        if dingtalk_staff_id is not None and dingtalk_staff_id.strip():
            q = q.where(
                MindbotUsageEvent.dingtalk_staff_id == dingtalk_staff_id.strip()[:128],
            )
        if before_id is not None:
            q = q.where(MindbotUsageEvent.id < before_id)
        q = q.order_by(MindbotUsageEvent.id.desc()).limit(min(limit, 100))
        result = await self._session.execute(q)
        return list(result.scalars().all())
