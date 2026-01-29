"""
Process Monitor Service for MindGraph Application

Monitors health of critical services (Qdrant, Celery, Redis) and automatically
restarts failed subprocesses with circuit breaker protection.

Features:
- Periodic health monitoring (configurable interval)
- Auto-restart for crashed subprocesses (Qdrant, Celery)
- Circuit breaker pattern (prevents restart loops)
- SMS alerts for critical failures
- Multi-worker coordination via Redis distributed lock

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any

try:
    from services.redis.redis_client import get_redis, is_redis_available, RedisOps
    _REDIS_AVAILABLE = True
except ImportError:
    get_redis = None
    is_redis_available = None
    RedisOps = None
    _REDIS_AVAILABLE = False

from services.infrastructure.process.process_manager import (
    ServerState,
    start_qdrant_server,
    start_celery_worker,
    start_postgresql_server,
    stop_qdrant_server,
    stop_celery_worker,
    stop_postgresql_server
)

try:
    from services.infrastructure.monitoring.critical_alert import CriticalAlertService
except ImportError:
    CriticalAlertService = None

try:
    from config.celery import celery_app
except ImportError:
    celery_app = None

try:
    from config.settings import config
    _CONFIG_AVAILABLE = True
except ImportError:
    config = None
    _CONFIG_AVAILABLE = False

try:
    import psycopg2
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    _PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

PROCESS_MONITOR_ENABLED = os.getenv("PROCESS_MONITOR_ENABLED", "true").lower() in ("true", "1", "yes")
PROCESS_MONITOR_INTERVAL_SECONDS = int(os.getenv("PROCESS_MONITOR_INTERVAL_SECONDS", "30"))
PROCESS_MONITOR_MAX_RESTARTS = int(os.getenv("PROCESS_MONITOR_MAX_RESTARTS", "3"))
PROCESS_MONITOR_RESTART_WINDOW_SECONDS = int(os.getenv("PROCESS_MONITOR_RESTART_WINDOW_SECONDS", "300"))
PROCESS_MONITOR_CIRCUIT_BREAKER_ENABLED = (
    os.getenv("PROCESS_MONITOR_CIRCUIT_BREAKER_ENABLED", "true").lower()
    in ("true", "1", "yes")
)
PROCESS_MONITOR_SMS_ALERTS_ENABLED = (
    os.getenv("PROCESS_MONITOR_SMS_ALERTS_ENABLED", "true").lower()
    in ("true", "1", "yes")
)
PROCESS_MONITOR_SMS_ALERT_COOLDOWN_SECONDS = int(os.getenv("PROCESS_MONITOR_SMS_ALERT_COOLDOWN_SECONDS", "600"))

# Redis keys for distributed coordination
MONITOR_LOCK_KEY = "process_monitor:lock"
MONITOR_LOCK_TTL = 60  # 1 minute - auto-release if worker crashes
RESTART_COUNTER_KEY_PREFIX = "process_monitor:restarts:"
SMS_ALERT_COOLDOWN_KEY_PREFIX = "process_monitor:sms_cooldown:"
STATUS_KEY_PREFIX = "process_monitor:status:"


# ============================================================================
# Service Status Enum
# ============================================================================

class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


# ============================================================================
# Service Metrics Dataclass
# ============================================================================

@dataclass
class ServiceMetrics:
    """Metrics for a monitored service"""
    service_name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check_time: Optional[float] = None
    last_success_time: Optional[float] = None
    restart_count: int = 0
    consecutive_failures: int = 0
    uptime_seconds: Optional[float] = None
    start_time: Optional[float] = None
    last_restart_time: Optional[float] = None
    last_sms_alert_time: Optional[float] = None
    circuit_breaker_open: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for API responses"""
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "last_check_time": self.last_check_time,
            "last_success_time": self.last_success_time,
            "restart_count": self.restart_count,
            "consecutive_failures": self.consecutive_failures,
            "uptime_seconds": self.uptime_seconds,
            "start_time": self.start_time,
            "last_restart_time": self.last_restart_time,
            "last_sms_alert_time": self.last_sms_alert_time,
            "circuit_breaker_open": self.circuit_breaker_open,
        }


