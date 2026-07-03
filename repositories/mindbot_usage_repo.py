"""
Async repository for MindbotUsageEvent (admin analytics).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindbot_usage import MindbotUsageEvent
from services.mindbot.errors import MindbotErrorCode


def _clip(s: str, max_len: int) -> str:
    return s.strip()[:max_len]


_SUCCESS_ERROR_CODES = (
    MindbotErrorCode.OK.value,
    MindbotErrorCode.ACCEPTED.value,
)


@dataclass(frozen=True)
class MindbotExportThread:
    """One DingTalk/Dify thread row aggregated from MindBot usage telemetry."""

    organization_id: int
    dify_user_key: str
    dify_conversation_id: str
    mindbot_config_id: int | None
    dingtalk_conversation_id: str | None
    dingtalk_chat_scope: str | None
    dingtalk_staff_id: str
    sender_nick: str | None
    linked_user_id: int | None
    first_event_at: datetime
    last_event_at: datetime


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
        stmt = select(distinct(MindbotUsageEvent.mindbot_config_id)).where(
            MindbotUsageEvent.organization_id == int(organization_id),
            MindbotUsageEvent.dingtalk_staff_id == staff,
            MindbotUsageEvent.mindbot_config_id.is_not(None),
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

    async def distinct_staff_for_org_with_usage(
        self,
        organization_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[tuple[str, str | None]]:
        """Distinct DingTalk staff ids with successful MindBot usage in one org."""
        org_id = int(organization_id)
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("nick")
        last_col = func.max(MindbotUsageEvent.created_at).label("last_event_at")
        base = select(MindbotUsageEvent.dingtalk_staff_id, nick_col, last_col).where(
            MindbotUsageEvent.organization_id == org_id,
            MindbotUsageEvent.error_code.in_(_SUCCESS_ERROR_CODES),
        )
        if start is not None:
            base = base.where(MindbotUsageEvent.created_at >= start)
        if end is not None:
            base = base.where(MindbotUsageEvent.created_at <= end)
        stmt = (
            base.group_by(MindbotUsageEvent.dingtalk_staff_id).order_by(last_col.desc()).limit(min(max(1, limit), 500))
        )
        rows = (await self._session.execute(stmt)).all()
        out: list[tuple[str, str | None]] = []
        for staff_raw, nick_raw, _last in rows:
            staff = (staff_raw or "").strip()[:128]
            if not staff:
                continue
            nick = (nick_raw or "").strip() or None
            out.append((staff, nick))
        return out

    async def list_dify_threads_for_export(
        self,
        organization_id: int,
        *,
        staff_ids: set[str] | None = None,
        chat_scopes: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 5000,
    ) -> list[MindbotExportThread]:
        """
        Distinct MindBot Dify threads for export supplement (group + 1:1).

        Aggregates successful usage rows by ``dify_user_key`` and
        ``dify_conversation_id``. Filter by ``staff_ids`` and/or ``chat_scopes``.
        When ``start`` / ``end`` are set, only events inside the window are
        inside the window are considered (at least one in-range turn qualifies
        the thread); export then fetches the full conversation from Dify.
        """
        org_id = int(organization_id)
        nick_col = func.max(MindbotUsageEvent.sender_nick).label("sender_nick")
        linked_col = func.max(MindbotUsageEvent.linked_user_id).label("linked_user_id")
        config_col = func.max(MindbotUsageEvent.mindbot_config_id).label("mindbot_config_id")
        dt_conv_col = func.max(MindbotUsageEvent.dingtalk_conversation_id).label("dingtalk_conversation_id")
        chat_scope_col = func.max(MindbotUsageEvent.dingtalk_chat_scope).label("dingtalk_chat_scope")
        first_col = func.min(MindbotUsageEvent.created_at).label("first_event_at")
        last_col = func.max(MindbotUsageEvent.created_at).label("last_event_at")

        base = (
            select(
                MindbotUsageEvent.organization_id,
                MindbotUsageEvent.dify_user_key,
                MindbotUsageEvent.dify_conversation_id,
                MindbotUsageEvent.dingtalk_staff_id,
                config_col,
                dt_conv_col,
                chat_scope_col,
                nick_col,
                linked_col,
                first_col,
                last_col,
            )
            .where(
                MindbotUsageEvent.organization_id == org_id,
                MindbotUsageEvent.dify_conversation_id.is_not(None),
                MindbotUsageEvent.dify_conversation_id != "",
                MindbotUsageEvent.error_code.in_(_SUCCESS_ERROR_CODES),
            )
            .group_by(
                MindbotUsageEvent.organization_id,
                MindbotUsageEvent.dify_user_key,
                MindbotUsageEvent.dify_conversation_id,
                MindbotUsageEvent.dingtalk_staff_id,
            )
        )

        if staff_ids:
            staff_list = [_clip(staff, 128) for staff in staff_ids if (staff or "").strip()]
            if staff_list:
                base = base.where(MindbotUsageEvent.dingtalk_staff_id.in_(staff_list))
            elif chat_scopes is None:
                return []

        if chat_scopes:
            scope_list = [_clip(scope, 16) for scope in chat_scopes if (scope or "").strip()]
            if not scope_list:
                return []
            base = base.where(MindbotUsageEvent.dingtalk_chat_scope.in_(scope_list))

        if start is not None:
            base = base.where(MindbotUsageEvent.created_at >= start)
        if end is not None:
            base = base.where(MindbotUsageEvent.created_at <= end)

        stmt = base.order_by(last_col.desc()).limit(min(max(1, limit), 5000))
        rows = (await self._session.execute(stmt)).all()
        out: list[MindbotExportThread] = []
        for row in rows:
            dify_conv = (row.dify_conversation_id or "").strip()[:128]
            dify_user = (row.dify_user_key or "").strip()[:256]
            staff = (row.dingtalk_staff_id or "").strip()[:128]
            if not dify_conv or not dify_user or not staff:
                continue
            config_raw = row.mindbot_config_id
            config_id = int(config_raw) if config_raw is not None else None
            dt_conv = (row.dingtalk_conversation_id or "").strip() or None
            if dt_conv:
                dt_conv = dt_conv[:256]
            scope = (row.dingtalk_chat_scope or "").strip() or None
            if scope:
                scope = scope[:16]
            nick = (row.sender_nick or "").strip() or None
            if nick:
                nick = nick[:256]
            linked_raw = row.linked_user_id
            linked_id = int(linked_raw) if linked_raw is not None else None
            out.append(
                MindbotExportThread(
                    organization_id=org_id,
                    dify_user_key=dify_user,
                    dify_conversation_id=dify_conv,
                    mindbot_config_id=config_id,
                    dingtalk_conversation_id=dt_conv,
                    dingtalk_chat_scope=scope,
                    dingtalk_staff_id=staff,
                    sender_nick=nick,
                    linked_user_id=linked_id,
                    first_event_at=row.first_event_at,
                    last_event_at=row.last_event_at,
                )
            )
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

    async def backfill_linked_user(
        self,
        organization_id: int,
        dingtalk_staff_id: str,
        user_id: int,
    ) -> int:
        """Set linked_user_id on historical usage rows after account bind."""
        staff = _clip(dingtalk_staff_id, 128)
        uid = int(user_id)
        org_id = int(organization_id)
        if not staff or uid <= 0 or org_id <= 0:
            return 0
        stmt = (
            update(MindbotUsageEvent)
            .where(
                MindbotUsageEvent.organization_id == org_id,
                MindbotUsageEvent.dingtalk_staff_id == staff,
                MindbotUsageEvent.linked_user_id.is_(None),
            )
            .values(linked_user_id=uid)
        )
        result = await self._session.execute(stmt)
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        return rowcount
