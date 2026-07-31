"""
Maite session reports repository.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from models.domain.maite_artifacts import MaiteSessionReport
from repositories.base import BaseRepository


class MaiteReportsRepository(BaseRepository[MaiteSessionReport]):
    """Async CRUD helpers for ``maite_session_reports``."""

    model = MaiteSessionReport

    async def get_for_session(self, session_id: int) -> Optional[MaiteSessionReport]:
        """Return the report row for an inquiry session, if any."""
        stmt = select(MaiteSessionReport).where(MaiteSessionReport.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
