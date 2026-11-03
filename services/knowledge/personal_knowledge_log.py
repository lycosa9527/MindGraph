"""Stage lines for a personal-knowledge Celery run.

The worker writes these to the application log. Each line is one status:
extracting, splitting, the table of contents, the OSS upload, embedding
handoff, completion, or failure.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token

logger = logging.getLogger(__name__)

_TASK_ID: ContextVar[str] = ContextVar("personal_knowledge_celery_task", default="")
_ERROR_STATUSES = frozenset({"failed", "oss_failed", "oss_refused"})


def bind_personal_knowledge_task(task_id: str) -> Token[str]:
    """Remember the Celery task id for logs emitted on this worker run."""
    return _TASK_ID.set(task_id or "")


def reset_personal_knowledge_task(token: Token[str]) -> None:
    """Drop the Celery task id bound for this run."""
    _TASK_ID.reset(token)


def log_personal_knowledge(status: str, **details: object) -> None:
    """Write one personal-knowledge status line for the application log."""
    parts = [f"status={status}"]
    task_id = _TASK_ID.get()
    if task_id:
        parts.append(f"task={task_id}")
    for key, value in details.items():
        if isinstance(value, str) and any(char.isspace() for char in value):
            parts.append(f"{key}={value!r}")
        else:
            parts.append(f"{key}={value}")
    level = logging.ERROR if status in _ERROR_STATUSES else logging.INFO
    logger.log(level, "[PersonalKnowledge] celery %s", " ".join(parts))
