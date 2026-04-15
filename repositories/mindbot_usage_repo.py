"""Async repository for MindbotUsageEvent (admin analytics)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_usage import MindbotUsageEvent


def _clip(s: str, max_len: int) -> str:
    return s.strip()[:max_len]


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

    async def get_event_by_id(
        self,
        *,
        organization_id: int,
        event_id: int,
    ) -> MindbotUsageEvent | None:
        q = select(MindbotUsageEvent).where(
            MindbotUsageEvent.organization_id == organization_id,
            MindbotUsageEvent.id == event_id,
        )
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

    async def list_events_for_thread(
        self,
        *,
        organization_id: int,
        dingtalk_staff_id: str,
        dingtalk_conversation_id: str | None,
        dify_conversation_id: str | None,
        limit: int,
        before_id: int | None,
    ) -> list[MindbotUsageEvent]:
        """
        List usage rows for one DingTalk/Dify conversation thread.

        Requires a non-empty DingTalk conversation id and/or Dify conversation id.
        """
        staff = _clip(dingtalk_staff_id, 128)
        dt = (dingtalk_conversation_id or "").strip()
        df = (dify_conversation_id or "").strip()
        if not staff or (not dt and not df):
            return []

        q = select(MindbotUsageEvent).where(
            MindbotUsageEvent.organization_id == organization_id,
            MindbotUsageEvent.dingtalk_staff_id == staff,
        )
        if dt:
            q = q.where(
                MindbotUsageEvent.dingtalk_conversation_id == dt[:256],
            )
        else:
            q = q.where(
                MindbotUsageEvent.dify_conversation_id == df[:128],
            )
        if before_id is not None:
            q = q.where(MindbotUsageEvent.id < before_id)
        q = q.order_by(MindbotUsageEvent.id.desc()).limit(min(limit, 100))
        result = await self._session.execute(q)
        return list(result.scalars().all())
