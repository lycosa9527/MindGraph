"""
Repository for persisted Kitty one-sentence panel turns.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.kitty_one_sentence import KittyOneSentenceSession, KittyOneSentenceTurn
from services.utils.typing_helpers import result_rowcount


class KittyOneSentenceTurnRepository:
    """Insert and list one-sentence turns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_ignore_duplicate(self, row: KittyOneSentenceTurn) -> bool:
        """Insert one turn; return False when scope+turn_id already exists."""
        stmt = (
            insert(KittyOneSentenceTurn)
            .values(
                session_id=row.session_id,
                user_id=row.user_id,
                organization_id=row.organization_id,
                scope=row.scope,
                turn_id=row.turn_id,
                role=row.role,
                content=row.content,
                phase=row.phase,
                source=row.source,
                action=row.action,
                outcome=row.outcome,
                user_text=row.user_text,
                diagram_type=row.diagram_type,
                voice_session_id=row.voice_session_id,
                request_id=row.request_id,
                command_detail=row.command_detail,
                created_at=row.created_at,
            )
            .on_conflict_do_nothing(constraint="uq_kitty_one_sentence_turn_scope_turn")
        )
        result = await self._session.execute(stmt)
        return result_rowcount(result) > 0

    async def list_for_session(
        self,
        *,
        session_id: str,
        user_id: int,
        limit: int,
    ) -> list[KittyOneSentenceTurn]:
        """Return turns oldest-first for one tracked session."""
        cap = min(max(limit, 1), 200)
        q = (
            select(KittyOneSentenceTurn)
            .where(
                KittyOneSentenceTurn.session_id == session_id,
                KittyOneSentenceTurn.user_id == int(user_id),
            )
            .order_by(KittyOneSentenceTurn.created_at.asc(), KittyOneSentenceTurn.id.asc())
            .limit(cap)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_for_scope(
        self,
        *,
        scope: str,
        user_id: int,
        limit: int,
    ) -> list[KittyOneSentenceTurn]:
        """Return turns oldest-first for one diagram scope owned by the user."""
        cap = min(max(limit, 1), 200)
        q = (
            select(KittyOneSentenceTurn)
            .where(
                KittyOneSentenceTurn.scope == scope,
                KittyOneSentenceTurn.user_id == int(user_id),
            )
            .order_by(KittyOneSentenceTurn.created_at.asc(), KittyOneSentenceTurn.id.asc())
            .limit(cap)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_actions_for_scope(
        self,
        *,
        scope: str,
        user_id: int,
        limit: int,
    ) -> list[KittyOneSentenceTurn]:
        """Return kitty action turns (non-null action) oldest-first for activity feed."""
        cap = min(max(limit, 1), 200)
        q = (
            select(KittyOneSentenceTurn)
            .where(
                KittyOneSentenceTurn.scope == scope,
                KittyOneSentenceTurn.user_id == int(user_id),
                KittyOneSentenceTurn.role == "kitty",
                KittyOneSentenceTurn.action.is_not(None),
            )
            .order_by(KittyOneSentenceTurn.created_at.asc(), KittyOneSentenceTurn.id.asc())
            .limit(cap)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_for_diagram_id(
        self,
        *,
        diagram_id: str,
        user_id: int,
        limit: int,
        actions_only: bool = False,
    ) -> list[KittyOneSentenceTurn]:
        """Return turns for a saved diagram id (scope or session.diagram_id)."""
        cap = min(max(limit, 1), 200)
        diagram = str(diagram_id or "").strip()
        if not diagram:
            return []
        q = (
            select(KittyOneSentenceTurn)
            .outerjoin(
                KittyOneSentenceSession,
                KittyOneSentenceTurn.session_id == KittyOneSentenceSession.id,
            )
            .where(
                KittyOneSentenceTurn.user_id == int(user_id),
                (
                    (KittyOneSentenceTurn.scope == diagram)
                    | (KittyOneSentenceSession.diagram_id == diagram)
                    | (KittyOneSentenceSession.diagram_scope == diagram)
                ),
            )
        )
        if actions_only:
            q = q.where(
                KittyOneSentenceTurn.role == "kitty",
                KittyOneSentenceTurn.action.is_not(None),
            )
        q = q.order_by(
            KittyOneSentenceTurn.created_at.asc(),
            KittyOneSentenceTurn.id.asc(),
        ).limit(cap)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def exists_turn(self, *, scope: str, turn_id: str) -> bool:
        """Return whether a turn id is already stored for the scope."""
        q = (
            select(KittyOneSentenceTurn.id)
            .where(
                KittyOneSentenceTurn.scope == scope,
                KittyOneSentenceTurn.turn_id == turn_id,
            )
            .limit(1)
        )
        return (await self._session.execute(q)).scalar_one_or_none() is not None
