"""Celery tasks for Showcase teaching-design cover generation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

from config.celery import celery_app
from services.monitoring.error_reporting import record_exception_from_celery
from services.redis.redis_async_client import close_async_redis
from services.showcase.covers.events import publish_showcase_cover_event_sync
from services.showcase.covers.generate import generate_showcase_cover
from services.showcase.covers.job_manifest import (
    DEFAULT_MAX_ATTEMPTS,
    cover_reason_is_retryable,
    get_cover_job_snapshot_sync,
    mark_cover_job_failed_sync,
    mark_cover_job_queued_sync,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

# LO convert ≤120s; leave headroom for PNG shrink + COS put + DB.
_SOFT_TIME_LIMIT_SECONDS = 180
_HARD_TIME_LIMIT_SECONDS = 210
# Total tries = DEFAULT_MAX_ATTEMPTS (initial + retries).
_MAX_RETRIES = max(0, DEFAULT_MAX_ATTEMPTS - 1)


def _rls_user_id(user_id: int, author_id: Optional[int]) -> int:
    return int(author_id) if author_id is not None else int(user_id)


async def _run_and_close(coro: Awaitable[object]) -> bool:
    try:
        return bool(await coro)
    finally:
        await close_async_redis()


def _persist_fail(
    *,
    post_id: str,
    user_id: int,
    author_id: Optional[int],
    organization_id: Optional[int],
    reason: str,
    celery_task_id: Optional[str],
) -> None:
    wrote = mark_cover_job_failed_sync(
        post_id=post_id,
        user_id=_rls_user_id(user_id, author_id),
        reason=reason,
        organization_id=organization_id,
        celery_task_id=celery_task_id,
    )
    if wrote:
        publish_showcase_cover_event_sync(post_id, "cover_fail", reason=reason)


def _requeue_for_retry(
    *,
    post_id: str,
    user_id: int,
    author_id: Optional[int],
    organization_id: Optional[int],
    attachment_key: str,
    celery_task_id: Optional[str],
) -> None:
    """Keep manifesto in-flight while Celery backoff runs (not terminal failed)."""
    mark_cover_job_queued_sync(
        post_id=post_id,
        user_id=_rls_user_id(user_id, author_id),
        attachment_key=attachment_key,
        organization_id=organization_id,
        celery_task_id=celery_task_id,
        force=False,
    )


def _should_retry(self, snapshot: Optional[dict], reason: Optional[str]) -> bool:
    if reason is None or not cover_reason_is_retryable(reason):
        return False
    if self.request.retries >= self.max_retries:
        return False
    if snapshot is not None:
        attempts = int(snapshot.get("attempt_count") or 0)
        max_attempts = int(snapshot.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
        if attempts >= max_attempts:
            return False
    return True


@celery_app.task(
    bind=True,
    name="showcase.generate_cover",
    queue="default",
    max_retries=_MAX_RETRIES,
    soft_time_limit=_SOFT_TIME_LIMIT_SECONDS,
    time_limit=_HARD_TIME_LIMIT_SECONDS,
)
def generate_cover_task(
    self,
    post_id: str,
    user_id: int,
    attachment_key: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
) -> bool:
    """Render and persist a teaching-design cover for ``post_id``."""
    task_id = getattr(self.request, "id", None)
    task_id_str = task_id if isinstance(task_id, str) else None
    logger.info(
        "[ShowcaseCoverTask] dispatch post=%s user=%s task=%s retry=%s",
        post_id[:8] if post_id else "",
        user_id,
        task_id_str,
        self.request.retries,
    )
    try:
        ok = asyncio.run(
            _run_and_close(
                generate_showcase_cover(
                    post_id=post_id,
                    user_id=int(user_id),
                    attachment_key=attachment_key,
                    organization_id=organization_id,
                    author_id=int(author_id) if author_id is not None else int(user_id),
                    celery_task_id=task_id_str,
                )
            )
        )
    except SoftTimeLimitExceeded as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s soft time limit: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        _persist_fail(
            post_id=post_id,
            user_id=user_id,
            author_id=author_id,
            organization_id=organization_id,
            reason="soft_time_limit",
            celery_task_id=task_id_str,
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        snapshot = get_cover_job_snapshot_sync(
            post_id=post_id,
            user_id=_rls_user_id(user_id, author_id),
            organization_id=organization_id,
        )
        if _should_retry(self, snapshot, "soft_time_limit"):
            _requeue_for_retry(
                post_id=post_id,
                user_id=user_id,
                author_id=author_id,
                organization_id=organization_id,
                attachment_key=attachment_key,
                celery_task_id=task_id_str,
            )
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc
        return False
    except TimeLimitExceeded as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s hard time limit: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        _persist_fail(
            post_id=post_id,
            user_id=user_id,
            author_id=author_id,
            organization_id=organization_id,
            reason="hard_time_limit",
            celery_task_id=task_id_str,
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        raise
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error(
            "[ShowcaseCoverTask] post=%s failed: %s",
            post_id[:8] if post_id else "",
            exc,
            exc_info=True,
        )
        reason = str(exc)[:200]
        _persist_fail(
            post_id=post_id,
            user_id=user_id,
            author_id=author_id,
            organization_id=organization_id,
            reason=reason,
            celery_task_id=task_id_str,
        )
        record_exception_from_celery(
            source="background",
            component="ShowcaseCoverTask",
            exc=exc,
            tags={"post_id": post_id, "user_id": user_id},
        )
        snapshot = get_cover_job_snapshot_sync(
            post_id=post_id,
            user_id=_rls_user_id(user_id, author_id),
            organization_id=organization_id,
        )
        if _should_retry(self, snapshot, reason):
            _requeue_for_retry(
                post_id=post_id,
                user_id=user_id,
                author_id=author_id,
                organization_id=organization_id,
                attachment_key=attachment_key,
                celery_task_id=task_id_str,
            )
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc
        raise

    if ok:
        return True

    snapshot = get_cover_job_snapshot_sync(
        post_id=post_id,
        user_id=_rls_user_id(user_id, author_id),
        organization_id=organization_id,
    )
    reason = None
    if snapshot is not None:
        err = snapshot.get("error_message")
        reason = err if isinstance(err, str) else None
    # lock_busy leaves no failed manifesto — do not retry spam.
    if not _should_retry(self, snapshot, reason):
        return False
    _requeue_for_retry(
        post_id=post_id,
        user_id=user_id,
        author_id=author_id,
        organization_id=organization_id,
        attachment_key=attachment_key,
        celery_task_id=task_id_str,
    )
    raise self.retry(
        exc=RuntimeError(reason or "cover_retry"),
        countdown=60 * (2**self.request.retries),
    )
