"""Celery runner for ZhiHui diagram-lesson decks."""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

from config.celery import celery_app
from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from services.infrastructure.http.error_handler import LLMServiceError
from services.monitoring.error_reporting import record_exception_from_celery
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from services.zhihui.lesson_deck import run_diagram_lesson_deck
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

# Multi-batch Wan polls can approach ~7 minutes each; budget for several batches.
_SOFT_TIME_LIMIT_SECONDS = 2400
_HARD_TIME_LIMIT_SECONDS = 2460
_TASK_ERRORS = (
    BACKGROUND_INFRA_ERRORS
    + DATABASE_ERRORS
    + (
        LLMServiceError,
        SoftTimeLimitExceeded,
        TimeLimitExceeded,
    )
)


@celery_app.task(
    bind=True,
    name="zhihui.run_diagram_lesson",
    queue="default",
    max_retries=0,
    soft_time_limit=_SOFT_TIME_LIMIT_SECONDS,
    time_limit=_HARD_TIME_LIMIT_SECONDS,
)
def run_diagram_lesson_task(self, conversation_id: str) -> bool:
    """Thin Celery wrapper around ``run_diagram_lesson_deck``."""
    task_id = getattr(self.request, "id", None)
    task_id_str = task_id if isinstance(task_id, str) else None
    logger.info(
        "[ZhiHuiLessonTask] start conversation=%s task=%s",
        conversation_id,
        task_id_str,
    )
    try:
        return bool(
            asyncio.run(
                run_diagram_lesson_deck(
                    conversation_id,
                    celery_task_id=task_id_str,
                )
            )
        )
    except SoftTimeLimitExceeded as exc:
        logger.error(
            "[ZhiHuiLessonTask] soft time limit conversation=%s",
            conversation_id,
            exc_info=True,
        )
        record_exception_from_celery(
            source="background",
            component="ZhiHuiLessonTask",
            exc=exc,
            tags={"conversation_id": conversation_id},
        )
        asyncio.run(_mark_terminal(conversation_id, "soft_time_limit"))
        return False
    except TimeLimitExceeded as exc:
        logger.error(
            "[ZhiHuiLessonTask] hard time limit conversation=%s",
            conversation_id,
            exc_info=True,
        )
        record_exception_from_celery(
            source="background",
            component="ZhiHuiLessonTask",
            exc=exc,
            tags={"conversation_id": conversation_id},
        )
        try:
            asyncio.run(_mark_terminal(conversation_id, "hard_time_limit"))
        except _TASK_ERRORS:
            pass
        raise
    except _TASK_ERRORS as exc:
        record_exception_from_celery(
            source="background",
            component="ZhiHuiLessonTask",
            exc=exc,
            tags={"conversation_id": conversation_id},
        )
        logger.exception(
            "[ZhiHuiLessonTask] failed conversation=%s err=%s",
            conversation_id,
            exc,
        )
        try:
            asyncio.run(_mark_terminal(conversation_id, str(exc)))
        except _TASK_ERRORS:
            pass
        return False


async def _mark_terminal(conversation_id: str, message: str) -> None:
    async with system_rls_session() as db:
        gens = await ZhihuiGenerationRepository(db).list_by_conversation(conversation_id)
        status = "partial" if gens else "failed"
        await ZhihuiConversationRepository(db).update_conversation(
            conversation_id,
            status=status,
            error_message=message[:2000],
            progress={"phase": status, "slide_count": len(gens)},
            commit=True,
        )
