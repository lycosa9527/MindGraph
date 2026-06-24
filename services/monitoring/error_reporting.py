"""
Shared helpers for structured error collection across subsystems.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from services.monitoring.error_collector import ErrorCollectorService, record_error_async
from services.monitoring.error_alert_config import error_collection_enabled
from services.monitoring.error_record import ErrorRecord

VALID_ERROR_SOURCES = frozenset(
    {
        "application",
        "llm",
        "frontend",
        "background",
        "mindbot",
        "rag",
        "collab",
        "auth",
    }
)

_VALID_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})


def _build_record(
    *,
    source: str,
    component: str,
    message: str,
    severity: str = "error",
    exception_type: str = "Error",
    stacktrace: str | None = None,
    tags: dict[str, Any] | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
) -> ErrorRecord:
    normalized_severity = severity.lower()
    if normalized_severity not in _VALID_SEVERITIES:
        normalized_severity = "error"
    return ErrorRecord(
        source=source,
        component=component,
        message=message,
        severity=normalized_severity,
        exception_type=exception_type or "Error",
        stacktrace=stacktrace,
        tags=tags,
        request_id=request_id,
        user_id=user_id,
        http_path=http_path,
        http_status=http_status,
    )


def record_failure(
    source: str,
    component: str,
    message: str,
    *,
    exception_type: str = "Error",
    severity: str = "error",
    stacktrace: str | None = None,
    tags: dict[str, Any] | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
) -> None:
    """Enqueue a non-exception failure for async persistence."""
    if not error_collection_enabled():
        return
    record = _build_record(
        source=source,
        component=component,
        message=message,
        severity=severity,
        exception_type=exception_type,
        stacktrace=stacktrace,
        tags=tags,
        request_id=request_id,
        user_id=user_id,
        http_path=http_path,
        http_status=http_status,
    )
    ErrorCollectorService.record(record)


def record_exception(
    source: str,
    component: str,
    exc: BaseException,
    *,
    severity: str = "error",
    tags: dict[str, Any] | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
    message: str | None = None,
) -> None:
    """Enqueue an exception for async persistence."""
    if not error_collection_enabled():
        return
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    record = _build_record(
        source=source,
        component=component,
        message=message if message is not None else str(exc),
        severity=severity,
        exception_type=type(exc).__name__,
        stacktrace=stack,
        tags=tags,
        request_id=request_id,
        user_id=user_id,
        http_path=http_path,
        http_status=http_status,
    )
    ErrorCollectorService.record(record)


async def record_exception_async(
    source: str,
    component: str,
    exc: BaseException,
    *,
    severity: str = "error",
    tags: dict[str, Any] | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
    message: str | None = None,
) -> int | None:
    """Persist an exception and return the new event id."""
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    record = _build_record(
        source=source,
        component=component,
        message=message if message is not None else str(exc),
        severity=severity,
        exception_type=type(exc).__name__,
        stacktrace=stack,
        tags=tags,
        request_id=request_id,
        user_id=user_id,
        http_path=http_path,
        http_status=http_status,
    )
    return await ErrorCollectorService.record_async(record)


async def record_failure_async(
    source: str,
    component: str,
    message: str,
    *,
    exception_type: str = "Error",
    severity: str = "error",
    stacktrace: str | None = None,
    tags: dict[str, Any] | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
) -> int | None:
    """Persist a non-exception failure and return the new event id."""
    record = _build_record(
        source=source,
        component=component,
        message=message,
        severity=severity,
        exception_type=exception_type,
        stacktrace=stacktrace,
        tags=tags,
        request_id=request_id,
        user_id=user_id,
        http_path=http_path,
        http_status=http_status,
    )
    return await ErrorCollectorService.record_async(record)


def record_exception_from_celery(
    source: str,
    component: str,
    exc: BaseException,
    *,
    severity: str = "error",
    tags: dict[str, Any] | None = None,
    user_id: int | None = None,
    message: str | None = None,
) -> int | None:
    """Persist an exception from a sync Celery task body via asyncio.run."""
    if not error_collection_enabled():
        return None
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    record = _build_record(
        source=source,
        component=component,
        message=message if message is not None else str(exc),
        severity=severity,
        exception_type=type(exc).__name__,
        stacktrace=stack,
        tags=tags,
        user_id=user_id,
    )
    return asyncio.run(record_error_async(record))
