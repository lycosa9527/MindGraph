"""Celery run lease helpers for Mind Classroom jobs."""

from __future__ import annotations

import logging
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository, MindClassroomSlideRepository
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_STOP_MID_RUN = frozenset({"cancelled", "failed", "partial", "ready"})


class LeaseLost(Exception):
    """This Celery run no longer owns the job (or must stop)."""


async def require_run_lease(
    job_id: str,
    *,
    celery_task_id: Optional[str],
) -> str:
    """Return current status while this task still owns the run."""
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).get_by_uuid(job_id)
        if row is None:
            raise LeaseLost("job missing")
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            raise LeaseLost(f"celery lease lost have={celery_task_id} want={owned}")
        if row.status in _STOP_MID_RUN:
            raise LeaseLost(f"status={row.status}")
        return str(row.status)


async def set_status_with_lease(
    job_id: str,
    *,
    status: str,
    stage: Optional[str] = None,
    progress: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
    result_json: Optional[dict[str, Any]] = None,
    lesson_plan_json: Optional[dict[str, Any]] = None,
    clear_error: bool = False,
    celery_task_id: Optional[str] = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    """Update job status when this task still holds the Celery lease."""
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        row = await repo.get_by_uuid(job_id)
        if row is None:
            raise LeaseLost("job missing")
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            raise LeaseLost(f"celery lease lost have={celery_task_id} want={owned}")
        await repo.update_job(
            job_id,
            status=status,
            current_stage=stage or status,
            progress=progress,
            error_message=error_message,
            result_json=result_json,
            lesson_plan_json=lesson_plan_json,
            clear_error=clear_error,
            started=started,
            finished=finished,
            commit=True,
        )


async def mark_terminal_from_error(
    job_id: str,
    exc: BaseException,
    *,
    celery_task_id: Optional[str] = None,
) -> Optional[str]:
    """Set failed/partial from a pipeline exception when this task still owns the lease."""
    async with system_rls_session() as db:
        job_repo = MindClassroomJobRepository(db)
        row = await job_repo.get_by_uuid(job_id)
        if row is None:
            return None
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            logger.info(
                "[MindClassroom] Skip terminal mark job=%s lease lost have=%s want=%s",
                job_id,
                celery_task_id,
                owned,
            )
            return None
        slides = await MindClassroomSlideRepository(db).list_by_job(job_id)
        status = "partial" if slides else "failed"
        await job_repo.update_job(
            job_id,
            status=status,
            current_stage=status,
            error_message=str(exc)[:2000],
            progress={"phase": status, "slide_count": len(slides)},
            finished=True,
            commit=True,
        )
        return status
