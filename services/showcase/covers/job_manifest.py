"""Cold Postgres manifesto for Showcase teaching-design cover/PDF jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.domain.showcase import ShowcaseCoverJob, ShowcasePost
from services.utils.error_types import DATABASE_ERRORS
from utils.db.rls_context import RlsContext, rls_sync_session

logger = logging.getLogger(__name__)

COVER_JOB_QUEUED = "queued"
COVER_JOB_RUNNING = "running"
COVER_JOB_SUCCEEDED = "succeeded"
COVER_JOB_FAILED = "failed"

COVER_JOB_STATUSES = frozenset(
    {
        COVER_JOB_QUEUED,
        COVER_JOB_RUNNING,
        COVER_JOB_SUCCEEDED,
        COVER_JOB_FAILED,
    }
)

STAGE_DOWNLOAD = "download"
STAGE_CONVERT = "convert"
STAGE_UPLOAD = "upload"
STAGE_PERSIST = "persist"

DEFAULT_MAX_ATTEMPTS = 3
_ATTEMPTS_CAP = 20
# Celery hard limit 210s + slack. Older queued/running rows are reclaimable.
IN_FLIGHT_STALE_SECONDS = 270

# Soft-fail reasons that must not Celery-retry.
NON_RETRYABLE_COVER_REASONS = frozenset(
    {
        "key_out_of_scope",
        "post_missing",
        "not_teaching_design",
        "stale_attachment_key",
        "post_gone_before_write",
        "stale_attachment_before_write",
    }
)


def cover_reason_is_retryable(reason: Optional[str]) -> bool:
    """True when Celery should retry after a cover soft-fail."""
    if not reason:
        return True
    if reason.startswith("unsupported_suffix="):
        return False
    if reason.startswith("enqueue_failed:"):
        return False
    return reason not in NON_RETRYABLE_COVER_REASONS


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def job_is_in_flight(
    status: Optional[str],
    updated_at: Optional[datetime] = None,
) -> bool:
    """True when a cover job is actively queued/running (not stale)."""
    if status not in {COVER_JOB_QUEUED, COVER_JOB_RUNNING}:
        return False
    if updated_at is None:
        return True
    age = (_now() - _as_utc(updated_at)).total_seconds()
    return age < IN_FLIGHT_STALE_SECONDS


def job_is_succeeded(status: Optional[str]) -> bool:
    """True when cover job is cold-complete."""
    return status == COVER_JOB_SUCCEEDED


def cover_job_public_payload(job: Optional[ShowcaseCoverJob]) -> Optional[dict[str, Any]]:
    """Compact cover_job dict for admin API tooltips."""
    if job is None:
        return None
    return {
        "status": job.status,
        "attempt_count": int(job.attempt_count or 0),
        "error_message": job.error_message,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "current_stage": job.current_stage,
    }


def _now() -> datetime:
    return datetime.now(UTC)


def _trim_attempts(attempts: Any) -> list[dict[str, Any]]:
    if not isinstance(attempts, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in attempts:
        if isinstance(item, dict):
            cleaned.append(item)
    if len(cleaned) > _ATTEMPTS_CAP:
        return cleaned[-_ATTEMPTS_CAP:]
    return cleaned


def _append_attempt_entry(
    job: ShowcaseCoverJob,
    *,
    status: str,
    error: Optional[str] = None,
    celery_task_id: Optional[str] = None,
) -> None:
    history = _trim_attempts(job.attempts)
    history.append(
        {
            "at": _now().isoformat(),
            "status": status,
            "error": (error[:200] if isinstance(error, str) and error else None),
            "celery_task_id": celery_task_id or job.celery_task_id,
        }
    )
    job.attempts = _trim_attempts(history)
    flag_modified(job, "attempts")


async def fetch_cover_jobs_by_post_ids(
    db: AsyncSession,
    post_ids: list[str],
) -> dict[str, ShowcaseCoverJob]:
    """Batch-load cover jobs for a page of posts (no COS I/O)."""
    if not post_ids:
        return {}
    rows = (await db.execute(select(ShowcaseCoverJob).where(ShowcaseCoverJob.post_id.in_(post_ids)))).scalars().all()
    return {row.post_id: row for row in rows}


async def get_cover_job(db: AsyncSession, post_id: str) -> Optional[ShowcaseCoverJob]:
    """Load one cover job by post id."""
    return (await db.execute(select(ShowcaseCoverJob).where(ShowcaseCoverJob.post_id == post_id))).scalar_one_or_none()


def get_cover_job_snapshot_sync(
    *,
    post_id: str,
    user_id: int,
    organization_id: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Sync load of job fields for Celery helpers (detached-safe)."""
    with rls_sync_session(RlsContext.for_celery_user(user_id, organization_id)) as db:
        job = db.execute(select(ShowcaseCoverJob).where(ShowcaseCoverJob.post_id == post_id)).scalar_one_or_none()
        if job is None:
            return None
        return {
            "post_id": job.post_id,
            "status": job.status,
            "attempt_count": int(job.attempt_count or 0),
            "max_attempts": int(job.max_attempts or DEFAULT_MAX_ATTEMPTS),
            "attachment_key": job.attachment_key,
            "error_message": job.error_message,
            "celery_task_id": job.celery_task_id,
            "updated_at": job.updated_at,
        }