# ============================================================================
# Process Monitor Class
# ============================================================================

class ProcessMonitor:
    """
    Monitors health of critical services and automatically restarts failed subprocesses.

    Features:
    - Periodic health checks (Qdrant, Celery, Redis)
    - Auto-restart with circuit breaker protection
    - SMS alerts for critical failures
    - Multi-worker coordination via Redis distributed lock
    """

    def __init__(self):
        """Initialize ProcessMonitor"""
        self.metrics: Dict[str, ServiceMetrics] = {
            "qdrant": ServiceMetrics(service_name="qdrant"),
            "celery": ServiceMetrics(service_name="celery"),
            "redis": ServiceMetrics(service_name="redis"),
            "postgresql": ServiceMetrics(service_name="postgresql"),
        }
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._last_multiple_failure_alert_time: Optional[float] = None

    async def _acquire_monitor_lock(self) -> bool:
        """
        Acquire Redis distributed lock for monitoring.

        Only one worker across all processes should run monitoring.

        Returns:
            True if lock acquired, False otherwise
        """
        if not _REDIS_AVAILABLE:
            return False
        if is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            # Try to acquire lock using SETNX (SET if Not eXists)
            lock_acquired = await asyncio.to_thread(
                redis_client.set,
                MONITOR_LOCK_KEY,
                f"{os.getpid()}:{time.time()}",
                ex=MONITOR_LOCK_TTL,
                nx=True
            )

            return bool(lock_acquired)
        except Exception as e:
            logger.debug("Failed to acquire monitor lock: %s", e)
            return False

    async def _refresh_monitor_lock(self) -> bool:
        """
        Refresh monitor lock TTL if held by this worker.

        Returns:
            True if lock refreshed, False if not held
        """
        if not _REDIS_AVAILABLE:
            return False
        if is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            # Check if we hold the lock and refresh TTL
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
            logger.debug("Failed to refresh monitor lock: %s", e)
            return False

    async def _check_redis_health(self) -> ServiceStatus:
        """
        Check Redis health.

        Returns:
            ServiceStatus (HEALTHY or UNHEALTHY)
        """
        try:
            if not _REDIS_AVAILABLE:
                return ServiceStatus.UNHEALTHY
            if is_redis_available is None or not is_redis_available():
                return ServiceStatus.UNHEALTHY
            if RedisOps is None:
                return ServiceStatus.UNHEALTHY

            ping_result = await asyncio.wait_for(
                asyncio.to_thread(RedisOps.ping),
                timeout=2.0
            )

            if ping_result:
                return ServiceStatus.HEALTHY
            return ServiceStatus.UNHEALTHY
        except asyncio.TimeoutError:
            logger.warning("[ProcessMonitor] Redis health check timed out")
            return ServiceStatus.UNHEALTHY
        except Exception as e:
            logger.warning("[ProcessMonitor] Redis health check failed: %s", e)
            return ServiceStatus.UNHEALTHY

    async def _check_qdrant_health(self) -> ServiceStatus:
        """
        Check Qdrant health.

        Returns:
            ServiceStatus (HEALTHY or UNHEALTHY)
        """
        # Skip Qdrant check if RAG is disabled
        if _CONFIG_AVAILABLE and config is not None:
            if not config.FEATURE_KNOWLEDGE_SPACE:
                return ServiceStatus.HEALTHY

        try:
            # HTTP check (run in thread pool to avoid blocking)
            def check_http():
                try:
                    urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
                    return True
                except Exception:
                    return False

            http_ok = await asyncio.wait_for(
                asyncio.to_thread(check_http),
                timeout=2.5
            )

            if not http_ok:
                return ServiceStatus.UNHEALTHY

            # Process check if subprocess managed
            if ServerState.qdrant_process is not None:
                return_code = ServerState.qdrant_process.poll()
                if return_code is not None:
                    # Process has terminated
                    logger.warning("[ProcessMonitor] Qdrant process terminated (return code: %s)", return_code)
                    return ServiceStatus.UNHEALTHY

            return ServiceStatus.HEALTHY
        except asyncio.TimeoutError:
            logger.warning("[ProcessMonitor] Qdrant health check timed out")
            return ServiceStatus.UNHEALTHY
        except Exception as e:
            logger.warning("[ProcessMonitor] Qdrant health check failed: %s", e)
            return ServiceStatus.UNHEALTHY

    async def _check_celery_health(self) -> ServiceStatus:
        """
        Check Celery worker health.

        Returns:
            ServiceStatus (HEALTHY or UNHEALTHY)
        """
        # Skip Celery check if RAG is disabled
        if _CONFIG_AVAILABLE and config is not None:
            if not config.FEATURE_KNOWLEDGE_SPACE:
                return ServiceStatus.HEALTHY

        try:
            if celery_app is None:
                logger.warning("[ProcessMonitor] Celery app not available")
                return ServiceStatus.UNHEALTHY

            # Check for active workers via Redis broker
            inspect = celery_app.control.inspect(timeout=2.0)
            active_workers = await asyncio.to_thread(inspect.active)

            if active_workers is None or not active_workers:
                logger.warning("[ProcessMonitor] No active Celery workers found")
                return ServiceStatus.UNHEALTHY

            # Process check if subprocess managed
            if ServerState.celery_worker_process is not None:
                return_code = ServerState.celery_worker_process.poll()
                if return_code is not None:
                    # Process has terminated
                    logger.warning("[ProcessMonitor] Celery process terminated (return code: %s)", return_code)
                    return ServiceStatus.UNHEALTHY

            return ServiceStatus.HEALTHY
        except Exception as e:
            logger.warning("[ProcessMonitor] Celery health check failed: %s", e)
            return ServiceStatus.UNHEALTHY

    async def _check_postgresql_health(self) -> ServiceStatus:
        """
        Check PostgreSQL health.

        Returns:
            ServiceStatus (HEALTHY or UNHEALTHY)
        """
        try:
            if not _PSYCOPG2_AVAILABLE or psycopg2 is None:
                # psycopg2 not installed, skip PostgreSQL check
                logger.debug("[ProcessMonitor] psycopg2 not available, skipping PostgreSQL health check")
                return ServiceStatus.HEALTHY

            # Store reference for type checking
            pg_module = psycopg2

            db_url = os.getenv('DATABASE_URL', '')
            if not db_url or 'postgresql' not in db_url.lower():
                # Not using PostgreSQL, skip check
                return ServiceStatus.HEALTHY

            # Connection test (run in thread pool to avoid blocking)
            def check_connection():
                try:
                    conn = pg_module.connect(db_url, connect_timeout=2)
                    conn.close()
                    return True
                except Exception:
                    return False

            connection_ok = await asyncio.wait_for(
                asyncio.to_thread(check_connection),
                timeout=2.5
            )

            if not connection_ok:
                return ServiceStatus.UNHEALTHY

            # Process check if subprocess managed
            if ServerState.postgresql_process is not None:
                return_code = ServerState.postgresql_process.poll()
                if return_code is not None:
                    # Process has terminated
                    logger.warning("[ProcessMonitor] PostgreSQL process terminated (return code: %s)", return_code)
                    return ServiceStatus.UNHEALTHY

            return ServiceStatus.HEALTHY
        except asyncio.TimeoutError:
            logger.warning("[ProcessMonitor] PostgreSQL health check timed out")
            return ServiceStatus.UNHEALTHY
        except Exception as e:
            logger.warning("[ProcessMonitor] PostgreSQL health check failed: %s", e)
            return ServiceStatus.UNHEALTHY

    async def _check_restart_count(self, service_name: str) -> int:
        """
        Get restart count for service in current time window.

        Returns:
            Number of restarts in the time window
        """
        if not _REDIS_AVAILABLE:
            return 0
        if is_redis_available is None or not is_redis_available():
            return 0

        try:
            if get_redis is None:
                return 0
            redis_client = get_redis()
            if redis_client is None:
                return 0

            key = f"{RESTART_COUNTER_KEY_PREFIX}{service_name}"
            count = await asyncio.to_thread(redis_client.get, key)
            return int(count) if count else 0
        except Exception:
            return 0

    async def _increment_restart_count(self, service_name: str) -> int:
        """
        Increment restart count for service.

        Returns:
            New restart count
        """
        if not _REDIS_AVAILABLE:
            return 0
        if is_redis_available is None or not is_redis_available():
            return 0

        try:
            if get_redis is None:
                return 0
            redis_client = get_redis()
            if redis_client is None:
                return 0

            key = f"{RESTART_COUNTER_KEY_PREFIX}{service_name}"
            count = await asyncio.to_thread(
                redis_client.incr,
                key
            )
            await asyncio.to_thread(
                redis_client.expire,
                key,
                PROCESS_MONITOR_RESTART_WINDOW_SECONDS
            )
            return int(count)
        except Exception as e:
            logger.warning("[ProcessMonitor] Failed to increment restart count: %s", e)
            return 0

    async def _check_sms_cooldown(self, service_name: str) -> bool:
        """
        Check if SMS alert is in cooldown period.

        Returns:
            True if in cooldown (should not send), False if can send
        """
        if not _REDIS_AVAILABLE:
            return False
        if is_redis_available is None or not is_redis_available():
            return False

        try:
            if get_redis is None:
                return False
            redis_client = get_redis()
            if redis_client is None:
                return False

            key = f"{SMS_ALERT_COOLDOWN_KEY_PREFIX}{service_name}"
            exists = await asyncio.to_thread(redis_client.exists, key)
            return bool(exists)
        except Exception:
            return False

    async def _set_sms_cooldown(self, service_name: str) -> None:
        """Set SMS alert cooldown period"""
        if not _REDIS_AVAILABLE:
            return
        if is_redis_available is None or not is_redis_available():
            return

        try:
            if get_redis is None:
                return
            redis_client = get_redis()
            if redis_client is None:
                return

            key = f"{SMS_ALERT_COOLDOWN_KEY_PREFIX}{service_name}"
            await asyncio.to_thread(
                redis_client.setex,
                key,
                PROCESS_MONITOR_SMS_ALERT_COOLDOWN_SECONDS,
                str(time.time())
            )
        except Exception as e:
            logger.warning("[ProcessMonitor] Failed to set SMS cooldown: %s", e)

    async def _send_sms_alert(self, service_name: str, reason: str) -> None:
        """
        Send SMS alert to admin phones via centralized critical alert service.

        Args:
            service_name: Name of the service that failed
            reason: Reason for the alert
        """
        if not PROCESS_MONITOR_SMS_ALERTS_ENABLED:
            return

        try:
            if CriticalAlertService is None:
                logger.warning("[ProcessMonitor] CriticalAlertService not available")
                return

            await CriticalAlertService.send_runtime_error_alert(
                component=service_name.capitalize(),
                error_message=reason,
                details=(
                    f"Process monitor detected {service_name} failure. "
                    "Check service status and logs."
                )
            )
            self.metrics[service_name].last_sms_alert_time = time.time()
        except Exception as e:
            logger.error(
                "[ProcessMonitor] Error sending SMS alert via critical alert service: %s",
                e,
                exc_info=True
            )

    async def _restart_service(self, service_name: str) -> bool:
        """
        Restart a failed service.

        Args:
            service_name: Name of service to restart ('qdrant' or 'celery')

        Returns:
            True if restart successful, False otherwise
        """
        logger.info("[ProcessMonitor] Attempting to restart %s...", service_name)

        try:
            if service_name == "qdrant":
                # Stop existing process if any (run in thread pool to avoid blocking)
                if ServerState.qdrant_process is not None:
                    await asyncio.to_thread(stop_qdrant_server)

                # Start new process (run in thread pool)
                process = await asyncio.to_thread(start_qdrant_server)
                if process is not None:
                    logger.info("[ProcessMonitor] Qdrant restarted successfully (PID: %s)", process.pid)
                    return True
                else:
                    # Process already running externally
                    logger.info("[ProcessMonitor] Qdrant is running externally")
                    return True

            elif service_name == "celery":
                # Stop existing process if any (run in thread pool)
                if ServerState.celery_worker_process is not None:
                    await asyncio.to_thread(stop_celery_worker)

                # Start new process (run in thread pool)
                process = await asyncio.to_thread(start_celery_worker)
                if process is not None:
                    logger.info("[ProcessMonitor] Celery restarted successfully (PID: %s)", process.pid)
                    return True

            elif service_name == "postgresql":
                # Stop existing process if any (run in thread pool)
                if ServerState.postgresql_process is not None:
                    await asyncio.to_thread(stop_postgresql_server)

                # Start new process (run in thread pool)
                process = await asyncio.to_thread(start_postgresql_server)
                if process is not None:
                    logger.info("[ProcessMonitor] PostgreSQL restarted successfully (PID: %s)", process.pid)
                    return True
                else:
                    # Process already running externally
                    logger.info("[ProcessMonitor] PostgreSQL is running externally")
                    return True

            return False
        except Exception as e:
            logger.error("[ProcessMonitor] Failed to restart %s: %s", service_name, e, exc_info=True)
            return False

    async def _check_and_restart_service(self, service_name: str, status: ServiceStatus) -> None:
        """
        Check service status and restart if needed.

        Args:
            service_name: Name of service ('qdrant', 'celery', 'redis', or 'postgresql')
            status: Current health status
        """
        metrics = self.metrics[service_name]
        metrics.last_check_time = time.time()

        # Update status
        old_status = metrics.status
        metrics.status = status

        # Update consecutive failures
        if status == ServiceStatus.HEALTHY:
            metrics.consecutive_failures = 0
            metrics.last_success_time = time.time()
            if metrics.start_time is None:
                metrics.start_time = time.time()
            if metrics.uptime_seconds is None and metrics.start_time:
                metrics.uptime_seconds = time.time() - metrics.start_time
            else:
                metrics.uptime_seconds = time.time() - metrics.start_time if metrics.start_time else None
        else:
            metrics.consecutive_failures += 1

        # Log status changes
        if old_status != status:
            logger.info(
                "[ProcessMonitor] %s status changed: %s -> %s",
                service_name.upper(),
                old_status.value,
                status.value
            )

        # Handle restart logic (only for Qdrant, Celery, and PostgreSQL, not Redis)
        if service_name in ("qdrant", "celery", "postgresql") and status == ServiceStatus.UNHEALTHY:
            # Check if process is actually dead
            if service_name == "qdrant":
                process = ServerState.qdrant_process
            elif service_name == "celery":
                process = ServerState.celery_worker_process
            else:  # postgresql
                process = ServerState.postgresql_process

            if process is None:
                # Process not managed by us (external/systemd)
                logger.debug("[ProcessMonitor] %s not managed by app, skipping restart", service_name)
                return

            return_code = process.poll()
            if return_code is None:
                # Process still running but health check failed
                logger.warning("[ProcessMonitor] %s process running but health check failed", service_name)
                return

            # Process is dead - attempt restart
            if PROCESS_MONITOR_CIRCUIT_BREAKER_ENABLED:
                restart_count = await self._check_restart_count(service_name)
                if restart_count >= PROCESS_MONITOR_MAX_RESTARTS:
                    # Circuit breaker open - don't restart
                    if not metrics.circuit_breaker_open:
                        metrics.circuit_breaker_open = True
                        logger.error(
                            "[ProcessMonitor] Circuit breaker OPEN for %s "
                            "(%d restarts in %d seconds)",
                            service_name,
                            restart_count,
                            PROCESS_MONITOR_RESTART_WINDOW_SECONDS
                        )
                        # Send SMS alert for circuit breaker
                        await self._send_sms_alert(
                            service_name,
                            f"Circuit breaker triggered - {service_name} failed {restart_count} times"
                        )
                    return

            # Attempt restart
            restart_success = await self._restart_service(service_name)
            if restart_success:
                metrics.restart_count += 1
                metrics.last_restart_time = time.time()
                metrics.start_time = time.time()
                metrics.circuit_breaker_open = False
                await self._increment_restart_count(service_name)
                logger.info("[ProcessMonitor] %s restarted successfully", service_name.upper())
            else:
                logger.error("[ProcessMonitor] Failed to restart %s", service_name)
                await self._increment_restart_count(service_name)

        # Handle critical failures (Redis down)
        if service_name == "redis" and status == ServiceStatus.UNHEALTHY:
            logger.critical("[ProcessMonitor] Redis is DOWN - application cannot function")
            # Send SMS immediately (no cooldown for critical services)
            await self._send_sms_alert(
                service_name,
                "Redis is down - application cannot function"
            )

        # Handle repeated failures (3+ consecutive) - only send alert once per failure streak
        if metrics.consecutive_failures == 3:
            logger.warning(
                "[ProcessMonitor] %s has failed %d consecutive times",
                service_name.upper(),
                metrics.consecutive_failures
            )
            # Send SMS alert if not in cooldown (only on 3rd failure, not every time)
            await self._send_sms_alert(
                service_name,
                f"{service_name} has failed {metrics.consecutive_failures} consecutive times"
            )

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - runs periodically"""
        logger.info("[ProcessMonitor] Starting monitoring loop (interval: %ds)", PROCESS_MONITOR_INTERVAL_SECONDS)

        while not self._shutdown_event.is_set():
            try:
                # Refresh lock to ensure we still hold it
                if not await self._refresh_monitor_lock():
                    # Lost lock - another worker is monitoring
                    logger.debug("[ProcessMonitor] Lost monitor lock, waiting...")
                    await asyncio.sleep(PROCESS_MONITOR_INTERVAL_SECONDS)
                    continue

                # Perform health checks (run in parallel for efficiency)
                # Check if using PostgreSQL
                db_url = os.getenv('DATABASE_URL', '')
                using_postgresql = 'postgresql' in db_url.lower()

                # Check if RAG is enabled (determines if Celery and Qdrant are needed)
                rag_enabled = (
                    _CONFIG_AVAILABLE and
                    config is not None and
                    config.FEATURE_KNOWLEDGE_SPACE
                )

                if using_postgresql:
                    if rag_enabled:
                        redis_status, qdrant_status, celery_status, postgresql_status = await asyncio.gather(
                            self._check_redis_health(),
                            self._check_qdrant_health(),
                            self._check_celery_health(),
                            self._check_postgresql_health(),
                            return_exceptions=False
                        )
                    else:
                        redis_status, postgresql_status = await asyncio.gather(
                            self._check_redis_health(),
                            self._check_postgresql_health(),
                            return_exceptions=False
                        )
                        qdrant_status = ServiceStatus.HEALTHY  # RAG disabled, skip Qdrant
                        celery_status = ServiceStatus.HEALTHY  # RAG disabled, skip Celery
                else:
                    if rag_enabled:
                        redis_status, qdrant_status, celery_status = await asyncio.gather(
                            self._check_redis_health(),
                            self._check_qdrant_health(),
                            self._check_celery_health(),
                            return_exceptions=False
                        )
                    else:
                        redis_status = await self._check_redis_health()
                        qdrant_status = ServiceStatus.HEALTHY  # RAG disabled, skip Qdrant
                        celery_status = ServiceStatus.HEALTHY  # RAG disabled, skip Celery
                    postgresql_status = ServiceStatus.HEALTHY  # Not using PostgreSQL

                # Check and restart services if needed
                await self._check_and_restart_service("redis", redis_status)
                if rag_enabled:
                    await self._check_and_restart_service("qdrant", qdrant_status)
                    await self._check_and_restart_service("celery", celery_status)
                if using_postgresql:
                    await self._check_and_restart_service("postgresql", postgresql_status)

                # Check for multiple services down
                statuses = [redis_status]
                if rag_enabled:
                    statuses.append(qdrant_status)
                    statuses.append(celery_status)
                if using_postgresql:
                    statuses.append(postgresql_status)
                unhealthy_count = sum(
                    1 for status in statuses
                    if status == ServiceStatus.UNHEALTHY
                )
                total_services = len(statuses)
                if unhealthy_count >= 2:
                    logger.error("[ProcessMonitor] Multiple services down (%d/%d)", unhealthy_count, total_services)
                    # Send SMS alert for multiple failures (with cooldown to prevent spam)
                    current_time = time.time()
                    cooldown_expired = (
                        self._last_multiple_failure_alert_time is None or
                        current_time - self._last_multiple_failure_alert_time >=
                        PROCESS_MONITOR_SMS_ALERT_COOLDOWN_SECONDS
                    )
                    if cooldown_expired:
                        await self._send_sms_alert(
                            "system",
                            f"Multiple services down ({unhealthy_count}/{total_services})"
                        )
                        self._last_multiple_failure_alert_time = current_time
                else:
                    # Reset alert time when services recover
                    self._last_multiple_failure_alert_time = None

                # Wait for next check
                await asyncio.sleep(PROCESS_MONITOR_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("[ProcessMonitor] Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error("[ProcessMonitor] Error in monitoring loop: %s", e, exc_info=True)
                await asyncio.sleep(PROCESS_MONITOR_INTERVAL_SECONDS)

        logger.info("[ProcessMonitor] Monitoring loop stopped")

    async def start(self) -> None:
        """Start process monitoring"""
        if not PROCESS_MONITOR_ENABLED:
            logger.info("[ProcessMonitor] Process monitoring disabled")
            return

        logger.info("[ProcessMonitor] Starting process monitor...")

        # Check if Redis is available (required for distributed lock)
        if not _REDIS_AVAILABLE:
            logger.warning("[ProcessMonitor] Redis not available, monitoring disabled")
            return
        if is_redis_available is None or not is_redis_available():
            logger.warning("[ProcessMonitor] Redis not available, monitoring disabled")
            return

        # Try to acquire lock
        if not await self._acquire_monitor_lock():
            logger.info("[ProcessMonitor] Monitor lock held by another worker, this worker will wait")
            # Keep trying to acquire lock
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    if await self._acquire_monitor_lock():
                        logger.info("[ProcessMonitor] Monitor lock acquired, starting monitoring")
                        break
                except asyncio.CancelledError:
                    return
                except Exception:
                    pass

        # Start monitoring loop
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("[ProcessMonitor] Process monitor started")

    async def stop(self) -> None:
        """Stop process monitoring"""
        logger.info("[ProcessMonitor] Stopping process monitor...")
        self._shutdown_event.set()

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("[ProcessMonitor] Process monitor stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of all monitored services.

        Returns:
            Dictionary with service status and metrics
        """
        return {
            service_name: metrics.to_dict()
            for service_name, metrics in self.metrics.items()
        }


class ProcessMonitorSingleton:
    """Singleton wrapper for ProcessMonitor to avoid global statement"""
    _instance: Optional[ProcessMonitor] = None

    @classmethod
    def get_instance(cls) -> ProcessMonitor:
        """Get global ProcessMonitor instance"""
        if cls._instance is None:
            cls._instance = ProcessMonitor()
        return cls._instance


def get_process_monitor() -> ProcessMonitor:
    """Get global ProcessMonitor instance"""
    return ProcessMonitorSingleton.get_instance()
