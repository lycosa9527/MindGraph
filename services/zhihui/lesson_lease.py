"""Celery run lease helpers for ZhiHui diagram lesson decks."""

from __future__ import annotations

import logging
from typing import Any, Optional

from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_STOP_MID_RUN = frozenset({"cancelled", "failed", "partial"})


class LeaseLost(Exception):
    """This Celery run no longer owns the conversation (or must stop)."""


async def require_run_lease(
    conversation_id: str,
    *,
    celery_task_id: Optional[str],
) -> str:
    """
    Return current status while this task still owns the run.

    Raises ``LeaseLost`` when the conversation is gone, cancelled/failed/partial,
    or another Celery task id replaced ``celery_task_id``.
    """
    async with system_rls_session() as db:
        row = await ZhihuiConversationRepository(db).get_by_uuid(conversation_id)
        if row is None:
            raise LeaseLost("conversation missing")
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            raise LeaseLost(f"celery lease lost have={celery_task_id} want={owned}")
        if row.status in _STOP_MID_RUN:
            raise LeaseLost(f"status={row.status}")
        return str(row.status)


async def set_status_with_lease(
    conversation_id: str,
    *,
    status: str,
    progress: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
    style_seed: Optional[str] = None,
    lesson_plan_json: Optional[dict[str, Any]] = None,
    clear_error: bool = False,
    celery_task_id: Optional[str] = None,
) -> None:
    """Update conversation status when this task still holds the Celery lease."""
    async with system_rls_session() as db:
        repo = ZhihuiConversationRepository(db)
        row = await repo.get_by_uuid(conversation_id)
        if row is None:
            raise LeaseLost("conversation missing")
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            raise LeaseLost(f"celery lease lost have={celery_task_id} want={owned}")
        await repo.update_conversation(
            conversation_id,
            status=status,
            progress=progress,
            error_message=error_message,
            style_seed=style_seed,
            lesson_plan_json=lesson_plan_json,
            clear_error=clear_error,
            commit=True,
        )


async def mark_terminal_from_error(
    conversation_id: str,
    exc: BaseException,
    *,
    celery_task_id: Optional[str] = None,
) -> Optional[str]:
    """Set failed/partial from a pipeline exception when this task still owns the lease."""
    async with system_rls_session() as db:
        conv_repo = ZhihuiConversationRepository(db)
        row = await conv_repo.get_by_uuid(conversation_id)
        if row is None:
            return None
        owned = row.celery_task_id
        if celery_task_id and owned and owned != celery_task_id:
            logger.info(
                "[ZhiHui] Skip terminal mark conversation=%s lease lost have=%s want=%s",
                conversation_id,
                celery_task_id,
                owned,
            )
            return None
        gen_repo = ZhihuiGenerationRepository(db)
        existing = await gen_repo.list_by_conversation(conversation_id)
        status = "partial" if existing else "failed"
        await conv_repo.update_conversation(
            conversation_id,
            status=status,
            error_message=str(exc)[:2000],
            progress={"phase": status, "slide_count": len(existing)},
            commit=True,
        )
        return status
