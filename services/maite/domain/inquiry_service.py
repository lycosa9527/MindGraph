"""
Maite inquiry session domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_learning import MaiteInquirySession
from models.domain.maite_stages import MaiteDecomposeSubmission
from repositories.maite.problems_repo import MaiteProblemsRepository
from repositories.maite.reports_repo import MaiteReportsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.errors import MaiteConflictError, MaiteNotFoundError
from services.maite.domain.public_serializers import (
    model_to_dict,
    public_remedy_task,
    public_variant_task,
)
from services.maite.domain.session_guards import require_mutable_session, require_owned_session
from services.maite.domain.transaction import commit_maite
from services.maite.events import emit_maite_session_event, stop_maite_session_event_bus
from services.maite.redis.practice_cache import (
    get_recent_practice,
    invalidate_recent_practice,
    set_recent_practice,
)
from services.maite.schemas.inquiry import SessionCreate, SessionRead, SnapshotRead

logger = logging.getLogger(__name__)

MIN_VARIANTS_FOR_COMPLETE = 3


class InquiryService:
    """Manage inquiry sessions, snapshots, and lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sessions = MaiteSessionsRepository(session)
        self._problems = MaiteProblemsRepository(session)
        self._stages = MaiteStagesRepository(session)
        self._reports = MaiteReportsRepository(session)

    async def create_session(
        self,
        payload: SessionCreate,
        *,
        user_id: int,
        organization_id: Optional[int],
    ) -> SessionRead:
        """Create a new inquiry session for an owned problem."""
        problem = await self._problems.get_owned(payload.problem_id, user_id)
        if problem is None:
            raise MaiteNotFoundError("Problem not found")
        row = MaiteInquirySession(
            user_id=user_id,
            organization_id=organization_id,
            problem_id=payload.problem_id,
            mode=payload.mode,
            title=payload.title,
            status="created",
            current_stage="decompose",
        )
        created = await self._sessions.create(row)
        await commit_maite(self._session)
        await self._mark_practice_dirty(user_id, created.id)
        logger.info(
            "[Maite] Session created id=%s user=%s problem=%s mode=%s",
            created.id,
            user_id,
            payload.problem_id,
            payload.mode,
        )
        return SessionRead.model_validate(created)

    async def list_sessions(self, user_id: int, *, limit: int = 50) -> list[SessionRead]:
        """List inquiry sessions for a user, preferring a short Redis cache."""
        cached = await get_recent_practice(user_id)
        if cached is not None:
            return [SessionRead.model_validate(item) for item in cached[:limit]]
        rows = await self._sessions.list_for_user(user_id, limit=limit)
        payload = [SessionRead.model_validate(row).model_dump(mode="json") for row in rows]
        await set_recent_practice(user_id, payload)
        return [SessionRead.model_validate(row) for row in rows]

    async def get_session(self, session_id: int, *, user_id: int) -> SessionRead:
        """Return a single owned inquiry session."""
        row = await require_owned_session(self._sessions, session_id, user_id)
        return SessionRead.model_validate(row)

    async def get_snapshot(self, session_id: int, *, user_id: int) -> SnapshotRead:
        """Return aggregated session snapshot across all stages."""
        row = await require_owned_session(self._sessions, session_id, user_id)
        problem = await self._problems.get_by_id(row.problem_id)
        decompose = await self._stages.decompose.get_for_session(session_id)
        diagnosis = await self._stages.diagnosis.get_for_session(session_id)
        remedy_tasks = await self._stages.remedy.list_for_session(session_id)
        variant_tasks = await self._stages.variant.list_for_session(session_id)
        report = await self._reports.get_for_session(session_id)
        return SnapshotRead(
            session={
                "id": row.id,
                "status": row.status,
                "current_stage": row.current_stage,
                "title": row.title,
                "mode": row.mode,
            },
            problem=model_to_dict(problem) if problem else None,
            decompose=model_to_dict(decompose),
            diagnosis=model_to_dict(diagnosis),
            remedy_tasks=[public_remedy_task(task) for task in remedy_tasks],
            variant_tasks=[public_variant_task(task) for task in variant_tasks],
            report=model_to_dict(report),
        )

    async def submit_decompose(
        self,
        session_id: int,
        *,
        user_id: int,
        condition_table: list[Any],
        step_table: list[Any],
        model_table: list[Any],
        validation_warnings: Optional[list[Any]] = None,
    ) -> dict[str, Any]:
        """Persist decompose tables and advance to diagnosis stage."""
        row = await require_mutable_session(self._sessions, session_id, user_id)
        existing = await self._stages.decompose.get_for_session(session_id)
        if existing is not None:
            raise MaiteConflictError("Decompose already submitted")
        submission = MaiteDecomposeSubmission(
            session_id=session_id,
            condition_table=condition_table,
            step_table=step_table,
            model_table=model_table,
            validation_warnings=validation_warnings or [],
        )
        created = await self._stages.decompose.create(submission)
        await self._sessions.update_by_id(
            row.id,
            current_stage="diagnosis",
            status="in_progress",
            updated_at=datetime.now(UTC),
        )
        await commit_maite(self._session)
        await self._mark_practice_dirty(user_id, session_id)
        logger.info(
            "[Maite] Decompose submitted session=%s user=%s -> diagnosis",
            session_id,
            user_id,
        )
        return model_to_dict(created) or {}

    async def redo_session(
        self,
        session_id: int,
        *,
        user_id: int,
        reason: Optional[str] = None,
    ) -> SessionRead:
        """Start a new version of an inquiry session."""
        original = await require_owned_session(self._sessions, session_id, user_id)
        row = MaiteInquirySession(
            user_id=user_id,
            organization_id=original.organization_id,
            problem_id=original.problem_id,
            mode=original.mode,
            title=original.title,
            status="created",
            current_stage="decompose",
            original_session_id=original.original_session_id or original.id,
            version_no=original.version_no + 1,
            redo_reason=reason,
        )
        created = await self._sessions.create(row)
        await commit_maite(self._session)
        await self._mark_practice_dirty(user_id, created.id)
        return SessionRead.model_validate(created)

    async def complete_session(self, session_id: int, *, user_id: int) -> SessionRead:
        """Mark session completed when required variant tasks are submitted."""
        row = await require_mutable_session(self._sessions, session_id, user_id)
        submitted = await self._stages.variant.count_submitted(session_id)
        if submitted < MIN_VARIANTS_FOR_COMPLETE:
            logger.warning(
                "[Maite] Complete blocked session=%s user=%s submitted=%s required=%s",
                session_id,
                user_id,
                submitted,
                MIN_VARIANTS_FOR_COMPLETE,
            )
            raise MaiteConflictError(f"At least {MIN_VARIANTS_FOR_COMPLETE} variant tasks must be submitted")
        updated = await self._sessions.update_by_id(
            row.id,
            status="completed",
            current_stage="completed",
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        if updated is None:
            raise MaiteNotFoundError("Session not found")
        await commit_maite(self._session)
        await invalidate_recent_practice(user_id)
        await emit_maite_session_event(
            str(session_id),
            "session_completed",
            {"session_id": session_id, "user_id": user_id},
        )
        await stop_maite_session_event_bus(str(session_id))
        logger.info(
            "[Maite] Session completed id=%s user=%s variants=%s",
            session_id,
            user_id,
            submitted,
        )
        return SessionRead.model_validate(updated)

    async def _mark_practice_dirty(self, user_id: int, session_id: int) -> None:
        await invalidate_recent_practice(user_id)
        await emit_maite_session_event(
            str(session_id),
            "practice_dirty",
            {"user_id": user_id, "session_id": session_id},
        )
