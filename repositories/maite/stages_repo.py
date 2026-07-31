"""
Maite stage artifacts repository.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_artifacts import MaitePromptRun, MaiteTaskReference
from models.domain.maite_stages import (
    MaiteDecomposeSubmission,
    MaiteDiagnosisResult,
    MaiteProblemAnalysis,
    MaiteRemedyTask,
    MaiteSelfAssessment,
    MaiteVariantTask,
)
from repositories.base import BaseRepository


class MaiteProblemAnalysisRepository(BaseRepository[MaiteProblemAnalysis]):
    """Async helpers for problem analysis rows."""

    model = MaiteProblemAnalysis


class MaiteSelfAssessmentRepository(BaseRepository[MaiteSelfAssessment]):
    """Async helpers for self-assessment rows."""

    model = MaiteSelfAssessment

    async def get_for_session(self, session_id: int) -> Optional[MaiteSelfAssessment]:
        """Return the self-assessment for a session, if present."""
        stmt = select(MaiteSelfAssessment).where(MaiteSelfAssessment.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class MaiteDecomposeRepository(BaseRepository[MaiteDecomposeSubmission]):
    """Async helpers for decompose submissions."""

    model = MaiteDecomposeSubmission

    async def get_for_session(self, session_id: int) -> Optional[MaiteDecomposeSubmission]:
        """Return the decompose submission for a session, if present."""
        stmt = select(MaiteDecomposeSubmission).where(MaiteDecomposeSubmission.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class MaiteDiagnosisRepository(BaseRepository[MaiteDiagnosisResult]):
    """Async helpers for diagnosis results."""

    model = MaiteDiagnosisResult

    async def get_for_session(self, session_id: int) -> Optional[MaiteDiagnosisResult]:
        """Return the diagnosis result for a session, if present."""
        stmt = select(MaiteDiagnosisResult).where(MaiteDiagnosisResult.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class MaiteRemedyTaskRepository(BaseRepository[MaiteRemedyTask]):
    """Async helpers for remedy tasks."""

    model = MaiteRemedyTask

    async def list_for_session(self, session_id: int) -> Sequence[MaiteRemedyTask]:
        """List remedy tasks for a session in creation order."""
        stmt = (
            select(MaiteRemedyTask).where(MaiteRemedyTask.session_id == session_id).order_by(MaiteRemedyTask.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class MaiteVariantTaskRepository(BaseRepository[MaiteVariantTask]):
    """Async helpers for variant tasks."""

    model = MaiteVariantTask

    async def list_for_session(self, session_id: int) -> Sequence[MaiteVariantTask]:
        """List variant tasks for a session in creation order."""
        stmt = (
            select(MaiteVariantTask)
            .where(MaiteVariantTask.session_id == session_id)
            .order_by(MaiteVariantTask.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_submitted(self, session_id: int) -> int:
        """Count variant tasks marked submitted for completion gating."""
        stmt = select(MaiteVariantTask).where(
            MaiteVariantTask.session_id == session_id,
            MaiteVariantTask.status == "submitted",
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())


class MaiteTaskReferenceRepository(BaseRepository[MaiteTaskReference]):
    """Async helpers for server-only task answer keys."""

    model = MaiteTaskReference

    async def get_for_task(self, task_kind: str, task_id: int) -> Optional[MaiteTaskReference]:
        """Load a private answer key for a remedy/variant task."""
        stmt = select(MaiteTaskReference).where(
            MaiteTaskReference.task_kind == task_kind,
            MaiteTaskReference.task_id == task_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class MaitePromptRunRepository(BaseRepository[MaitePromptRun]):
    """Async helpers for prompt audit rows."""

    model = MaitePromptRun


class MaiteStagesRepository:
    """Facade grouping stage repositories for convenience."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.analysis = MaiteProblemAnalysisRepository(session)
        self.self_assessment = MaiteSelfAssessmentRepository(session)
        self.decompose = MaiteDecomposeRepository(session)
        self.diagnosis = MaiteDiagnosisRepository(session)
        self.remedy = MaiteRemedyTaskRepository(session)
        self.variant = MaiteVariantTaskRepository(session)
        self.task_reference = MaiteTaskReferenceRepository(session)
        self.prompt_run = MaitePromptRunRepository(session)
