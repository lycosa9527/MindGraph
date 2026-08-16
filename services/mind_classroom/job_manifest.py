"""Cold Postgres manifesto for Mind Classroom lecture jobs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.celery_log import classroom_status_changed, log_classroom_celery
from utils.db.session_open import system_rls_session

JOB_QUEUED = "queued"
JOB_PLANNING = "planning"
JOB_GENERATING = "generating"
JOB_READY = "ready"
JOB_PARTIAL = "partial"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

_ACTIVE = frozenset({JOB_QUEUED, JOB_PLANNING, JOB_GENERATING})


def hash_spec_snapshot(spec: dict[str, Any]) -> str:
    """Stable SHA-256 of the spec snapshot used for job reuse."""
    payload = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _attempt_entry(status: str, stage: Optional[str], message: Optional[str] = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "status": status,
        "stage": stage,
        "at": datetime.now(UTC).isoformat(),
    }
    if message:
        entry["message"] = message[:500]
    return entry


async def mark_job_queued(
    job_id: str,
    *,
    celery_task_id: Optional[str] = None,
) -> None:
    """Record that Celery accepted the job."""
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        await repo.update_job(
            job_id,
            status=JOB_QUEUED,
            current_stage="queued",
            progress={"phase": "queued"},
            celery_task_id=celery_task_id,
            attempt_entry=_attempt_entry(JOB_QUEUED, "queued"),
            commit=True,
        )


async def mark_job_stage(
    job_id: str,
    *,
    status: str,
    stage: str,
    progress: Optional[dict[str, Any]] = None,
    result_json: Optional[dict[str, Any]] = None,
    lesson_plan_json: Optional[dict[str, Any]] = None,
    celery_task_id: Optional[str] = None,
    error_message: Optional[str] = None,
    clear_error: bool = False,
    started: bool = False,
    finished: bool = False,
) -> None:
    """Update job status/stage on the manifesto."""
    previous_status: Optional[str] = None
    previous_stage: Optional[str] = None
    owned: Optional[str] = None
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        row = await repo.get_by_uuid(job_id)
        if row is not None:
            previous_status = row.status
            previous_stage = row.current_stage
            owned = row.celery_task_id
        await repo.update_job(
            job_id,
            status=status,
            current_stage=stage,
            progress=progress or {"phase": stage},
            result_json=result_json,
            lesson_plan_json=lesson_plan_json,
            celery_task_id=celery_task_id,
            error_message=error_message,
            clear_error=clear_error,
            increment_attempt=status in _ACTIVE,
            attempt_entry=_attempt_entry(status, stage, error_message),
            started=started,
            finished=finished,
            commit=True,
        )
    if classroom_status_changed(previous_status, previous_stage, status, stage):
        log_classroom_celery(
            "status",
            job_id=job_id,
            celery_task_id=celery_task_id or owned,
            status=status,
            stage=stage,
        )


async def mark_job_ready(
    job_id: str,
    *,
    result_json: dict[str, Any],
    progress: Optional[dict[str, Any]] = None,
    celery_task_id: Optional[str] = None,
) -> None:
    """Mark the job ready with lecture steps."""
    await mark_job_stage(
        job_id,
        status=JOB_READY,
        stage="ready",
        progress=progress or {"phase": "ready"},
        result_json=result_json,
        celery_task_id=celery_task_id,
        clear_error=True,
        finished=True,
    )


async def mark_job_failed(
    job_id: str,
    message: str,
    *,
    status: str = JOB_FAILED,
    progress: Optional[dict[str, Any]] = None,
    celery_task_id: Optional[str] = None,
) -> None:
    """Mark the job failed or partial."""
    await mark_job_stage(
        job_id,
        status=status,
        stage=status,
        progress=progress or {"phase": status},
        error_message=message[:2000],
        celery_task_id=celery_task_id,
        finished=True,
    )
