"""Cold Postgres manifesto for Mind Classroom lecture jobs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.celery_log import classroom_status_changed, log_classroom_celery
from services.mind_classroom.job_events import publish_classroom_job_snapshot
from utils.db.session_open import system_rls_session

JOB_QUEUED = "queued"
JOB_PLANNING = "planning"
JOB_GENERATING = "generating"
JOB_READY = "ready"
JOB_PARTIAL = "partial"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

_ACTIVE = frozenset({JOB_QUEUED, JOB_PLANNING, JOB_GENERATING})
_TERMINAL = frozenset({JOB_READY, JOB_PARTIAL, JOB_FAILED, JOB_CANCELLED})


def should_apply_job_stage(previous: Optional[str], next_status: str) -> bool:
    """Refuse writes that resurrect a cancelled or finished job."""
    if previous == JOB_CANCELLED:
        return False
    if previous in _TERMINAL and next_status in _ACTIVE:
        return False
    return True


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
    await publish_classroom_job_snapshot(job_id)


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
    record_attempt: bool = True,
) -> None:
    """Update job status/stage on the manifesto."""
    previous_status: Optional[str] = None
    previous_stage: Optional[str] = None
    owned: Optional[str] = None
    payload = progress or {"phase": stage}
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        row = await repo.get_by_uuid(job_id)
        if row is not None:
            previous_status = row.status
            previous_stage = row.current_stage
            owned = row.celery_task_id
        if not should_apply_job_stage(previous_status, status):
            return
        await repo.update_job(
            job_id,
            status=status,
            current_stage=stage,
            progress=payload,
            result_json=result_json,
            lesson_plan_json=lesson_plan_json,
            celery_task_id=celery_task_id,
            error_message=error_message,
            clear_error=clear_error,
            increment_attempt=record_attempt and status in _ACTIVE,
            attempt_entry=_attempt_entry(status, stage, error_message) if record_attempt else None,
            started=started,
            finished=finished,
            commit=True,
        )
    if classroom_status_changed(previous_status, previous_stage, status, stage):
        phase = payload.get("phase") if isinstance(payload, dict) else None
        detail = None
        if isinstance(phase, str) and phase and phase not in {status, stage}:
            detail = f"phase={phase}"
        log_classroom_celery(
            "status",
            job_id=job_id,
            celery_task_id=celery_task_id or owned,
            status=status,
            stage=stage,
            detail=detail,
        )
    await publish_classroom_job_snapshot(job_id)


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
