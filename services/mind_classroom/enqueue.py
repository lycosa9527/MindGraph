"""Enqueue Mind Classroom Celery jobs and write the manifesto."""

from __future__ import annotations

import logging
from typing import Any, Optional

from config.celery import celery_app
from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.job_manifest import hash_spec_snapshot, mark_job_failed, mark_job_queued
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

TASK_SCRIPT = "mind_classroom.run_script"
TASK_SLIDES = "mind_classroom.run_slides"


def _task_name(mode: str) -> str:
    return TASK_SLIDES if mode == "slide_deck" else TASK_SCRIPT


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
    Create a classroom job (or reuse a ready one) and enqueue Celery.

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
                return {"job_id": existing.id, "status": existing.status, "reused": True}
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
    task_id: Optional[str] = None
    try:
        async_result = celery_app.send_task(_task_name(mode), kwargs={"job_id": job.id}, queue="default")
        task_id = str(async_result.id) if async_result.id else None
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindClassroom] Enqueue failed job=%s err=%s", job.id, exc)
        await mark_job_failed(job.id, f"enqueue_failed: {exc}")
        return {"job_id": job.id, "status": "failed", "reused": False, "celery_task_id": None}

    if task_id:
        await mark_job_queued(job.id, celery_task_id=task_id)
    return {
        "job_id": job.id,
        "status": "queued",
        "reused": False,
        "celery_task_id": task_id,
    }