async def mark_cover_job_running(
    db: AsyncSession,
    *,
    post_id: str,
    attachment_key: Optional[str] = None,
    celery_task_id: Optional[str] = None,
    stage: str = STAGE_DOWNLOAD,
) -> Optional[ShowcaseCoverJob]:
    """Mark job running and bump attempt_count for this Celery try."""
    job = await get_cover_job(db, post_id)
    if job is None:
        job = ShowcaseCoverJob(post_id=post_id, attempts=[], max_attempts=DEFAULT_MAX_ATTEMPTS)
        db.add(job)
    job.status = COVER_JOB_RUNNING
    job.current_stage = stage
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.error_message = None
    job.started_at = _now()
    job.finished_at = None
    job.updated_at = _now()
    if attachment_key:
        job.attachment_key = attachment_key
    if celery_task_id:
        job.celery_task_id = celery_task_id
    _append_attempt_entry(job, status=COVER_JOB_RUNNING, celery_task_id=celery_task_id)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_cover_job_stage(
    db: AsyncSession,
    *,
    post_id: str,
    stage: str,
) -> None:
    """Update current_stage without changing status."""
    job = await get_cover_job(db, post_id)
    if job is None:
        return
    job.current_stage = stage
    job.updated_at = _now()
    await db.commit()


async def bind_cover_job_succeeded(
    db: AsyncSession,
    *,
    post_id: str,
) -> ShowcaseCoverJob:
    """Mutate job to succeeded in the open session (caller commits with post paths)."""
    job = await get_cover_job(db, post_id)
    if job is None:
        job = ShowcaseCoverJob(post_id=post_id, attempts=[], max_attempts=DEFAULT_MAX_ATTEMPTS)
        db.add(job)
    job.status = COVER_JOB_SUCCEEDED
    job.current_stage = STAGE_PERSIST
    job.error_message = None
    job.finished_at = _now()
    job.updated_at = _now()
    _append_attempt_entry(job, status=COVER_JOB_SUCCEEDED)
    return job


async def mark_cover_job_failed(
    db: AsyncSession,
    *,
    post_id: str,
    reason: str,
    celery_task_id: Optional[str] = None,
) -> Optional[ShowcaseCoverJob]:
    """Persist terminal or intermediate failure on the cold manifesto."""
    job = await get_cover_job(db, post_id)
    if job is None:
        job = ShowcaseCoverJob(post_id=post_id, attempts=[], max_attempts=DEFAULT_MAX_ATTEMPTS)
        db.add(job)
    trimmed = reason[:200] if reason else "unknown"
    job.status = COVER_JOB_FAILED
    job.error_message = trimmed
    job.finished_at = _now()
    job.updated_at = _now()
    if celery_task_id:
        job.celery_task_id = celery_task_id
    _append_attempt_entry(
        job,
        status=COVER_JOB_FAILED,
        error=trimmed,
        celery_task_id=celery_task_id,
    )
    await db.commit()
    await db.refresh(job)
    return job


