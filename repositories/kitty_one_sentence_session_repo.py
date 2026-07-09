"""
Repository for Kitty one-sentence panel sessions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.kitty_one_sentence import KittyOneSentenceSession


class KittyOneSentenceSessionRepository:
    """Insert, update, and list one-sentence sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: str, *, user_id: int) -> Optional[KittyOneSentenceSession]:
        """Load one session owned by the user."""
        q = (
            select(KittyOneSentenceSession)
            .where(
                KittyOneSentenceSession.id == session_id,
                KittyOneSentenceSession.user_id == int(user_id),
            )
            .limit(1)
        )
        return (await self._session.execute(q)).scalar_one_or_none()

    async def get_by_user_scope(
        self,
        *,
        user_id: int,
        diagram_scope: str,
    ) -> Optional[KittyOneSentenceSession]:
        """Load the session for a user + diagram scope pair."""
        q = (
            select(KittyOneSentenceSession)
            .where(
                KittyOneSentenceSession.user_id == int(user_id),
                KittyOneSentenceSession.diagram_scope == diagram_scope,
            )
            .limit(1)
        )
        return (await self._session.execute(q)).scalar_one_or_none()

    async def insert(self, row: KittyOneSentenceSession) -> KittyOneSentenceSession:
        """Persist a new session row."""
        self._session.add(row)
        await self._session.flush()
        return row

    async def touch_after_turn(
        self,
        session_id: str,
        *,
        phase: str,
        role: str,
        content: str,
        diagram_type: Optional[str],
        voice_session_id: Optional[str],
    ) -> None:
        """Increment counters and refresh activity timestamps after a stored turn."""
        now = datetime.now(UTC)
        session_row = await self.get_by_id_raw(session_id)
        if session_row is None:
            return

        create_inc = 1 if phase == "create" else 0
        edit_inc = 1 if phase == "edit" else 0
        preview = session_row.first_prompt_preview
        if preview is None and role == "user" and phase == "create":
            preview = content.strip()[:120] or None

        values: dict[str, object] = {
            "turn_count": int(session_row.turn_count) + 1,
            "create_turn_count": int(session_row.create_turn_count) + create_inc,
            "edit_turn_count": int(session_row.edit_turn_count) + edit_inc,
            "updated_at": now,
            "last_activity_at": now,
        }
        if preview is not None and session_row.first_prompt_preview is None:
            values["first_prompt_preview"] = preview
        if diagram_type and not session_row.diagram_type:
            values["diagram_type"] = diagram_type
        if voice_session_id:
            values["last_voice_session_id"] = voice_session_id

        await self._session.execute(
            update(KittyOneSentenceSession).where(KittyOneSentenceSession.id == session_id).values(**values)
        )

    async def get_by_id_raw(self, session_id: str) -> Optional[KittyOneSentenceSession]:
        """Load session by primary key without user filter (internal)."""
        q = select(KittyOneSentenceSession).where(KittyOneSentenceSession.id == session_id).limit(1)
        return (await self._session.execute(q)).scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        user_id: int,
        limit: int,
        before_id: Optional[str] = None,
    ) -> list[KittyOneSentenceSession]:
        """Return sessions newest-first for analytics listing."""
        cap = min(max(limit, 1), 100)
        q = select(KittyOneSentenceSession).where(KittyOneSentenceSession.user_id == int(user_id))
        if before_id:
            anchor = await self.get_by_id(before_id, user_id=user_id)
            if anchor is not None:
                q = q.where(KittyOneSentenceSession.last_activity_at < anchor.last_activity_at)
        q = q.order_by(
            KittyOneSentenceSession.last_activity_at.desc(),
            KittyOneSentenceSession.id.desc(),
        ).limit(cap)
        return list((await self._session.execute(q)).scalars().all())
