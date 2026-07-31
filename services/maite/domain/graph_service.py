"""
Maite knowledge/thinking graph domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_artifacts import MaiteGraphNodeProgress
from repositories.maite.graph_repo import MaiteGraphRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from services.maite.domain.errors import MaiteNotFoundError
from services.maite.domain.transaction import commit_maite


class GraphService:
    """Read and update graph node progress for a user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._graph = MaiteGraphRepository(session)
        self._sessions = MaiteSessionsRepository(session)

    async def list_nodes(
        self,
        user_id: int,
        *,
        graph_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List graph node progress rows for a user."""
        rows = await self._graph.list_for_user(user_id, graph_type=graph_type)
        return [self._row_dict(row) for row in rows]

    async def update_node(
        self,
        *,
        user_id: int,
        session_id: int,
        graph_type: str,
        node_name: str,
        state: str,
        evidence: str = "",
        source: str = "manual",
    ) -> dict[str, Any]:
        """Create or update graph node progress for a session."""
        await self._require_owned_session(session_id, user_id)
        existing_rows = await self._graph.list_for_user(user_id, graph_type=graph_type)
        match = next(
            (row for row in existing_rows if row.node_name == node_name and row.session_id == session_id),
            None,
        )
        if match is None:
            row = MaiteGraphNodeProgress(
                user_id=user_id,
                session_id=session_id,
                graph_type=graph_type,
                node_name=node_name,
                state=state,
                evidence=evidence,
                source=source,
            )
            saved = await self._graph.create(row)
        else:
            saved = await self._graph.update_by_id(
                match.id,
                state=state,
                evidence=evidence,
                source=source,
                updated_at=datetime.now(UTC),
            )
        await commit_maite(self._session)
        return self._row_dict(saved)

    async def _require_owned_session(self, session_id: int, user_id: int) -> None:
        row = await self._sessions.get_owned(session_id, user_id)
        if row is None:
            raise MaiteNotFoundError("Session not found")

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        table = getattr(row, "__table__", None)
        if table is None:
            return {}
        return {col.name: getattr(row, col.name) for col in table.columns}
