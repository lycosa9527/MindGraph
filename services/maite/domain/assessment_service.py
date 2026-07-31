"""
Maite self-assessment domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_stages import MaiteSelfAssessment
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.errors import MaiteConflictError, MaiteNotFoundError


class AssessmentService:
    """Persist student mastery self-assessments."""

    def __init__(self, session: AsyncSession) -> None:
        self._sessions = MaiteSessionsRepository(session)
        self._stages = MaiteStagesRepository(session)

    async def save_assessment(
        self,
        session_id: int,
        *,
        items: list[dict[str, Any]],
        user_id: int,
    ) -> dict[str, Any]:
        """Save mastery self-assessment items for a session."""
        inquiry = await self._sessions.get_owned(session_id, user_id)
        if inquiry is None:
            raise MaiteNotFoundError("Session not found")
        if inquiry.status == "completed":
            raise MaiteConflictError("Completed sessions are read-only")
        row = MaiteSelfAssessment(session_id=session_id, items=items)
        saved = await self._stages.self_assessment.create(row)
        await self._sessions.update_by_id(
            inquiry.id,
            status="assessed",
            current_stage="self_assessment",
            updated_at=datetime.now(UTC),
        )
        return self._row_dict(saved)

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        table = getattr(row, "__table__", None)
        if table is None:
            return {}
        return {col.name: getattr(row, col.name) for col in table.columns}
