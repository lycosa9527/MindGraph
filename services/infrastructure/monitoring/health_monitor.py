"""
Health Monitor Service for MindGraph Application

Monitors overall server health by periodically calling /health/all endpoint
and sends SMS alerts to admin phones when failures are detected.

Features:
- Periodic health monitoring via HTTP endpoint (configurable interval)
- SMS alerts for unhealthy/degraded status
- Cooldown mechanism (prevents alert spam)
- Multi-worker coordination via Redis distributed lock
- Tracks consecutive failures before alerting

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

import httpx

try:
    from services.redis.redis_client import get_redis, is_redis_available
    _REDIS_AVAILABLE = True
except ImportError:
    get_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

try:
    from services.infrastructure.monitoring.critical_alert import CriticalAlertService
    _CRITICAL_ALERT_AVAILABLE = True
except ImportError:
    CriticalAlertService = None
    _CRITICAL_ALERT_AVAILABLE = False

try:
    from services.infrastructure.monitoring.process_monitor import get_process_monitor
    _PROCESS_MONITOR_AVAILABLE = True
except ImportError:
    get_process_monitor = None
    _PROCESS_MONITOR_AVAILABLE = False

try:
    from services.infrastructure.recovery.database_check_state import get_database_check_state_manager
    _DATABASE_CHECK_STATE_AVAILABLE = True
except ImportError:
    get_database_check_state_manager = None
    _DATABASE_CHECK_STATE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

HEALTH_MONITOR_ENABLED = os.getenv("HEALTH_MONITOR_ENABLED", "true").lower() in ("true", "1", "yes")
HEALTH_MONITOR_INTERVAL_SECONDS = int(os.getenv("HEALTH_MONITOR_INTERVAL_SECONDS", "900"))
HEALTH_MONITOR_SMS_ALERT_COOLDOWN_SECONDS = int(os.getenv("HEALTH_MONITOR_SMS_ALERT_COOLDOWN_SECONDS", "1800"))
HEALTH_MONITOR_FAILURE_THRESHOLD = int(os.getenv("HEALTH_MONITOR_FAILURE_THRESHOLD", "1"))
HEALTH_MONITOR_TIMEOUT_SECONDS = int(os.getenv("HEALTH_MONITOR_TIMEOUT_SECONDS", "30"))
HEALTH_MONITOR_STARTUP_DELAY_SECONDS = int(os.getenv("HEALTH_MONITOR_STARTUP_DELAY_SECONDS", "10"))

# Get server port from environment
SERVER_PORT = int(os.getenv("PORT", "9527"))
HEALTH_ENDPOINT_URL = f"http://localhost:{SERVER_PORT}/health/all"

# Redis keys for distributed coordination
MONITOR_LOCK_KEY = "health_monitor:lock"
MONITOR_LOCK_TTL = 60
SMS_ALERT_COOLDOWN_KEY = "health_monitor:sms_cooldown"


# ============================================================================
# Health Status Dataclass
# ============================================================================

@dataclass
class HealthStatus:
    """Health check status and metrics"""
    status: str
    last_check_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_alert_time: Optional[float] = None
    total_checks: int = 0
    total_failures: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary for API responses"""
        return {
            "status": self.status,
            "last_check_time": self.last_check_time,
            "last_success_time": self.last_success_time,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time,
            "last_alert_time": self.last_alert_time,
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "last_error": self.last_error,
        }


# ============================================================================
# Health Monitor Class
# ============================================================================

