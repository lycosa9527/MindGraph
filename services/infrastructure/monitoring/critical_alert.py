"""
Record critical failures for the error collector.

Startup, health, and process-monitor failures are logged and persisted here.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from services.monitoring.error_reporting import record_failure
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


class CriticalAlertService:
    """Persist critical failures for the error collector."""

    @staticmethod
    def _record(
        component: str,
        error_type: str,
        error_message: str,
        details: Optional[str],
        persist_error: bool,
    ) -> bool:
        """Log a critical failure and optionally enqueue it for the error collector."""
        logger.critical(
            "[CriticalAlert] Component: %s, Type: %s, Message: %s",
            component,
            error_type,
            error_message,
        )
        if details:
            logger.critical("[CriticalAlert] Error details: %s", details)

        if not persist_error:
            return False

        try:
            record_failure(
                source="application",
                component=component,
                message=error_message,
                severity="critical",
                exception_type=error_type,
                stacktrace=details,
            )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.error("[CriticalAlert] Failed to record failure: %s", exc)
            return False
        return True

    @staticmethod
    async def send_critical_alert(
        component: str,
        error_type: str,
        error_message: str,
        details: Optional[str] = None,
        persist_error: bool = True,
    ) -> bool:
        """
        Record a critical failure.

        Args:
            component: Component name (Redis, Database, LLM, Application, etc.)
            error_type: Error type (StartupFailure, RuntimeError, etc.)
            error_message: Error message
            details: Optional additional details
            persist_error: When False, skip error collection (caller already persisted)

        Returns:
            True when the failure was enqueued for the error collector
        """
        return CriticalAlertService._record(
            component,
            error_type,
            error_message,
            details,
            persist_error,
        )

    @staticmethod
    async def send_startup_failure_alert(component: str, error_message: str, details: Optional[str] = None) -> bool:
        """Record a startup failure."""
        return await CriticalAlertService.send_critical_alert(
            component=component,
            error_type="StartupFailure",
            error_message=error_message,
            details=details,
        )

    @staticmethod
    async def send_runtime_error_alert(
        component: str,
        error_message: str,
        details: Optional[str] = None,
        *,
        persist_error: bool = True,
    ) -> bool:
        """Record a runtime critical error."""
        return await CriticalAlertService.send_critical_alert(
            component=component,
            error_type="RuntimeError",
            error_message=error_message,
            details=details,
            persist_error=persist_error,
        )

    @staticmethod
    def send_startup_failure_alert_sync(component: str, error_message: str, details: Optional[str] = None) -> bool:
        """Record a startup failure from synchronous startup code."""
        return CriticalAlertService._record(
            component,
            "StartupFailure",
            error_message,
            details,
            True,
        )
