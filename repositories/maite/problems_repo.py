"""
Maite problems repository.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select

from models.domain.maite_learning import MaiteProblem
from repositories.base import BaseRepository


class MaiteProblemsRepository(BaseRepository[MaiteProblem]):
    """Async CRUD helpers for ``maite_problems``."""

    model = MaiteProblem

    async def list_for_user(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[MaiteProblem]:
        """List problems owned by a user, newest first."""
        stmt = (
            select(MaiteProblem)
            .where(MaiteProblem.user_id == user_id)
            .order_by(MaiteProblem.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_owned(self, problem_id: int, user_id: int) -> Optional[MaiteProblem]:
        """Fetch a problem only when it belongs to ``user_id``."""
        stmt = select(MaiteProblem).where(
            MaiteProblem.id == problem_id,
            MaiteProblem.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
