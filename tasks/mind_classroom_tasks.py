"""Celery runners for Mind Classroom lecture jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

from config.celery import celery_app
from repositories.mind_classroom_repo import MindClassroomJobRepository, MindClassroomSlideRepository
from services.infrastructure.http.error_handler import LLMServiceError
from services.mind_classroom.canvas_tour import run_canvas_tour_job
from services.mind_classroom.slide_deck import run_slide_deck_job
from services.monitoring.error_reporting import record_exception_from_celery
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_SCRIPT_SOFT = 120
_SCRIPT_HARD = 150
_SLIDE_SOFT = 2400
_SLIDE_HARD = 2460
_TASK_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + (LLMServiceError, SoftTimeLimitExceeded, TimeLimitExceeded)


def _run_script(job_id: str, celery_task_id: Optional[str]) -> bool:
    return bool(asyncio.run(run_canvas_tour_job(job_id, celery_task_id=celery_task_id)))


def _run_slides(job_id: str, celery_task_id: Optional[str]) -> bool:
    return bool(asyncio.run(run_slide_deck_job(job_id, celery_task_id=celery_task_id)))


async def _mark_terminal(job_id: str, message: str, *, celery_task_id: Optional[str] = None) -> None:
    async with system_rls_session() as db:
        job_repo = MindClassroomJobRepository(db)
        row = await job_repo.get_by_uuid(job_id)
        if row is None:
            return
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            return
        slides = await MindClassroomSlideRepository(db).list_by_job(job_id)
        status = "partial" if slides else "failed"
        await job_repo.update_job(
            job_id,
            status=status,
            current_stage=status,
            error_message=message[:2000],
            progress={"phase": status, "slide_count": len(slides)},
            finished=True,
            commit=True,
        )


def _handle_task_error(job_id: str, celery_task_id: Optional[str], exc: BaseException, component: str) -> None:
    record_exception_from_celery(
        source="background",
        component=component,
        exc=exc,
        tags={"job_id": job_id},
    )
    try:
        asyncio.run(_mark_terminal(job_id, str(exc), celery_task_id=celery_task_id))
    except _TASK_ERRORS:
        pass


@celery_app.task(
    bind=True,
    name="mind_classroom.run_script",
    queue="default",
    max_retries=0,
    soft_time_limit=_SCRIPT_SOFT,
    time_limit=_SCRIPT_HARD,
)
def run_script_task(self, job_id: str) -> bool:
    """Short canvas-tour script generation."""
    task_id = getattr(self.request, "id", None)
    task_id_str = task_id if isinstance(task_id, str) else None
    try:
        return _run_script(job_id, task_id_str)
    except SoftTimeLimitExceeded as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomScriptTask")
        return False
    except TimeLimitExceeded as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomScriptTask")
        raise
    except _TASK_ERRORS as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomScriptTask")
        return False


@celery_app.task(
    bind=True,
    name="mind_classroom.run_slides",
    queue="default",
    max_retries=0,
    soft_time_limit=_SLIDE_SOFT,
    time_limit=_SLIDE_HARD,
)
def run_slides_task(self, job_id: str) -> bool:
    """Long slide-deck Wan generation."""
    task_id = getattr(self.request, "id", None)
    task_id_str = task_id if isinstance(task_id, str) else None
    try:
        return _run_slides(job_id, task_id_str)
    except SoftTimeLimitExceeded as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomSlideTask")
        return False
    except TimeLimitExceeded as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomSlideTask")
        raise
    except _TASK_ERRORS as exc:
        _handle_task_error(job_id, task_id_str, exc, "MindClassroomSlideTask")
        return False
