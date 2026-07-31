"""
Maite graph node progress repository.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from models.domain.maite_artifacts import MaiteGraphNodeProgress
from repositories.base import BaseRepository


class MaiteGraphRepository(BaseRepository[MaiteGraphNodeProgress]):
    """Async CRUD helpers for ``maite_graph_node_progress``."""

    model = MaiteGraphNodeProgress

    async def list_for_user(
        self,
        user_id: int,
        *,
        graph_type: str | None = None,
    ) -> Sequence[MaiteGraphNodeProgress]:
        """List graph nodes for a user, optionally filtered by graph type."""
        stmt = select(MaiteGraphNodeProgress).where(MaiteGraphNodeProgress.user_id == user_id)
        if graph_type:
            stmt = stmt.where(MaiteGraphNodeProgress.graph_type == graph_type)
        stmt = stmt.order_by(MaiteGraphNodeProgress.updated_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