def mark_cover_job_failed_sync(
    *,
    post_id: str,
    user_id: int,
    reason: str,
    organization_id: Optional[int] = None,
    celery_task_id: Optional[str] = None,
) -> None:
    """Sync fail update for Celery time-limit / retry paths."""
    try:
        with rls_sync_session(RlsContext.for_celery_user(user_id, organization_id)) as db:
            job = db.execute(select(ShowcaseCoverJob).where(ShowcaseCoverJob.post_id == post_id)).scalar_one_or_none()
            if job is None:
                job = ShowcaseCoverJob(
                    post_id=post_id,
                    attempts=[],
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                )
                db.add(job)
            trimmed = reason[:200] if reason else "unknown"
            job.status = COVER_JOB_FAILED
            job.error_message = trimmed
            job.finished_at = _now()
            job.updated_at = _now()
            if celery_task_id:
                job.celery_task_id = celery_task_id
            _append_attempt_entry(
                job,
                status=COVER_JOB_FAILED,
                error=trimmed,
                celery_task_id=celery_task_id,
            )
            db.commit()
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[ShowcaseCoverJob] sync fail mark post=%s: %s",
            post_id[:8],
            exc,
        )


def mark_cover_job_queued_sync(
    *,
    post_id: str,
    user_id: int,
    attachment_key: str,
    organization_id: Optional[int] = None,
    celery_task_id: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Sync queued upsert. Returns False when skipped (cold succeeded)."""
    try:
        with rls_sync_session(RlsContext.for_celery_user(user_id, organization_id)) as db:
            job = db.execute(select(ShowcaseCoverJob).where(ShowcaseCoverJob.post_id == post_id)).scalar_one_or_none()
            if job is not None and not force and job_is_succeeded(job.status) and job.attachment_key == attachment_key:
                return False
            if job is None:
                job = ShowcaseCoverJob(
                    post_id=post_id,
                    attempts=[],
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                    attempt_count=0,
                )
                db.add(job)
            job.status = COVER_JOB_QUEUED
            job.current_stage = None
            job.attachment_key = attachment_key
            job.error_message = None
            job.finished_at = None
            job.updated_at = _now()
            if force:
                job.attempt_count = 0
            if celery_task_id:
                job.celery_task_id = celery_task_id
            _append_attempt_entry(job, status=COVER_JOB_QUEUED, celery_task_id=celery_task_id)
            db.commit()
            return True
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[ShowcaseCoverJob] sync queue mark post=%s: %s",
            post_id[:8],
            exc,
        )
        return True


async def cover_job_blocks_auto_enqueue(
    db: AsyncSession,
    *,
    post_id: str,
    attachment_key: str,
) -> bool:
    """True when automatic backfill must not re-queue a cold-succeeded job."""
    job = await get_cover_job(db, post_id)
    if job is None:
        return False
    return job_is_succeeded(job.status) and job.attachment_key == attachment_key


def cover_job_blocks_auto_enqueue_sync(
    *,
    post_id: str,
    attachment_key: str,
    user_id: int,
    organization_id: Optional[int] = None,
) -> bool:
    """Sync variant for enqueue helpers without an open AsyncSession."""
    snapshot = get_cover_job_snapshot_sync(
        post_id=post_id,
        user_id=user_id,
        organization_id=organization_id,
    )
    if snapshot is None:
        return False
    return job_is_succeeded(snapshot.get("status")) and snapshot.get("attachment_key") == attachment_key


async def load_post_attachment_key(db: AsyncSession, post_id: str) -> Optional[str]:
    """Return teaching-design attachment_path from post spec."""
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if post is None or post.case_type != "teaching_design":
        return None
    if not isinstance(post.spec, dict):
        return None
    value = post.spec.get("attachment_path")
    return value if isinstance(value, str) and value.strip() else None
