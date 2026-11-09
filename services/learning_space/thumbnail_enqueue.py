"""Queue a Celery thumbnail render when a student submits homework."""

from __future__ import annotations

import logging

from kombu.exceptions import OperationalError as BrokerOperationalError

from config.celery import celery_app
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

SUBMIT_THUMBNAIL_TASK = "learning_space.render_submit_thumbnail"


def enqueue_submit_thumbnail(submission_id: int, token: str) -> bool:
    """Send one thumbnail job. A broker failure leaves the row for the API sweep."""
    if submission_id <= 0 or not token.strip():
        return False
    try:
        async_result = celery_app.send_task(
            SUBMIT_THUMBNAIL_TASK,
            kwargs={"submission_id": int(submission_id), "token": token.strip()},
            queue="default",
        )
    except (*BACKGROUND_INFRA_ERRORS, BrokerOperationalError) as exc:
        logger.warning(
            "[LearningSpace] Submit thumbnail enqueue failed submission=%s: %s",
            submission_id,
            exc,
        )
        return False
    task_id = getattr(async_result, "id", None)
    logger.info(
        "[LearningSpace] Submit thumbnail queued submission=%s task=%s",
        submission_id,
        task_id if isinstance(task_id, str) else "",
    )
    return True
