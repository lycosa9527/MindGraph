"""One API-side renderer for submitted homework thumbnails.

The submission row is the queue. ``thumb_pending`` stays set until the PNG is
stored, so a restarted worker draws the same homework again. A Redis lock keeps
the four API workers from launching Chromium at once, and a row lease keeps a
second pass off the card this process is already drawing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm.attributes import flag_modified

from models.domain.learning_space import LearningSubmission
from services.learning_space.thumbnail_backfill import install_submit_thumbnail
from services.learning_space.thumbnail_backfill_scan import SUBMIT_THUMBNAIL_DUE_SQL
from services.learning_space.thumbnail_submit import (
    THUMB_PENDING,
    THUMB_TOKEN,
    SubmitThumbnailJob,
    hold_thumbnail_claim,
    run_submit_thumbnail_job,
    thumbnail_clock,
)
from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_IDLE_SECONDS = 3.0
_LOCK_KEY = redis_keys.LOCK.format(resource="learning-space:submit-thumbnail")
_LOCK_TTL_SECONDS = 180
_WORKER_ERRORS = DATABASE_ERRORS + BACKGROUND_INFRA_ERRORS + (LookupError,)


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _claim_token(snapshot: dict[str, object]) -> str:
    pending = _text(snapshot.get(THUMB_PENDING))
    token = _text(snapshot.get(THUMB_TOKEN))
    return pending or token or uuid4().hex


async def claim_next_submit_thumbnail(now: datetime | None = None) -> SubmitThumbnailJob | None:
    """Lock the oldest due diagram, lease it, and return the spec to draw."""
    now_iso = thumbnail_clock(now)
    clock = now if now is not None else datetime.now(UTC)
    async with system_rls_session() as db:
        statement = (
            select(LearningSubmission)
            .where(text(SUBMIT_THUMBNAIL_DUE_SQL))
            .order_by(LearningSubmission.submitted_at.asc().nullsfirst(), LearningSubmission.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
            .params(now_iso=now_iso)
        )
        row = (await db.execute(statement)).scalar_one_or_none()
        if row is None or row.id is None or not isinstance(row.snapshot_spec, dict):
            return None
        snap = dict(row.snapshot_spec)
        token = _claim_token(snap)
        if not hold_thumbnail_claim(snap, token, clock, _LOCK_TTL_SECONDS):
            return None
        row.snapshot_spec = snap
        flag_modified(row, "snapshot_spec")
        try:
            await db.commit()
        except DATABASE_ERRORS:
            await db.rollback()
            raise
        spec = snap.get("spec")
        if not isinstance(spec, dict):
            return None
        return SubmitThumbnailJob(
            submission_id=int(row.id),
            owner_id=int(row.student_user_id),
            token=token,
            spec=dict(spec),
            diagram_type=snap.get("diagram_type"),
            fallback_thumb=None,
            previous_ref=snap.get("thumbnail"),
        )


async def render_one_due_submit_thumbnail(now: datetime | None = None) -> bool:
    """Draw one due submission. False when nothing was stored."""
    try:
        job = await claim_next_submit_thumbnail(now)
    except DATABASE_ERRORS as exc:
        logger.warning("[LearningSpace] Submit thumbnail claim failed: %s", exc)
        return False
    if job is None:
        return False
    return await run_submit_thumbnail_job(job)


class _LockNotice:
    """Warn once per Redis outage, then again after a lock is acquired."""

    def __init__(self) -> None:
        self.pending = True

    def warn(self, message: str) -> None:
        """Log the first failure of this outage."""
        if not self.pending:
            return
        self.pending = False
        logger.warning("[LearningSpace] %s", message)

    def recovered(self) -> None:
        """Allow the next outage to log again."""
        self.pending = True


_lock_notice = _LockNotice()


async def _acquire_render_lock() -> str | None:
    """One cluster-wide renderer. No lock means this process waits."""
    if not is_redis_available():
        _lock_notice.warn("Submit thumbnail waiting for Redis")
        return None
    lock_id = f"{os.getpid()}:{uuid4().hex[:8]}"
    try:
        acquired = await get_async_redis().set(_LOCK_KEY, lock_id, nx=True, ex=_LOCK_TTL_SECONDS)
    except REDIS_ERRORS as exc:
        _lock_notice.warn(f"Submit thumbnail lock failed: {exc}")
        return None
    if acquired:
        _lock_notice.recovered()
        return lock_id
    return None


async def _release_render_lock(lock_id: str) -> None:
    if not is_redis_available():
        return
    try:
        await AsyncRedisOps.compare_and_delete(_LOCK_KEY, lock_id)
    except REDIS_ERRORS as exc:
        logger.warning("[LearningSpace] Submit thumbnail lock release failed: %s", exc)


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        return


async def run_submit_thumbnail_worker(stop: asyncio.Event) -> None:
    """Render due homework thumbnails until shutdown. One card at a time per cluster."""
    install_submit_thumbnail()
    while not stop.is_set():
        lock_id = await _acquire_render_lock()
        if lock_id is None:
            await _wait(stop, _IDLE_SECONDS)
            continue
        worked = False
        try:
            worked = await render_one_due_submit_thumbnail()
        except _WORKER_ERRORS as exc:
            logger.warning("[LearningSpace] Submit thumbnail worker failed: %s", exc)
        finally:
            await _release_render_lock(lock_id)
        if not worked:
            await _wait(stop, _IDLE_SECONDS)


def start_submit_thumbnail_worker() -> tuple[asyncio.Task[None], asyncio.Event]:
    """Start the homework thumbnail renderer on this API worker."""
    stop = asyncio.Event()
    task = asyncio.create_task(run_submit_thumbnail_worker(stop), name="submit_thumbnail_worker")
    return task, stop
