"""Celery task that draws a thumbnail after a student submits homework."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

from config.celery import celery_app
from services.learning_space.thumbnail_backfill import install_submit_thumbnail
from services.learning_space.thumbnail_submit import (
    claim_submit_thumbnail,
    record_submit_thumbnail_retry,
    run_submit_thumbnail_job,
)
from services.redis.redis_async_client import close_async_redis
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)

_SOFT_TIME_LIMIT_SECONDS = 90
_HARD_TIME_LIMIT_SECONDS = 120


async def _run_and_close(coro: Awaitable[bool]) -> bool:
    try:
        return bool(await coro)
    finally:
        await close_async_redis()


async def _render_submission(submission_id: int, token: str) -> bool:
    install_submit_thumbnail()
    job = await claim_submit_thumbnail(submission_id, token)
    if job is None:
        logger.info(
            "[LearningSpace] Submit thumbnail skipped submission=%s",
            submission_id,
        )
        return True
    return await run_submit_thumbnail_job(job)


@celery_app.task(
    bind=True,
    name="learning_space.render_submit_thumbnail",
    queue="default",
    max_retries=0,
    soft_time_limit=_SOFT_TIME_LIMIT_SECONDS,
    time_limit=_HARD_TIME_LIMIT_SECONDS,
)
def render_submit_thumbnail_task(self, submission_id: int, token: str) -> bool:
    """Draw the PNG for this submit. The API sweep retries when this does not finish."""
    task_id = getattr(self.request, "id", None)
    logger.info(
        "[LearningSpace] Submit thumbnail start submission=%s task=%s",
        submission_id,
        task_id if isinstance(task_id, str) else "",
    )
    try:
        return asyncio.run(_run_and_close(_render_submission(int(submission_id), token)))
    except SoftTimeLimitExceeded:
        logger.warning("[LearningSpace] Submit thumbnail timed out submission=%s", submission_id)
        try:
            asyncio.run(_run_and_close(record_submit_thumbnail_retry(int(submission_id), token)))
        except DATABASE_ERRORS as exc:
            logger.warning(
                "[LearningSpace] Submit thumbnail retry save failed submission=%s: %s",
                submission_id,
                exc,
            )
        return False
    except TimeLimitExceeded:
        logger.error("[LearningSpace] Submit thumbnail hard timeout submission=%s", submission_id)
        raise