class HealthMonitor:
    """
    Monitors overall server health by periodically calling /health/all endpoint.

    Features:
    - Periodic health checks via HTTP endpoint
    - SMS alerts for unhealthy/degraded status
    - Cooldown mechanism (prevents alert spam)
    - Multi-worker coordination via Redis distributed lock
    """

    def __init__(self):
        """Initialize HealthMonitor"""
        self.status = HealthStatus(status="unknown")
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(HEALTH_MONITOR_TIMEOUT_SECONDS),
                http2=True
            )
        return self._http_client

    async def _close_http_client(self) -> None:
        """Close HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _acquire_monitor_lock(self) -> bool:
        """
        Acquire Redis distributed lock for monitoring.

        Only one worker across all processes should run monitoring.

        Returns:
            True if lock acquired, False otherwise
        """
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            lock_acquired = await asyncio.to_thread(
                redis_client.set,
                MONITOR_LOCK_KEY,
                f"{os.getpid()}:{time.time()}",
                ex=MONITOR_LOCK_TTL,
                nx=True
            )

            return bool(lock_acquired)
        except Exception as e:
            logger.debug("[HealthMonitor] Failed to acquire monitor lock: %s", e)
            return False

    async def _refresh_monitor_lock(self) -> bool:
        """
        Refresh monitor lock TTL if held by this worker.

        Returns:
            True if lock refreshed, False if not held
        """
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            lock_value = await asyncio.to_thread(redis_client.get, MONITOR_LOCK_KEY)
            if lock_value:
                if isinstance(lock_value, bytes):
                    lock_pid = lock_value.decode('utf-8').split(':', maxsplit=1)[0]
                else:
                    lock_pid = str(lock_value).split(':', maxsplit=1)[0]
                if lock_pid == str(os.getpid()):
                    await asyncio.to_thread(
                        redis_client.expire,
                        MONITOR_LOCK_KEY,
                        MONITOR_LOCK_TTL
                    )
                    return True
            return False
        except Exception as e:
            logger.debug("[HealthMonitor] Failed to refresh monitor lock: %s", e)
            return False

    async def _check_sms_cooldown(self) -> bool:
        """
        Check if SMS alert is in cooldown period.

        Returns:
            True if in cooldown (should not send), False if can send
        """
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            exists = await asyncio.to_thread(redis_client.exists, SMS_ALERT_COOLDOWN_KEY)
            return bool(exists)
        except Exception:
            return False

    async def _set_sms_cooldown(self) -> None:
        """Set SMS alert cooldown period"""
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return

        try:
            if get_redis is None:
                return
            redis_client = get_redis()
            if redis_client is None:
                return

            await asyncio.to_thread(
                redis_client.setex,
                SMS_ALERT_COOLDOWN_KEY,
                HEALTH_MONITOR_SMS_ALERT_COOLDOWN_SECONDS,
                str(time.time())
            )
        except Exception as e:
            logger.warning("[HealthMonitor] Failed to set SMS cooldown: %s", e)

    async def _send_sms_alert(self, reason: str, critical: bool = False) -> None:
        """
        Send SMS alert to admin phones via centralized critical alert service.

        Args:
            reason: Reason for the alert
            critical: If True, indicates critical failure (currently unused,
                     reserved for future use to bypass cooldown)
        """
        if not _CRITICAL_ALERT_AVAILABLE or CriticalAlertService is None:
            logger.warning("[HealthMonitor] Critical alert service not available")
            return

        try:
            await CriticalAlertService.send_runtime_error_alert(
                component="Server",
                error_message=reason,
                details="Health monitor detected server health issues. "
                        "Check /health/all endpoint and logs for details."
            )
            self.status.last_alert_time = time.time()
            if critical:
                logger.info("[HealthMonitor] Critical alert sent: %s", reason)
        except Exception as e:
            logger.error(
                "[HealthMonitor] Error sending SMS alert via critical alert service: %s",
                e,
                exc_info=True
            )

    async def _check_process_monitor_status(self) -> Optional[Dict[str, Any]]:
        """
        Check process monitor status to see if it's handling service failures.

        Returns:
            Process monitor status dict if available, None otherwise
        """
        if not _PROCESS_MONITOR_AVAILABLE or get_process_monitor is None:
            return None

        try:
            process_monitor = get_process_monitor()
            return process_monitor.get_status()
        except Exception as e:
            logger.debug("[HealthMonitor] Failed to get process monitor status: %s", e)
            return None

    def _is_process_monitor_handling_issue(
        self,
        health_response: Dict[str, Any],
        process_monitor_status: Optional[Dict[str, Any]]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if process monitor is actively handling the health issue.

        Process monitor handles: qdrant, celery, redis
        Health monitor should alert if:
        - Process monitor circuit breaker is open (restart attempts failed)
        - Issue is not handled by process monitor (database, LLM, etc.)
        - Process monitor status unavailable

        Health monitor should NOT alert if:
        - Process monitor is actively attempting restarts (circuit breaker closed, restart_count > 0)

        Returns:
            Tuple of (is_handling, reason)
            is_handling: True if process monitor is handling it, False if it has given up or can't handle it
            reason: Explanation of why it's handling/not handling
        """
        if not process_monitor_status:
            return False, "Process monitor status unavailable - alerting"

        checks = health_response.get("checks", {})
        if not isinstance(checks, dict):
            return False, "Invalid health check response structure"

        process_monitor_services = {"qdrant", "celery", "redis"}
        unhealthy_components = []
        process_monitor_handled_components = []

        for check_name, check_data in checks.items():
            if not isinstance(check_data, dict):
                continue
            check_status = check_data.get("status", "unknown")
            if check_status in ("unhealthy", "error"):
                unhealthy_components.append(check_name)
                if check_name in process_monitor_services:
                    process_monitor_handled_components.append(check_name)

        if not process_monitor_handled_components:
            return False, "Issue not handled by process monitor (database, LLM, etc.) - alerting"

        for service_name in process_monitor_handled_components:
            service_status = process_monitor_status.get(service_name)
            if not isinstance(service_status, dict):
                continue

            circuit_breaker_open = service_status.get("circuit_breaker_open", False)
            status = service_status.get("status", "unknown")
            consecutive_failures = service_status.get("consecutive_failures", 0)
            restart_count = service_status.get("restart_count", 0)

            if circuit_breaker_open:
                return (
                    False,
                    f"Process monitor circuit breaker open for {service_name} "
                    "(restart attempts failed) - alerting"
                )

            if status == "unhealthy" and consecutive_failures > 0 and restart_count > 0:
                return True, f"Process monitor is attempting to restart {service_name} - suppressing alert"

        return False, None

    async def _check_health(self) -> tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check server health by calling /health/all endpoint.

        Returns:
            Tuple of (status, error_message, response_data)
            status: "healthy", "degraded", "unhealthy", or "error"
            error_message: Error description if status is "error", None otherwise
            response_data: Parsed JSON response if available, None otherwise
        """
        try:
            client = await self._get_http_client()
            response = await client.get(HEALTH_ENDPOINT_URL)

            if response.status_code == 200:
                try:
                    data = response.json()
                    overall_status = data.get("status", "unknown")
                    if overall_status == "healthy":
                        return "healthy", None, data
                    elif overall_status == "degraded":
                        return "degraded", None, data
                    else:
                        return "unhealthy", f"Status: {overall_status}", data
                except (ValueError, json.JSONDecodeError) as e:
                    return "error", f"Failed to parse JSON response: {e}", None

            elif response.status_code == 503:
                try:
                    data = response.json()
                    overall_status = data.get("status", "unknown")
                    if overall_status == "unhealthy":
                        return "unhealthy", f"HTTP 503 - Status: {overall_status}", data
                    else:
                        return "degraded", f"HTTP 503 - Status: {overall_status}", data
                except (ValueError, json.JSONDecodeError):
                    return "degraded", "HTTP 503 - Service Unavailable", None

            elif response.status_code == 500:
                try:
                    data = response.json()
                    error_msg = data.get("errors", ["Unknown error"])
                    if isinstance(error_msg, list) and error_msg:
                        error_msg = error_msg[0]
                    return "unhealthy", f"HTTP 500 - {error_msg}", data
                except (ValueError, json.JSONDecodeError):
                    return "unhealthy", "HTTP 500 - Internal Server Error", None

            else:
                return "error", f"Unexpected HTTP status: {response.status_code}", None

        except httpx.TimeoutException:
            return "error", "Health check timeout", None
        except httpx.ConnectError:
            return "error", "Connection error - server may be down", None
        except httpx.HTTPError as e:
            return "error", f"HTTP error: {e}", None
        except Exception as e:
            return "error", f"Unexpected error: {e}", None

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - runs periodically"""
        logger.info("[HealthMonitor] Starting monitoring loop (interval: %ds)", HEALTH_MONITOR_INTERVAL_SECONDS)

        while not self._shutdown_event.is_set():
            try:
                if not await self._refresh_monitor_lock():
                    logger.debug("[HealthMonitor] Lost monitor lock, waiting...")
                    await asyncio.sleep(HEALTH_MONITOR_INTERVAL_SECONDS)
                    continue

                check_time = time.time()
                self.status.last_check_time = check_time
                self.status.total_checks += 1

                health_status, error_msg, response_data = await self._check_health()

                if health_status == "healthy":
                    self.status.status = "healthy"
                    self.status.last_success_time = check_time
                    self.status.consecutive_failures = 0
                    self.status.last_error = None
                    logger.debug("[HealthMonitor] Health check passed")

                elif health_status in ("degraded", "unhealthy", "error"):
                    self.status.consecutive_failures += 1
                    self.status.last_failure_time = check_time
                    self.status.total_failures += 1
                    self.status.last_error = error_msg

                    if health_status == "unhealthy":
                        self.status.status = "unhealthy"
                        logger.warning(
                            "[HealthMonitor] Health check failed (unhealthy): %s",
                            error_msg
                        )
                    elif health_status == "degraded":
                        self.status.status = "degraded"
                        logger.warning(
                            "[HealthMonitor] Health check failed (degraded): %s",
                            error_msg
                        )
                    else:
                        self.status.status = "error"
                        logger.error(
                            "[HealthMonitor] Health check error: %s",
                            error_msg
                        )

                    if self.status.consecutive_failures >= HEALTH_MONITOR_FAILURE_THRESHOLD:
                        should_alert = True
                        alert_reason = f"Server health check failed: {health_status}"
                        if error_msg:
                            alert_reason += f" - {error_msg}"

                        if response_data:
                            checks = response_data.get("checks", {})
                            unhealthy_components = []
                            for check_name, check_data in checks.items():
                                if isinstance(check_data, dict):
                                    check_status = check_data.get("status", "unknown")
                                    if check_status in ("unhealthy", "error"):
                                        unhealthy_components.append(check_name)

                            if unhealthy_components:
                                alert_reason += f" (Components: {', '.join(unhealthy_components)})"

                            # Check if database check is in progress (long-running operation)
                            if "database" in unhealthy_components:
                                if _DATABASE_CHECK_STATE_AVAILABLE and get_database_check_state_manager:
                                    try:
                                        state_manager = get_database_check_state_manager()
                                        if await state_manager.is_check_in_progress():
                                            should_alert = False
                                            logger.info(
                                                "[HealthMonitor] Database check is in progress "
                                                "(long-running operation), skipping alert"
                                            )
                                            unhealthy_components = [
                                                c for c in unhealthy_components
                                                if c != "database"
                                            ]
                                            if unhealthy_components:
                                                alert_reason = (
                                                    f"Server health check failed: {health_status}"
                                                )
                                                if error_msg:
                                                    alert_reason += f" - {error_msg}"
                                                alert_reason += f" (Components: {', '.join(unhealthy_components)})"
                                            else:
                                                # All issues are database-related and check is in progress
                                                should_alert = False
                                                logger.info(
                                                    "[HealthMonitor] All issues are database-related "
                                                    "and check is in progress, skipping alert"
                                                )
                                    except Exception as e:
                                        logger.debug(
                                            "[HealthMonitor] Failed to check database state: %s",
                                            e
                                        )

                            process_monitor_status = await self._check_process_monitor_status()
                            if process_monitor_status:
                                is_handling, handling_reason = self._is_process_monitor_handling_issue(
                                    response_data,
                                    process_monitor_status
                                )
                                if is_handling:
                                    should_alert = False
                                    logger.info(
                                        "[HealthMonitor] Process monitor is handling the issue, "
                                        "skipping alert: %s",
                                        handling_reason
                                    )
                                elif handling_reason:
                                    alert_reason += f" - {handling_reason}"

                        if should_alert:
                            is_critical = health_status == "unhealthy"
                            await self._send_sms_alert(alert_reason, critical=is_critical)
                        else:
                            logger.debug(
                                "[HealthMonitor] Alert suppressed - process monitor is handling the issue"
                            )

                await asyncio.sleep(HEALTH_MONITOR_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("[HealthMonitor] Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error("[HealthMonitor] Error in monitoring loop: %s", e, exc_info=True)
                await asyncio.sleep(HEALTH_MONITOR_INTERVAL_SECONDS)

        logger.info("[HealthMonitor] Monitoring loop stopped")

    async def start(self) -> None:
        """Start health monitoring"""
        if not HEALTH_MONITOR_ENABLED:
            logger.info("[HealthMonitor] Health monitoring disabled")
            return

        logger.info("[HealthMonitor] Starting health monitor...")

        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            logger.warning("[HealthMonitor] Redis not available, monitoring disabled")
            return

        if not await self._acquire_monitor_lock():
            logger.info("[HealthMonitor] Monitor lock held by another worker, this worker will wait")
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(30)
                    if await self._acquire_monitor_lock():
                        logger.info("[HealthMonitor] Monitor lock acquired, starting monitoring")
                        break
                except asyncio.CancelledError:
                    return
                except Exception:
                    pass

        # Wait for server to be ready before starting health checks
        # This prevents the health monitor from making HTTP requests before
        # Uvicorn has finished starting the server and accepting connections
        if HEALTH_MONITOR_STARTUP_DELAY_SECONDS > 0:
            logger.info(
                "[HealthMonitor] Waiting %d seconds for server to be ready before starting health checks",
                HEALTH_MONITOR_STARTUP_DELAY_SECONDS
            )
            try:
                await asyncio.sleep(HEALTH_MONITOR_STARTUP_DELAY_SECONDS)
            except asyncio.CancelledError:
                logger.info("[HealthMonitor] Startup delay cancelled")
                return

        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("[HealthMonitor] Health monitor started")

    async def stop(self) -> None:
        """Stop health monitoring"""
        logger.info("[HealthMonitor] Stopping health monitor...")
        self._shutdown_event.set()

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        await self._close_http_client()
        logger.info("[HealthMonitor] Health monitor stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current health monitoring status.

        Returns:
            Dictionary with monitoring status and metrics
        """
        return self.status.to_dict()


# Global HealthMonitor instance (singleton pattern)
class _HealthMonitorSingleton:
    """Singleton holder for HealthMonitor instance"""
    _instance: Optional[HealthMonitor] = None

    @classmethod
    def get_instance(cls) -> HealthMonitor:
        """Get singleton HealthMonitor instance"""
        if cls._instance is None:
            cls._instance = HealthMonitor()
        return cls._instance


def get_health_monitor() -> HealthMonitor:
    """Get global HealthMonitor instance"""
    return _HealthMonitorSingleton.get_instance()
