"""Enqueue Mind Classroom Celery jobs and write the manifesto."""

from __future__ import annotations

import logging
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.celery_log import log_classroom_celery
from services.mind_classroom.job_manifest import hash_spec_snapshot, mark_job_failed, mark_job_queued
from services.mind_classroom.queue_dispatch import (
    WORKER_MISSING_MSG,
    ensure_queued_dispatch,
    send_classroom_task,
    task_name_for_settings,
    workers_register_task,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

TASK_SCRIPT = "mind_classroom.run_script"
TASK_SLIDES = "mind_classroom.run_slides"


def _task_name(mode: str) -> str:
    return TASK_SLIDES if mode == "slide_deck" else TASK_SCRIPT


async def _reuse_payload(job_id: str, status: str, settings: dict[str, Any]) -> dict[str, Any]:
    if status == "queued":
        status = await ensure_queued_dispatch(job_id, task_name_for_settings(settings))
    log_classroom_celery(
        "reuse",
        job_id=job_id,
        status=status,
        detail=f"mode={settings.get('mode') or 'canvas_tour'}",
    )
    return {"job_id": job_id, "status": status, "reused": True}


async def create_and_enqueue_job(
    *,
    user_id: int,
    spec_snapshot: dict[str, Any],
    settings: dict[str, Any],
    organization_id: Optional[int] = None,
    diagram_id: Optional[str] = None,
    reuse: bool = True,
) -> dict[str, Any]:
    """
    Create a classroom job (or reuse a ready/in-flight one) and enqueue Celery.

    Returns a public job payload including ``reused``.
    """
    spec_hash = hash_spec_snapshot(spec_snapshot)
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        if reuse:
            existing = await repo.find_reusable(
                user_id=user_id,
                spec_hash=spec_hash,
                settings=settings,
            )
            if existing is not None:
                return await _reuse_payload(existing.id, existing.status, settings)
        active = await repo.count_active_jobs(user_id)
        if active >= repo.max_active_jobs():
            raise RuntimeError(f"Too many active classroom jobs ({active}/{repo.max_active_jobs()}). Wait or cancel.")
        job = await repo.create_job(
            user_id=user_id,
            spec_snapshot=spec_snapshot,
            settings=settings,
            spec_hash=spec_hash,
            organization_id=organization_id,
            diagram_id=diagram_id,
            commit=True,
        )

    mode = str(settings.get("mode") or "canvas_tour")
    task_name = _task_name(mode)
    if workers_register_task(task_name) is False:
        await mark_job_failed(job.id, WORKER_MISSING_MSG)
        log_classroom_celery(
            "error",
            job_id=job.id,
            status="failed",
            detail="reason=worker_missing_task",
        )
        return {"job_id": job.id, "status": "failed", "reused": False, "celery_task_id": None}

    task_id: Optional[str] = None
    try:
        task_id = send_classroom_task(task_name, job.id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindClassroom] Enqueue failed job=%s err=%s", job.id, exc)
        await mark_job_failed(job.id, f"enqueue_failed: {exc}")
        return {"job_id": job.id, "status": "failed", "reused": False, "celery_task_id": None}

    if task_id:
        await mark_job_queued(job.id, celery_task_id=task_id)
    log_classroom_celery(
        "enqueue",
        job_id=job.id,
        celery_task_id=task_id,
        status="queued",
        detail=f"mode={mode} task={task_name}",
    )
    return {
        "job_id": job.id,
        "status": "queued",
        "reused": False,
        "celery_task_id": task_id,
    }
