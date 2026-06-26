"""
Central error collection service — persists structured errors to PostgreSQL.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from config.db_sessions import open_async_session
from models.domain.error_event import ErrorEvent, ErrorGroup
from services.monitoring.alert_dispatcher import AlertDispatcher
from services.monitoring.error_alert_config import error_collection_enabled
from services.monitoring.error_record import ErrorRecord
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_bg_tasks: set[asyncio.Task] = set()

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*\S+"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
)

_MAX_MESSAGE_LEN = 4000
_MAX_STACK_LEN = 16000


def _fire_and_forget(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)

    def _on_done(done_task: asyncio.Task) -> None:
        _bg_tasks.discard(done_task)
        if not done_task.cancelled() and done_task.exception() is not None:
            logger.debug("[ErrorCollector] background task failed: %s", done_task.exception())

    task.add_done_callback(_on_done)


def redact_sensitive_text(text: str) -> str:
    """Strip likely secrets and PII from error text."""
    if not text:
        return ""
    redacted = text
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    if len(redacted) > _MAX_STACK_LEN:
        return redacted[:_MAX_STACK_LEN] + "\n... [truncated]"
    return redacted


def compute_fingerprint(
    *,
    exception_type: str,
    component: str,
    message: str,
    stacktrace: str | None = None,
) -> str:
    """Stable fingerprint for grouping similar errors."""
    stack_hint = ""
    if stacktrace:
        lines = [line.strip() for line in stacktrace.splitlines() if line.strip()]
        frame_lines = [line for line in lines if line.startswith("File ")]
        stack_hint = "|".join(frame_lines[-3:])
    message_hint = message[:120] if message else ""
    raw = f"{exception_type}|{component}|{message_hint}|{stack_hint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _normalize_record(record: ErrorRecord) -> ErrorRecord:
    message = redact_sensitive_text(record.message)[:_MAX_MESSAGE_LEN]
    stack = redact_sensitive_text(record.stacktrace) if record.stacktrace else None
    fingerprint = record.fingerprint or compute_fingerprint(
        exception_type=record.exception_type,
        component=record.component,
        message=message,
        stacktrace=stack,
    )
    severity = record.severity.lower()
    if severity not in ("debug", "info", "warning", "error", "critical"):
        severity = "error"
    return ErrorRecord(
        source=record.source,
        component=record.component[:128],
        message=message,
        severity=severity,
        exception_type=(record.exception_type or "Error")[:256],
        stacktrace=stack,
        tags=record.tags,
        request_id=record.request_id,
        user_id=record.user_id,
        http_path=record.http_path[:512] if record.http_path else None,
        http_status=record.http_status,
        fingerprint=fingerprint,
    )


async def _persist_record(record: ErrorRecord) -> int | None:
    now = datetime.now(UTC)
    async with open_async_session() as session:
        group_result = await session.execute(select(ErrorGroup).where(ErrorGroup.fingerprint == record.fingerprint))
        group = group_result.scalar_one_or_none()
        if group is None:
            group = ErrorGroup(
                fingerprint=record.fingerprint or "",
                severity=record.severity,
                source=record.source,
                component=record.component,
                exception_type=record.exception_type,
                sample_message=record.message,
                occurrence_count=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(group)
            await session.flush()
        else:
            new_count = group.occurrence_count + 1
            new_severity = record.severity
            if _severity_rank(record.severity) > _severity_rank(group.severity):
                group.severity = new_severity
            await session.execute(
                update(ErrorGroup)
                .where(ErrorGroup.id == group.id)
                .values(
                    occurrence_count=new_count,
                    last_seen_at=now,
                    sample_message=record.message,
                    component=record.component,
                    exception_type=record.exception_type,
                )
            )
            await session.refresh(group)

        event = ErrorEvent(
            group_id=group.id,
            fingerprint=record.fingerprint or "",
            severity=record.severity,
            source=record.source,
            component=record.component,
            exception_type=record.exception_type,
            message=record.message,
            stacktrace=record.stacktrace,
            tags=record.tags,
            request_id=record.request_id,
            user_id=record.user_id,
            http_path=record.http_path,
            http_status=record.http_status,
            created_at=now,
        )
        session.add(event)
        await session.commit()
        return event.id


def _severity_rank(severity: str) -> int:
    ranks = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
    return ranks.get(severity.lower(), 3)


async def record_error_async(record: ErrorRecord) -> int | None:
    """Persist one error event and update its group aggregate."""
    if not error_collection_enabled():
        return None
    normalized = _normalize_record(record)
    try:
        event_id = await _persist_record(normalized)
    except SQLAlchemyError as db_error:
        logger.warning("[ErrorCollector] Failed to persist error: %s", db_error)
        return None
    except BACKGROUND_INFRA_ERRORS as infra_error:
        logger.warning("[ErrorCollector] Infra error while persisting: %s", infra_error)
        return None

    if event_id is not None:
        _fire_and_forget(AlertDispatcher.evaluate_after_record(normalized, event_id))
    return event_id


def record_error(record: ErrorRecord) -> None:
    """Schedule async persistence (safe from sync or async callers)."""
    if not error_collection_enabled():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("[ErrorCollector] No running loop; skipping error record")
        return
    if loop.is_running():
        _fire_and_forget(record_error_async(record))


class ErrorCollectorService:
    """Facade for error collection hooks."""

    @staticmethod
    def enabled() -> bool:
        """Return whether error collection is active."""
        return error_collection_enabled()

    @staticmethod
    def record(record: ErrorRecord) -> None:
        """Enqueue an error for async persistence."""
        record_error(record)

    @staticmethod
    async def record_async(record: ErrorRecord) -> int | None:
        """Persist an error and return the new event id."""
        return await record_error_async(record)
