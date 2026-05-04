"""
Lifespan management for MindGraph application.

Handles FastAPI application startup and shutdown lifecycle:
- Optional Linux Fail2ban template gate (before Redis)
- Redis initialization

Copy-paste commands for all dependencies: python -m services.infrastructure.utils.launch_commands
- Database initialization and integrity checks
- LLM service initialization
- Background task scheduling
- Resource cleanup on shutdown
"""

import asyncio
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from config.celery import CeleryStartupError, init_celery_worker_check
from config.settings import config
from services.auth.geoip_country import log_geolite_country_mmdb_startup_status

_log_geolite_country_mmdb_startup_status = log_geolite_country_mmdb_startup_status
from services.auth.sms_middleware import get_sms_middleware
from services.infrastructure.lifecycle.lifespan_collab_integration import (
    start_online_collab_subsystem_async,
)
from services.infrastructure.lifecycle.lifespan_db_integration import (
    lifespan_startup_database_phase,
)
from services.infrastructure.lifecycle.lifespan_redis_integration import lifespan_init_redis_phase
from services.infrastructure.lifecycle.lifespan_shutdown import (
    LifespanBackgroundTasks,
    run_lifespan_shutdown,
)
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.monitoring.health_monitor import get_health_monitor
from services.infrastructure.monitoring.process_monitor import get_process_monitor
from services.infrastructure.lifecycle.startup import _handle_shutdown_signal
from services.infrastructure.utils.browser import log_browser_diagnostics
from services.infrastructure.utils.launch_commands import lines_playwright_startup_critical
from services.llm import llm_service
from services.llm.qdrant_startup import QdrantStartupError, init_qdrant_sync
from services.redis.redis_distributed_lock import (
    acquire_startup_sms_notification_lock,
    release_startup_sms_notification_lock,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.infrastructure.security.abuseipdb_service import (
    apply_blacklist_baseline_from_file_async,
    clear_ip_reputation_sismember_cache,
)
from services.infrastructure.security.fail2ban_integration.startup_gate import (
    enforce_fail2ban_startup_or_exit,
)
from services.infrastructure.security.abuseipdb_scheduler import start_abuseipdb_blacklist_scheduler
from services.infrastructure.security.crowdsec_blocklist_service import (
    apply_crowdsec_baseline_from_file_async,
    crowdsec_blocklist_sync_enabled,
    merge_crowdsec_blocklist_from_network,
)
from services.utils.backup_scheduler import start_backup_scheduler
from services.utils.temp_image_cleaner import start_cleanup_scheduler

# PDF auto-import removed - no longer needed for image-based viewing
from agents.inline_recommendations import start_inline_rec_cleanup_scheduler
from utils.auth import AUTH_MODE
from utils.auth.config import ADMIN_PHONES
from utils.dependency_checker import DependencyError, check_system_dependencies

logger = logging.getLogger(__name__)


def _log_security_startup_posture() -> None:
    """
    Log security-relevant configuration once per main worker.

    Helps operators verify production settings: OpenAPI exposure, auth mode,
    and verbose logging that may write user prompts to log files.
    """
    openapi_schema = "enabled" if config.debug else "disabled"
    logger.info(
        "[SECURITY] Startup posture: app_DEBUG=%s LOG_LEVEL=%s OpenAPI_schema=%s",
        config.debug,
        config.log_level,
        openapi_schema,
    )
    logger.info("[SECURITY] AUTH_MODE=%s", AUTH_MODE)
    if AUTH_MODE == "enterprise":
        logger.warning(
            "[SECURITY] AUTH_MODE=enterprise: JWT validation is disabled for all requests. "
            "Use only on isolated networks (VPN, private LAN). "
            "Never expose this deployment directly to the public Internet."
        )
    if not config.debug and config.log_level == "DEBUG":
        logger.warning(
            "[SECURITY] LOG_LEVEL=DEBUG while DEBUG=False: verbose logs (including prompts in some code paths) "
            "may be written to logs/app.log. Prefer LOG_LEVEL=INFO for production."
        )


async def _send_startup_sms_notification_once() -> None:
    """
    Notify admins via SMS at most once per process group.

    Uvicorn does not set UVICORN_WORKER_ID; a Redis lock ensures only one
    worker sends when multiple workers run the lifespan.
    """
    is_debug_mode = os.getenv("DEBUG", "").lower() == "true"
    if is_debug_mode:
        logger.debug("[LIFESPAN] Startup SMS notification skipped (DEBUG mode enabled)")
        return

    sms_startup_enabled = os.getenv("SMS_STARTUP_NOTIFICATION_ENABLED", "true").lower() in ("true", "1", "yes")
    if not sms_startup_enabled:
        logger.debug("[LIFESPAN] Startup SMS notification disabled (SMS_STARTUP_NOTIFICATION_ENABLED=false)")
        return

    sms_middleware = get_sms_middleware()
    if not sms_middleware.is_available:
        logger.debug("[LIFESPAN] SMS service not available, skipping startup SMS notification")
        return

    admin_phones = [phone.strip() for phone in ADMIN_PHONES if phone.strip()]
    if not admin_phones:
        logger.debug("[LIFESPAN] No admin phones configured, skipping startup SMS notification")
        return

    startup_template_id = os.getenv("TENCENT_SMS_TEMPLATE_STARTUP", "").strip()
    if not startup_template_id:
        logger.warning("[LIFESPAN] TENCENT_SMS_TEMPLATE_STARTUP not configured, skipping startup SMS notification")
        return

    lock_token = await acquire_startup_sms_notification_lock()
    if lock_token is None:
        return

    try:
        success, message = await sms_middleware.send_notification(
            phones=admin_phones,
            template_id=startup_template_id,
            template_params=[],
            lang="zh",
        )
        if success:
            logger.info("[LIFESPAN] Startup SMS notification sent successfully: %s", message)
        else:
            logger.warning("[LIFESPAN] Failed to send startup SMS notification: %s", message)
    finally:
        await release_startup_sms_notification_lock(lock_token)




@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Handles application initialization and cleanup.
    """
    # Startup timing
    startup_start = time.time()
    fastapi_app.state.start_time = startup_start
    fastapi_app.state.is_shutting_down = False

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    # Only log startup messages from first worker to avoid repetition.
    # Note: Uvicorn does not set UVICORN_WORKER_ID; default '0' applies to all workers.
    # Features that must run once per cluster (e.g. startup SMS) use Redis locks instead.
    worker_id = os.getenv("UVICORN_WORKER_ID", "0")
    is_main_worker = worker_id == "0" or not worker_id

    if is_main_worker:
        logger.debug("=" * 80)
        logger.debug("FastAPI Application Starting")
        logger.debug("=" * 80)
        logger.debug("[LIFESPAN] Starting lifespan initialization...")
        logger.debug("[LIFESPAN] Signal handlers registered")
        _log_security_startup_posture()
        _log_geolite_country_mmdb_startup_status()
        enforce_fail2ban_startup_or_exit()

    # Initialize Redis (REQUIRED for caching, rate limiting, sessions)
    # Application will exit if Redis is not available
    await lifespan_init_redis_phase(is_main_worker)

    await apply_blacklist_baseline_from_file_async()
    await apply_crowdsec_baseline_from_file_async()
    if crowdsec_blocklist_sync_enabled():
        try:
            await merge_crowdsec_blocklist_from_network()
        except Exception as crowdsec_exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("[CrowdSec] Startup blocklist merge failed: %s", crowdsec_exc)

    clear_ip_reputation_sismember_cache()

    try:
        from utils.auth import warmup_jwt_secret_async

        await warmup_jwt_secret_async()
        if is_main_worker:
            logger.debug("[LIFESPAN] JWT secret cache warmed via async Redis client")
    except Exception as jwt_warm_exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning(
                "[LIFESPAN] JWT secret async warmup failed (sync fallback will be used on first call): %s",
                jwt_warm_exc,
            )

    # Initialize Qdrant (REQUIRED only if Knowledge Space feature is enabled)
    knowledge_space_enabled = config.FEATURE_KNOWLEDGE_SPACE
    if knowledge_space_enabled:
        if is_main_worker:
            logger.debug("[LIFESPAN] Initializing Qdrant...")
        try:
            init_qdrant_sync()
            if is_main_worker:
                logger.debug("Qdrant initialized successfully")
        except QdrantStartupError as e:
            # Error message already logged by init_qdrant_sync with instructions
            # Send critical alert before exiting
            try:
                CriticalAlertService.send_startup_failure_alert_sync(
                    component="Qdrant",
                    error_message=f"Qdrant startup failed: {str(e)}",
                    details=(
                        "Application cannot start without Qdrant when Knowledge Space is enabled. "
                        "Check Qdrant connection and configuration."
                    ),
                )
            except Exception as alert_error:  # pylint: disable=broad-except
                logger.error("Failed to send startup failure alert: %s", alert_error)
            logger.error("Application startup failed. Exiting.")
            os._exit(1)  # pylint: disable=protected-access
    else:
        if is_main_worker:
            logger.debug("[LIFESPAN] Skipping Qdrant initialization (Knowledge Space feature is disabled)")

    # Check Celery worker availability (REQUIRED only if Knowledge Space feature is enabled)
    if knowledge_space_enabled:
        if is_main_worker:
            logger.debug("[LIFESPAN] Checking Celery worker availability...")
        try:
            init_celery_worker_check()
            if is_main_worker:
                logger.debug("Celery worker is available")
        except CeleryStartupError as e:
            # Error message already logged by init_celery_worker_check with instructions
            # Send critical alert before exiting
            try:
                CriticalAlertService.send_startup_failure_alert_sync(
                    component="Celery",
                    error_message=f"Celery worker unavailable: {str(e)}",
                    details=(
                        "Application cannot start without Celery worker when Knowledge Space is enabled. "
                        "Start Celery worker: celery -A config.celery worker --loglevel=info"
                    ),
                )
            except Exception as alert_error:  # pylint: disable=broad-except
                logger.error("Failed to send startup failure alert: %s", alert_error)
            logger.error("Application startup failed. Exiting.")
            os._exit(1)  # pylint: disable=protected-access
    else:
        if is_main_worker:
            logger.debug("[LIFESPAN] Skipping Celery worker check (Knowledge Space feature is disabled)")

    # Check system dependencies for Knowledge Space feature (Tesseract OCR)
    # Application will exit if required dependencies are missing
    if is_main_worker:
        logger.debug("[LIFESPAN] Checking system dependencies...")
    try:
        if not check_system_dependencies(exit_on_error=True):
            # check_system_dependencies already exits, but this is a safety check
            logger.error("System dependency check failed. Exiting.")
            os._exit(1)  # pylint: disable=protected-access
        if is_main_worker:
            logger.debug("System dependencies check passed")
    except DependencyError as e:
        if is_main_worker:
            logger.error("Dependency check failed: %s", e)
        try:
            CriticalAlertService.send_startup_failure_alert_sync(
                component="Dependencies",
                error_message=f"System dependency check failed: {str(e)}",
                details=("Required system dependencies are missing. Check Tesseract OCR installation."),
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            if is_main_worker:
                logger.error("Failed to send startup failure alert: %s", alert_error)
        os._exit(1)  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-except
        # Log but don't exit on unexpected errors during dependency check
        # This allows the app to start even if dependency check has issues
        if is_main_worker:
            logger.warning("Error during dependency check (non-fatal): %s", e)

    # Note: Legacy JavaScript cache removed in v5.0.0 (Vue migration)
    # Frontend assets are now served from frontend/dist/ via Vue SPA handler

    await lifespan_startup_database_phase(is_main_worker)

    # Initialize LLM Service
    if is_main_worker:
        logger.debug("[LIFESPAN] Initializing LLM clients...")
        logger.debug("[LIFESPAN] Loading LLM prompts...")
        logger.debug("[LIFESPAN] Configuring LLM rate limiters...")
        logger.debug("[LIFESPAN] Initializing LLM load balancer...")

    try:
        # llm_service.initialize() handles all the above stages internally
        llm_service.initialize()
        if is_main_worker:
            logger.debug("LLM Service initialized")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to initialize LLM Service: %s", e)

    # Verify Playwright installation (for PNG generation)
    if is_main_worker:
        try:
            await log_browser_diagnostics()
        except NotImplementedError:
            for line in lines_playwright_startup_critical():
                logger.error(line)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not verify Playwright installation: %s", e)

    # Start temp image cleanup task
    cleanup_task = None
    try:
        cleanup_task = asyncio.create_task(start_cleanup_scheduler(interval_hours=1))
        if is_main_worker:
            logger.debug("Temp image cleanup scheduler started")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start cleanup scheduler: %s", e)

    # Start workshop subsystem: cleanup scheduler + Lua script preload + idle monitor.
    workshop_cleanup_task, session_manager_task = await start_online_collab_subsystem_async(
        is_main_worker
    )

    worker_perf_task: Optional[asyncio.Task[None]] = None
    worker_perf_stop: Optional[asyncio.Event] = None
    try:
        from services.infrastructure.monitoring.worker_perf_heartbeat import (  # pylint: disable=import-outside-toplevel
            start_worker_perf_heartbeat,
        )

        worker_perf_task, worker_perf_stop = start_worker_perf_heartbeat()
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start admin worker perf heartbeat: %s", e)

    # Start inline recommendations cleanup scheduler (prunes stale sessions)
    try:
        asyncio.create_task(start_inline_rec_cleanup_scheduler(interval_minutes=30))
        if is_main_worker:
            logger.debug("Inline recommendations cleanup scheduler started")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start inline rec cleanup scheduler: %s", e)

    # Start database backup scheduler (daily automatic backups)
    # Backs up database daily, keeps configurable retention (default: 2 backups)
    # Uses Redis distributed lock to ensure only ONE worker runs backups across all workers
    # All workers start the scheduler, but only the lock holder executes backups
    backup_scheduler_task: Optional[asyncio.Task] = None
    try:
        backup_scheduler_task = asyncio.create_task(start_backup_scheduler())
        # Don't log here - the scheduler will log whether it acquired the lock
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == "0" or not worker_id:
            logger.warning("Failed to start backup scheduler: %s", e)

    abuseipdb_scheduler_task: Optional[asyncio.Task] = None
    try:
        abuseipdb_scheduler_task = asyncio.create_task(start_abuseipdb_blacklist_scheduler())
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == "0" or not worker_id:
            logger.warning("Failed to start AbuseIPDB blacklist scheduler: %s", e)

    # PDF auto-import removed - no longer needed for image-based viewing
    # Documents are now registered via register_image_folders.py script
    # Users manually export PDFs to images and place folders in storage/library/

    # Start process monitor (health monitoring and auto-restart for Qdrant, Celery, Redis)
    # Uses Redis distributed lock to ensure only ONE worker monitors across all workers
    # All workers start the monitor, but only the lock holder performs monitoring
    process_monitor_task: Optional[asyncio.Task] = None
    try:
        process_monitor = get_process_monitor()
        process_monitor_task = asyncio.create_task(process_monitor.start())
        if is_main_worker:
            logger.debug("Process monitor started")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start process monitor: %s", e)
        process_monitor_task = None  # Ensure it's None if initialization failed

    # Start health monitor (periodic health checks via /health/all endpoint)
    # Uses Redis distributed lock to ensure only ONE worker monitors across all workers
    # All workers start the monitor, but only the lock holder performs monitoring
    health_monitor_task: Optional[asyncio.Task] = None
    try:
        health_monitor = get_health_monitor()
        health_monitor_task = asyncio.create_task(health_monitor.start())
        if is_main_worker:
            logger.debug("Health monitor started")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start health monitor: %s", e)
        health_monitor_task = None  # Ensure it's None if initialization failed

    # Initialize Diagram Cache (Redis with database persistence)
    # Note: health_monitor_task is used in the finally block for cleanup
    _ = health_monitor_task  # Reference to prevent pylint unused variable warning
    # Starts background sync worker for dirty tracking
    try:
        get_diagram_cache()
        if is_main_worker:
            logger.debug("Diagram cache initialized")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to initialize diagram cache: %s", e)

    # Send startup notification SMS (Redis lock — once per cluster; not gated on worker id)
    try:
        await _send_startup_sms_notification_once()
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "[LIFESPAN] Failed to send startup SMS notification (non-critical): %s",
            e,
        )

    # Wait for monitor startup messages to complete before showing completion banner
    # This ensures all monitor startup logs appear before "APPLICATION LAUNCH COMPLETE"
    # Monitors are async tasks that log messages like:
    # - "[ProcessMonitor] Starting process monitor..."
    # - "[ProcessMonitor] Process monitor started"
    # - "[ProcessMonitor] Starting monitoring loop..."
    # - "[HealthMonitor] Starting health monitor..."
    # - "[HealthMonitor] Waiting X seconds..."
    # - "[HealthMonitor] Health monitor started"
    # - "[HealthMonitor] Starting monitoring loop..."
    # Give monitors time to log their initial startup messages
    if process_monitor_task is not None or health_monitor_task is not None:
        # Wait a brief moment for monitor tasks to log their initial startup messages
        # This ensures completion messages appear after all startup logging
        await asyncio.sleep(0.3)

    # Print completion messages after all startup activities are complete
    if is_main_worker:
        startup_duration = time.time() - startup_start
        logger.debug("[LIFESPAN] Startup complete, yielding to application...")
        # Print prominent launch completion notification
        # This appears after all startup activities including monitor initialization
        print()
        print("=" * 80)
        print("✓ APPLICATION LAUNCH COMPLETE")
        print("=" * 80)
        print("All services initialized and ready to accept requests.")
        print(f"Startup time: {startup_duration:.2f}s")
        print("=" * 80)
        print()

    holdings = LifespanBackgroundTasks(
        cleanup_task=cleanup_task,
        workshop_cleanup_task=workshop_cleanup_task,
        session_manager_task=session_manager_task,
        worker_perf_task=worker_perf_task,
        worker_perf_stop=worker_perf_stop,
        backup_scheduler_task=backup_scheduler_task,
        abuseipdb_scheduler_task=abuseipdb_scheduler_task,
        process_monitor_task=process_monitor_task,
        health_monitor_task=health_monitor_task,
    )

    # Yield control to application
    try:
        yield
    finally:
        await run_lifespan_shutdown(
            fastapi_app=fastapi_app,
            is_main_worker=is_main_worker,
            holdings=holdings,
        )
