"""Repository for Mind Classroom jobs and slides."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional, Sequence

from sqlalchemy import desc, func, select

from models.domain.mind_classroom import (
    MindClassroomJob,
    MindClassroomSlide,
    generate_classroom_id,
)
from repositories.base import BaseRepository

_ACTIVE_STATUSES = ("queued", "planning", "generating")
_DEFAULT_STALE_MINUTES = 60
_MAX_ACTIVE_JOBS = 1
_ATTEMPTS_CAP = 20


class MindClassroomSlideRepository(BaseRepository[MindClassroomSlide]):
    """Async CRUD for mind_classroom_slides."""

    model = MindClassroomSlide

    async def get_by_logical_key(self, logical_key: str) -> Optional[MindClassroomSlide]:
        """Load one slide by COS logical key."""
        cleaned = (logical_key or "").strip()
        if not cleaned:
            return None
        stmt = select(MindClassroomSlide).where(MindClassroomSlide.cos_logical_key == cleaned).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_job(self, job_id: str) -> Sequence[MindClassroomSlide]:
        """Ordered slides for one job."""
        stmt = (
            select(MindClassroomSlide)
            .where(MindClassroomSlide.job_id == job_id)
            .order_by(MindClassroomSlide.slide_index.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_slide(
        self,
        *,
        slide_id: str,
        job_id: str,
        user_id: int,
        slide_index: int,
        cos_logical_key: str,
        title: Optional[str] = None,
        teacher_script: Optional[str] = None,
        focus_node_ids: Optional[list[Any]] = None,
        content_type: str = "image/png",
        size: Optional[str] = None,
        prompt: Optional[str] = None,
        commit: bool = True,
    ) -> MindClassroomSlide:
        """Insert one slide row."""
        row = MindClassroomSlide(
            id=slide_id,
            job_id=job_id,
            user_id=user_id,
            slide_index=slide_index,
            title=title[:256] if title else None,
            teacher_script=teacher_script,
            focus_node_ids=focus_node_ids,
            cos_logical_key=cos_logical_key,
            content_type=content_type,
            size=size,
            prompt=prompt[:4000] if prompt else None,
        )
        self.session.add(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def delete_by_job(self, job_id: str, *, commit: bool = True) -> list[str]:
        """Delete slides for a job. Returns COS keys."""
        rows = list(await self.list_by_job(job_id))
        keys = [row.cos_logical_key for row in rows if row.cos_logical_key]
        for row in rows:
            await self.session.delete(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return keys


class MindClassroomJobRepository(BaseRepository[MindClassroomJob]):
    """Async CRUD for mind_classroom_jobs."""

    model = MindClassroomJob

    async def get_by_uuid(self, job_id: str) -> Optional[MindClassroomJob]:
        """Load one job by UUID."""
        return await self.session.get(MindClassroomJob, job_id)

    async def count_active_jobs(self, user_id: int) -> int:
        """Count non-terminal jobs for concurrency gating."""
        stmt = (
            select(func.count())
            .select_from(MindClassroomJob)
            .where(
                MindClassroomJob.user_id == user_id,
                MindClassroomJob.status.in_(_ACTIVE_STATUSES),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    @staticmethod
    def max_active_jobs() -> int:
        """Per-user concurrent classroom job cap."""
        return _MAX_ACTIVE_JOBS

    async def find_reusable(
        self,
        *,
        user_id: int,
        spec_hash: str,
        settings: dict[str, Any],
    ) -> Optional[MindClassroomJob]:
        """Latest ready/partial job with the same spec hash and settings."""
        stmt = (
            select(MindClassroomJob)
            .where(
                MindClassroomJob.user_id == user_id,
                MindClassroomJob.spec_hash == spec_hash,
                MindClassroomJob.status.in_(("ready", "partial")),
            )
            .order_by(desc(MindClassroomJob.updated_at))
            .limit(8)
        )
        result = await self.session.execute(stmt)
        for row in result.scalars().all():
            if row.settings == settings:
                return row
        return None

    async def latest_job_for_diagram(
        self,
        *,
        user_id: int,
        diagram_id: str,
        mode: Optional[str] = None,
    ) -> Optional[MindClassroomJob]:
        """Newest classroom job for a library mind map, optionally filtered by mode."""
        cleaned = (diagram_id or "").strip()
        if not cleaned:
            return None
        stmt = (
            select(MindClassroomJob)
            .where(
                MindClassroomJob.user_id == user_id,
                MindClassroomJob.diagram_id == cleaned,
            )
            .order_by(desc(MindClassroomJob.updated_at))
            .limit(12)
        )
        result = await self.session.execute(stmt)
        for row in result.scalars().all():
            row_mode = (row.settings or {}).get("mode")
            if mode and row_mode != mode:
                continue
            return row
        return None

    async def latest_slide_job_for_diagram(
        self,
        *,
        user_id: int,
        diagram_id: str,
    ) -> Optional[MindClassroomJob]:
        """Newest slide_deck job for a library mind map."""
        return await self.latest_job_for_diagram(
            user_id=user_id,
            diagram_id=diagram_id,
            mode="slide_deck",
        )

    async def create_job(
        self,
        *,
        user_id: int,
        spec_snapshot: dict[str, Any],
        settings: dict[str, Any],
        spec_hash: str,
        organization_id: Optional[int] = None,
        diagram_id: Optional[str] = None,
        job_id: Optional[str] = None,
        commit: bool = True,
    ) -> MindClassroomJob:
        """Insert a queued job row."""
        now = datetime.now(UTC)
        row = MindClassroomJob(
            id=job_id or generate_classroom_id(),
            user_id=user_id,
            organization_id=organization_id,
            diagram_id=diagram_id,
            spec_snapshot=spec_snapshot,
            settings=settings,
            spec_hash=spec_hash,
            status="queued",
            current_stage="queued",
            progress={"phase": "queued"},
            attempt_count=0,
            attempts=[],
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        current_stage: Optional[str] = None,
        progress: Optional[dict[str, Any]] = None,
        result_json: Optional[dict[str, Any]] = None,
        lesson_plan_json: Optional[dict[str, Any]] = None,
        celery_task_id: Optional[str] = None,
        error_message: Optional[str] = None,
        clear_error: bool = False,
        increment_attempt: bool = False,
        attempt_entry: Optional[dict[str, Any]] = None,
        started: bool = False,
        finished: bool = False,
        commit: bool = True,
    ) -> Optional[MindClassroomJob]:
        """Patch mutable job fields."""
        row = await self.get_by_uuid(job_id)
        if row is None:
            return None
        now = datetime.now(UTC)
        if status is not None:
            row.status = status
        if current_stage is not None:
            row.current_stage = current_stage
        if progress is not None:
            row.progress = progress
        if result_json is not None:
            row.result_json = result_json
        if lesson_plan_json is not None:
            row.lesson_plan_json = lesson_plan_json
        if celery_task_id is not None:
            row.celery_task_id = celery_task_id
        if clear_error:
            row.error_message = None
        elif error_message is not None:
            row.error_message = error_message
        if increment_attempt:
            row.attempt_count = int(row.attempt_count or 0) + 1
        if attempt_entry is not None:
            history = list(row.attempts or [])
            history.append(attempt_entry)
            row.attempts = history[-_ATTEMPTS_CAP:]
        if started and row.started_at is None:
            row.started_at = now
        if finished:
            row.finished_at = now
        row.updated_at = now
        await self.session.flush()
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        return row

    async def claim_for_run(
        self,
        job_id: str,
        *,
        celery_task_id: Optional[str] = None,
    ) -> Optional[MindClassroomJob]:
        """Claim a job for the worker. ``queued`` → ``planning``."""
        row = await self.get_by_uuid(job_id)
        if row is None:
            return None
        if row.status in ("ready", "cancelled"):
            return row
        if row.status in ("failed", "partial"):
            if not isinstance(row.lesson_plan_json, dict) and not isinstance(row.result_json, dict):
                return row
            row.status = "planning"
            row.current_stage = "planning"
            row.progress = {"phase": "planning", "resumed": True}
            row.error_message = None
        if celery_task_id:
            row.celery_task_id = celery_task_id
        if row.status == "queued":
            row.status = "planning"
            row.current_stage = "planning"
            row.progress = {"phase": "planning"}
            row.error_message = None
        if row.started_at is None:
            row.started_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def mark_stale_active_jobs(
        self,
        *,
        max_age_minutes: int = _DEFAULT_STALE_MINUTES,
        user_id: Optional[int] = None,
    ) -> tuple[int, list[str]]:
        """Mark long-stuck jobs failed/partial. Returns (count, celery ids)."""
        cutoff = datetime.now(UTC) - timedelta(minutes=max(5, int(max_age_minutes)))
        stmt = select(MindClassroomJob).where(
            MindClassroomJob.status.in_(_ACTIVE_STATUSES),
            MindClassroomJob.updated_at < cutoff,
        )
        if user_id is not None:
            stmt = stmt.where(MindClassroomJob.user_id == user_id)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return 0, []
        slide_repo = MindClassroomSlideRepository(self.session)
        updated = 0
        task_ids: list[str] = []
        for row in rows:
            slides = await slide_repo.list_by_job(row.id)
            row.status = "partial" if slides else "failed"
            row.current_stage = row.status
            row.error_message = (f"Timed out after {max_age_minutes} minutes without progress")[:2000]
            row.progress = {"phase": row.status, "slide_count": len(slides), "stale": True}
            row.finished_at = datetime.now(UTC)
            row.updated_at = datetime.now(UTC)
            if row.celery_task_id:
                task_ids.append(str(row.celery_task_id))
            updated += 1
        if updated:
            await self.session.commit()
        return updated, task_ids

    async def delete_job(self, job_id: str, *, commit: bool = True) -> bool:
        """Delete job and cascaded slides."""
        row = await self.get_by_uuid(job_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return True
