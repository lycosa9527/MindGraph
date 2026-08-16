"""Re-dispatch Mind Classroom jobs that stay queued because Celery never claimed them."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from config.celery import celery_app
from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.celery_log import log_classroom_celery
from services.mind_classroom.job_manifest import mark_job_failed, mark_job_queued
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

KICK_AFTER_SECONDS = 20
QUEUED_GIVE_UP_SECONDS = 180
WORKER_MISSING_MSG = "Celery worker did not pick up this lecture job. Restart Celery after deploy, then tap Restart."


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def queued_watch_action(
    created_at: datetime,
    updated_at: datetime,
    *,
    now: Optional[datetime] = None,
) -> str:
    """Return wait, kick, or fail for a job that is still queued."""
    current = now or datetime.now(UTC)
    created_age = (current - _aware(created_at)).total_seconds()
    idle_age = (current - _aware(updated_at)).total_seconds()
    if created_age >= QUEUED_GIVE_UP_SECONDS:
        return "fail"
    if idle_age >= KICK_AFTER_SECONDS:
        return "kick"
    return "wait"


def workers_register_task(task_name: str) -> Optional[bool]:
    """True/False when inspect works; None when the broker does not answer."""
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        registered = inspect.registered()
    except BACKGROUND_INFRA_ERRORS:
        return None
    if not registered:
        return None
    return any(task_name in (tasks or []) for tasks in registered.values())


def send_classroom_task(task_name: str, job_id: str) -> Optional[str]:
    """Enqueue one classroom Celery task. Returns the task id."""
    async_result = celery_app.send_task(task_name, kwargs={"job_id": job_id}, queue="default")
    return str(async_result.id) if async_result.id else None


async def ensure_queued_dispatch(job_id: str, task_name: str) -> str:
    """Kick or fail a job still sitting in queued. Returns the current status."""
    action = "wait"
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).get_by_uuid(job_id)
        if row is None:
            return "missing"
        if row.status != "queued":
            return str(row.status)
        action = queued_watch_action(row.created_at, row.updated_at)
    if action == "wait":
        return "queued"
    if action == "fail" or workers_register_task(task_name) is False:
        await mark_job_failed(job_id, WORKER_MISSING_MSG)
        log_classroom_celery(
            "error",
            job_id=job_id,
            status="failed",
            detail="reason=worker_missing_or_timeout",
        )
        return "failed"
    try:
        task_id = send_classroom_task(task_name, job_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindClassroom] Kick failed job=%s err=%s", job_id, exc)
        return "queued"
    if task_id:
        await mark_job_queued(job_id, celery_task_id=task_id)
        log_classroom_celery(
            "kick",
            job_id=job_id,
            celery_task_id=task_id,
            status="queued",
            detail=f"task={task_name}",
        )
    return "queued"


def task_name_for_settings(settings: Optional[dict[str, Any]]) -> str:
    """Celery task name from job settings."""
    mode = str((settings or {}).get("mode") or "canvas_tour")
    return "mind_classroom.run_slides" if mode == "slide_deck" else "mind_classroom.run_script"
