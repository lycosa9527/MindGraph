"""
Async repository for MindbotUsageEvent (admin analytics).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func, select
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
        """Return recent usage events for one organization."""
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
        """Return one usage event by primary key within an org."""
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

    async def distinct_config_ids_for_staff(
        self,
        organization_id: int,
        dingtalk_staff_id: str,
    ) -> set[int]:
        """MindBot config ids that handled events for this staff member."""
        staff = _clip(dingtalk_staff_id, 128)
        if not staff:
            return set()
        stmt = (
            select(distinct(MindbotUsageEvent.mindbot_config_id))
            .where(
                MindbotUsageEvent.organization_id == int(organization_id),
                MindbotUsageEvent.dingtalk_staff_id == staff,
                MindbotUsageEvent.mindbot_config_id.is_not(None),
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {int(value) for value in rows if value is not None}

    async def distinct_staff_for_users(
        self,
        organization_id: int,
        user_ids: list[int],
    ) -> list[tuple[str, str | None]]:
        """Distinct staff ids linked to MindGraph users via usage events."""
        if not user_ids:
            return []
        uid_set = {int(uid) for uid in user_ids if int(uid) > 0}
        if not uid_set:
            return []
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("nick")
        stmt = (
            select(MindbotUsageEvent.dingtalk_staff_id, nick_col)
            .where(
                MindbotUsageEvent.organization_id == int(organization_id),
                MindbotUsageEvent.linked_user_id.in_(uid_set),
            )
            .group_by(MindbotUsageEvent.dingtalk_staff_id)
        )
        rows = (await self._session.execute(stmt)).all()
        out: list[tuple[str, str | None]] = []
        for staff_raw, nick_raw in rows:
            staff = (staff_raw or "").strip()[:128]
            if not staff:
                continue
            nick = (nick_raw or "").strip() or None
            out.append((staff, nick))
        return out

    async def distinct_staff_map_for_users(
        self,
        organization_id: int,
        user_ids: list[int],
    ) -> dict[int, list[tuple[str, str | None]]]:
        """Map each linked MindGraph user id to distinct DingTalk staff ids."""
        if not user_ids:
            return {}
        uid_set = {int(uid) for uid in user_ids if int(uid) > 0}
        if not uid_set:
            return {}
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("nick")
        stmt = (
            select(
                MindbotUsageEvent.linked_user_id,
                MindbotUsageEvent.dingtalk_staff_id,
                nick_col,
            )
            .where(
                MindbotUsageEvent.organization_id == int(organization_id),
                MindbotUsageEvent.linked_user_id.in_(uid_set),
            )
            .group_by(
                MindbotUsageEvent.linked_user_id,
                MindbotUsageEvent.dingtalk_staff_id,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[int, list[tuple[str, str | None]]] = {uid: [] for uid in uid_set}
        for uid_raw, staff_raw, nick_raw in rows:
            uid = int(uid_raw)
            staff = (staff_raw or "").strip()[:128]
            if not staff:
                continue
            nick = (nick_raw or "").strip() or None
            out.setdefault(uid, []).append((staff, nick))
        return out

    async def distinct_unbound_staff_for_org(
        self,
        organization_id: int,
        *,
        exclude_staff_ids: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[tuple[str, str | None]]:
        """Staff with MindBot usage but no linked MindGraph user in events."""
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("nick")
        base = select(MindbotUsageEvent.dingtalk_staff_id, nick_col).where(
            MindbotUsageEvent.organization_id == int(organization_id),
            MindbotUsageEvent.linked_user_id.is_(None),
        )
        if start is not None:
            base = base.where(MindbotUsageEvent.created_at >= start)
        if end is not None:
            base = base.where(MindbotUsageEvent.created_at <= end)
        stmt = (
            base.group_by(MindbotUsageEvent.dingtalk_staff_id)
            .order_by(MindbotUsageEvent.dingtalk_staff_id)
            .limit(min(max(1, limit), 500))
        )
        rows = (await self._session.execute(stmt)).all()
        excluded = exclude_staff_ids or set()
        out: list[tuple[str, str | None]] = []
        for staff_raw, nick_raw in rows:
            staff = (staff_raw or "").strip()[:128]
            if not staff or staff in excluded:
                continue
            nick = (nick_raw or "").strip() or None
            out.append((staff, nick))
        return out

    async def distinct_unbound_staff_all_orgs(
        self,
        *,
        exclude_staff_by_org: dict[int, set[str]] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[tuple[int, str, str | None]]:
        """Unbound staff rows across organizations (org_id, staff_id, nick)."""
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("nick")
        base = select(
            MindbotUsageEvent.organization_id,
            MindbotUsageEvent.dingtalk_staff_id,
            nick_col,
        ).where(MindbotUsageEvent.linked_user_id.is_(None))
        if start is not None:
            base = base.where(MindbotUsageEvent.created_at >= start)
        if end is not None:
            base = base.where(MindbotUsageEvent.created_at <= end)
        stmt = (
            base.group_by(
                MindbotUsageEvent.organization_id,
                MindbotUsageEvent.dingtalk_staff_id,
            )
            .order_by(
                MindbotUsageEvent.organization_id,
                MindbotUsageEvent.dingtalk_staff_id,
            )
            .limit(min(max(1, limit), 500))
        )
        rows = (await self._session.execute(stmt)).all()
        excluded_map = exclude_staff_by_org or {}
        out: list[tuple[int, str, str | None]] = []
        for org_raw, staff_raw, nick_raw in rows:
            org_id = int(org_raw)
            staff = (staff_raw or "").strip()[:128]
            if not staff:
                continue
            if staff in excluded_map.get(org_id, set()):
                continue
            nick = (nick_raw or "").strip() or None
            out.append((org_id, staff, nick))
        return out
