"""Structured Mind Classroom Celery / job-status log lines."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("services.mind_classroom")

_CELERY_ERROR_EVENTS = frozenset({"error"})


def classroom_status_changed(
    previous_status: Optional[str],
    previous_stage: Optional[str],
    status: str,
    stage: Optional[str],
) -> bool:
    """True when manifesto status or stage actually moved."""
    next_stage = stage or status
    return previous_status != status or (previous_stage or "") != next_stage


def format_classroom_celery_line(
    event: str,
    *,
    job_id: str,
    celery_task_id: Optional[str] = None,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    detail: Optional[str] = None,
) -> str:
    """One-line Celery status for API and worker logs."""
    parts = [f"[MindClassroom] Celery {event} job={job_id}"]
    if celery_task_id:
        parts.append(f"task={celery_task_id}")
    if status:
        parts.append(f"status={status}")
    if stage and stage != status:
        parts.append(f"stage={stage}")
    if detail:
        parts.append(detail)
    return " ".join(parts)


def celery_log_level(event: str) -> int:
    """ERROR for failed dispatch/run; INFO for enqueue / status / finish."""
    return logging.ERROR if event in _CELERY_ERROR_EVENTS else logging.INFO


def log_classroom_celery(
    event: str,
    *,
    job_id: str,
    celery_task_id: Optional[str] = None,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Job lifecycle line. Failures are ERROR; the rest stay INFO."""
    logger.log(
        celery_log_level(event),
        format_classroom_celery_line(
            event,
            job_id=job_id,
            celery_task_id=celery_task_id,
            status=status,
            stage=stage,
            detail=detail,
        ),
    )
