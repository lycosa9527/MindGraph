"""Celery tasks for MindMate export jobs."""

from __future__ import annotations

import asyncio
import logging

from config.celery import celery_app
from services.dify.export.job_runner import run_export_job
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="mindmate_export.run_job", queue="default")
def run_mindmate_export_job(self, job_id: int, user_id: int) -> None:
    """Run a MindMate export job asynchronously."""
    logger.info(
        "[MindMateExportTask] dispatch job=%s user=%s task=%s",
        job_id,
        user_id,
        self.request.id,
    )
    try:
        asyncio.run(run_export_job(int(job_id), int(user_id)))
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error(
            "[MindMateExportTask] job=%s failed: %s",
            job_id,
            exc,
            exc_info=True,
        )
        raise
