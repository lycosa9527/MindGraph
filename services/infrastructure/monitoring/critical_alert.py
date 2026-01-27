"""
Critical Alert Service for MindGraph Application

Centralized service for sending critical SMS alerts to admin phones.
Ensures only ONE alert per critical error scenario (no spam).

Features:
- SMS alerts for critical application errors
- Redis-based deduplication (prevents duplicate alerts)
- Component-based cooldown mechanism
- Comprehensive logging (essential since SMS template is fixed)
- Non-blocking (doesn't crash app if SMS fails)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Optional

try:
    from services.redis.redis_client import get_redis, is_redis_available
    _REDIS_AVAILABLE = True
except ImportError:
    get_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

try:
    from services.auth.sms_middleware import get_sms_middleware
    from utils.auth.config import ADMIN_PHONES
    _SMS_AVAILABLE = True
except ImportError:
    get_sms_middleware = None
    ADMIN_PHONES = []
    _SMS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

CRITICAL_ALERT_ENABLED = os.getenv("CRITICAL_ALERT_ENABLED", "true").lower() in ("true", "1", "yes")
CRITICAL_ALERT_COOLDOWN_SECONDS = int(os.getenv("CRITICAL_ALERT_COOLDOWN_SECONDS", "1800"))  # 30 min default
CRITICAL_ALERT_EXCEPTION_COOLDOWN_SECONDS = int(
    os.getenv("CRITICAL_ALERT_EXCEPTION_COOLDOWN_SECONDS", "3600")
)  # 1 hour for exceptions

# Redis keys for alert tracking
ALERT_SENT_KEY_PREFIX = "critical_alert:sent:"


# ============================================================================
# Critical Alert Service
# ============================================================================

class CriticalAlertService:
    """
    Centralized service for sending critical SMS alerts.

    Ensures only ONE alert per critical error scenario to prevent spam.
    Uses Redis-based deduplication and component-based cooldown.
    """

    @staticmethod
    def _calculate_error_hash(component: str, error_type: str, error_message: str) -> str:
        """
        Calculate hash for error deduplication.

        Args:
            component: Component name (Redis, Database, LLM, etc.)
            error_type: Error type (StartupFailure, RuntimeError, etc.)
            error_message: Error message (first 50 chars used)

        Returns:
            SHA256 hash string
        """
        message_preview = error_message[:50] if error_message else ""
        hash_input = f"{component}:{error_type}:{message_preview}"
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    async def _check_alert_sent(component: str, error_hash: str) -> bool:
        """
        Check if alert was already sent for this error.

        Args:
            component: Component name
            error_hash: Error hash

        Returns:
            True if alert already sent, False otherwise
        """
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            key = f"{ALERT_SENT_KEY_PREFIX}{component}:{error_hash}"
            exists = await asyncio.to_thread(redis_client.exists, key)
            return bool(exists)
        except Exception as e:
            logger.debug("[CriticalAlert] Failed to check alert sent status: %s", e)
            return False

    @staticmethod
    async def _mark_alert_sent(component: str, error_hash: str, cooldown_seconds: int) -> None:
        """
        Mark alert as sent in Redis.

        Args:
            component: Component name
            error_hash: Error hash
            cooldown_seconds: Cooldown period in seconds
        """
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return

        try:
            if get_redis is None:
                return
            redis_client = get_redis()
            if redis_client is None:
                return

            key = f"{ALERT_SENT_KEY_PREFIX}{component}:{error_hash}"
            await asyncio.to_thread(
                redis_client.setex,
                key,
                cooldown_seconds,
                str(time.time())
            )
        except Exception as e:
            logger.warning("[CriticalAlert] Failed to mark alert as sent: %s", e)

    @staticmethod
    async def send_critical_alert(
        component: str,
        error_type: str,
        error_message: str,
        details: Optional[str] = None,
        bypass_cooldown: bool = False,
        cooldown_seconds: Optional[int] = None
    ) -> bool:
        """
        Send critical SMS alert to admin phones.

        Ensures only ONE alert per unique error scenario (prevents spam).

        Args:
            component: Component name (Redis, Database, LLM, Application, etc.)
            error_type: Error type (StartupFailure, RuntimeError, UnhandledException, etc.)
            error_message: Error message
            details: Optional additional details (stack trace, context, etc.)
            bypass_cooldown: If True, bypass cooldown check (for startup failures)
            cooldown_seconds: Custom cooldown period (default: CRITICAL_ALERT_COOLDOWN_SECONDS)

        Returns:
            True if alert was sent, False if skipped (cooldown or already sent)
        """
        # Skip SMS alerts in debug mode (frequent restarts during development)
        is_debug_mode = os.getenv("DEBUG", "").lower() == "true"
        if is_debug_mode:
            logger.debug("[CriticalAlert] Critical alert skipped (DEBUG mode enabled)")
            return False

        if not CRITICAL_ALERT_ENABLED:
            logger.debug("[CriticalAlert] Critical alerting disabled")
            return False

        if not _SMS_AVAILABLE:
            logger.warning("[CriticalAlert] SMS service not available, cannot send alert")
            return False

        error_hash = CriticalAlertService._calculate_error_hash(component, error_type, error_message)

        if not bypass_cooldown:
            if await CriticalAlertService._check_alert_sent(component, error_hash):
                logger.info(
                    "[CriticalAlert] Alert already sent for %s:%s (hash: %s), skipping to prevent spam",
                    component,
                    error_type,
                    error_hash
                )
                return False

        admin_phones = [phone.strip() for phone in ADMIN_PHONES if phone.strip()]
        if not admin_phones:
            logger.warning("[CriticalAlert] No admin phones configured, cannot send alert")
            return False

        logger.critical(
            "[CriticalAlert] CRITICAL ERROR DETECTED - Component: %s, Type: %s, Message: %s, Hash: %s",
            component,
            error_type,
            error_message,
            error_hash
        )
        if details:
            logger.critical("[CriticalAlert] Error details: %s", details)

        try:
            if get_sms_middleware is None:
                logger.warning("[CriticalAlert] SMS middleware function not available")
                return False
            sms_middleware = get_sms_middleware()
            if not sms_middleware.is_available:
                logger.warning("[CriticalAlert] SMS middleware not available")
                return False

            success, message = await sms_middleware.send_alert(admin_phones, lang="zh")
            if success:
                logger.info(
                    "[CriticalAlert] SMS alert sent successfully - Component: %s, Type: %s, Hash: %s",
                    component,
                    error_type,
                    error_hash
                )

                if not bypass_cooldown:
                    cooldown = cooldown_seconds or CRITICAL_ALERT_COOLDOWN_SECONDS
                    await CriticalAlertService._mark_alert_sent(component, error_hash, cooldown)

                return True
            else:
                logger.error("[CriticalAlert] Failed to send SMS alert: %s", message)
                return False
        except Exception as e:
            logger.error("[CriticalAlert] Error sending SMS alert: %s", e, exc_info=True)
            return False

    @staticmethod
    async def send_startup_failure_alert(
        component: str,
        error_message: str,
        details: Optional[str] = None
    ) -> bool:
        """
        Send alert for startup failure (app cannot start).

        No cooldown - app is exiting anyway, only one chance to alert.

        Args:
            component: Component name (Redis, Qdrant, Celery, Database, etc.)
            error_message: Error message
            details: Optional additional details

        Returns:
            True if alert was sent, False otherwise
        """
        return await CriticalAlertService.send_critical_alert(
            component=component,
            error_type="StartupFailure",
            error_message=error_message,
            details=details,
            bypass_cooldown=True
        )

    @staticmethod
    async def send_runtime_error_alert(
        component: str,
        error_message: str,
        details: Optional[str] = None
    ) -> bool:
        """
        Send alert for runtime critical error.

        Uses cooldown to prevent spam.

        Args:
            component: Component name
            error_message: Error message
            details: Optional additional details

        Returns:
            True if alert was sent, False if skipped (cooldown)
        """
        return await CriticalAlertService.send_critical_alert(
            component=component,
            error_type="RuntimeError",
            error_message=error_message,
            details=details,
            bypass_cooldown=False,
            cooldown_seconds=CRITICAL_ALERT_COOLDOWN_SECONDS
        )

    @staticmethod
    async def send_unhandled_exception_alert(
        component: str,
        exception_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        request_path: Optional[str] = None
    ) -> bool:
        """
        Send alert for unhandled exception.

        Uses longer cooldown (1 hour) to prevent spam from repeated crashes.

        Args:
            component: Component name (usually "Application")
            exception_type: Exception class name
            error_message: Exception message
            stack_trace: Optional stack trace
            request_path: Optional request path

        Returns:
            True if alert was sent, False if skipped (cooldown)
        """
        details_parts = []
        if request_path:
            details_parts.append(f"Request Path: {request_path}")
        if stack_trace:
            details_parts.append(f"Stack Trace: {stack_trace[:500]}")  # Limit stack trace length
        details = "\n".join(details_parts) if details_parts else None

        return await CriticalAlertService.send_critical_alert(
            component=component,
            error_type=f"UnhandledException:{exception_type}",
            error_message=error_message,
            details=details,
            bypass_cooldown=False,
            cooldown_seconds=CRITICAL_ALERT_EXCEPTION_COOLDOWN_SECONDS
        )


    @staticmethod
    def send_startup_failure_alert_sync(
        component: str,
        error_message: str,
        details: Optional[str] = None
    ) -> bool:
        """
        Send alert for startup failure (synchronous version for use during startup).

        Creates new event loop if needed. Use this when calling from synchronous code.

        Args:
            component: Component name (Redis, Qdrant, Celery, Database, etc.)
            error_message: Error message
            details: Optional additional details

        Returns:
            True if alert was sent, False otherwise
        """
        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        CriticalAlertService.send_startup_failure_alert(
                            component, error_message, details
                        )
                    )
                    return True
                else:
                    return loop.run_until_complete(
                        CriticalAlertService.send_startup_failure_alert(
                            component, error_message, details
                        )
                    )
            except RuntimeError:
                return asyncio.run(
                    CriticalAlertService.send_startup_failure_alert(
                        component, error_message, details
                    )
                )
        except Exception as e:
            logger.error("[CriticalAlert] Failed to send startup failure alert: %s", e, exc_info=True)
            return False


def get_critical_alert_service() -> type[CriticalAlertService]:
    """Get CriticalAlertService class (static methods, no instance needed)"""
    return CriticalAlertService
