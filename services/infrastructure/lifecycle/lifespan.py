"""
Lifespan management for MindGraph application.

Handles FastAPI application startup and shutdown lifecycle:
- Redis initialization
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

from clients.llm import close_httpx_clients
from config.celery import CeleryStartupError, init_celery_worker_check
from config.database import close_db, init_db
from config.settings import config
from services.auth.ip_geolocation import get_geolocation_service
from services.auth.sms_middleware import get_sms_middleware, shutdown_sms_service
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.monitoring.health_monitor import get_health_monitor
from services.infrastructure.monitoring.process_monitor import get_process_monitor
from services.infrastructure.recovery.recovery_startup import check_database_on_startup
from services.infrastructure.lifecycle.startup import (
    _handle_shutdown_signal
)
from services.infrastructure.utils.browser import log_browser_diagnostics
from services.llm import llm_service
from services.llm.qdrant_service import QdrantStartupError, init_qdrant_sync
from services.redis.redis_bayi_whitelist import get_bayi_whitelist
from services.redis.cache.redis_cache_loader import reload_cache_from_database
from services.redis.redis_client import RedisStartupError, close_redis_sync, init_redis_sync
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.redis.redis_token_buffer import get_token_tracker
from services.utils.backup_scheduler import start_backup_scheduler
from services.utils.temp_image_cleaner import start_cleanup_scheduler
from services.workshop import start_workshop_cleanup_scheduler
# PDF auto-import removed - no longer needed for image-based viewing
from services.utils.update_notifier import update_notifier
from utils.auth import AUTH_MODE, display_demo_info
from utils.auth.config import ADMIN_PHONES
from utils.dependency_checker import DependencyError, check_system_dependencies

logger = logging.getLogger(__name__)




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

    # Only log startup messages from first worker to avoid repetition
    worker_id = os.getenv('UVICORN_WORKER_ID', '0')
    is_main_worker = (worker_id == '0' or not worker_id)

    if is_main_worker:
        logger.debug("=" * 80)
        logger.debug("FastAPI Application Starting")
        logger.debug("=" * 80)
        logger.debug("[LIFESPAN] Starting lifespan initialization...")
        logger.debug("[LIFESPAN] Signal handlers registered")

    # Initialize Redis (REQUIRED for caching, rate limiting, sessions)
    # Application will exit if Redis is not available
    if is_main_worker:
        logger.debug("[LIFESPAN] Initializing Redis...")
    try:
        init_redis_sync()
        if is_main_worker:
            logger.debug("Redis initialized successfully")
    except RedisStartupError as e:
        # Error message already logged by init_redis_sync with instructions
        # Send critical alert before exiting
        try:
            CriticalAlertService.send_startup_failure_alert_sync(
                component="Redis",
                error_message=f"Redis startup failed: {str(e)}",
                details=(
                    "Application cannot start without Redis. "
                    "Check Redis connection and configuration."
                )
            )
        except Exception as alert_error:  # pylint: disable=broad-except
            logger.error("Failed to send startup failure alert: %s", alert_error)
        logger.error("Application startup failed. Exiting.")
        os._exit(1)  # pylint: disable=protected-access

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
                    )
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
                    )
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
                details=(
                    "Required system dependencies are missing. "
                    "Check Tesseract OCR installation."
                )
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

    # Initialize Database with corruption detection and recovery
    if is_main_worker:
        logger.debug("[LIFESPAN] Initializing database...")
    try:
        # Check database integrity on startup (uses Redis lock to ensure only one worker checks)
        # Note: Removed worker_id check - Redis lock handles multi-worker coordination
        # If corruption is detected, interactive recovery wizard is triggered
        if is_main_worker:
            logger.debug("[LIFESPAN] Checking database integrity...")
        if not check_database_on_startup():
            if is_main_worker:
                logger.critical("Database recovery failed or was aborted. Shutting down.")
            try:
                CriticalAlertService.send_startup_failure_alert_sync(
                    component="Database",
                    error_message="Database recovery failed or was aborted",
                    details=(
                        "Database integrity check failed and recovery was not successful. "
                        "Manual intervention required."
                    )
                )
            except Exception as alert_error:  # pylint: disable=broad-except
                if is_main_worker:
                    logger.error("Failed to send startup failure alert: %s", alert_error)
            raise SystemExit(1)
        # Initialize database connection
        # Only log from first worker to avoid duplicate messages
        if is_main_worker:
            logger.debug("Database integrity verified")
            logger.debug("[LIFESPAN] Connecting to PostgreSQL database...")
            logger.debug("[LIFESPAN] Verifying PostgreSQL tables...")
            logger.debug("[LIFESPAN] Running database migrations...")

        # init_db() handles connection, table creation, and migrations
        init_db()
        if is_main_worker:
            logger.debug("Database initialized successfully")
            # Display demo info if in demo mode
            display_demo_info()

        # Load cache from database and IP geolocation database in parallel
        # Note: Both use Redis lock/distributed coordination to ensure only one worker loads
        if is_main_worker:
            logger.debug("[LIFESPAN] Loading cache and IP database...")

        # Check if user auth cache preloading is enabled
        preload_auth_cache = os.getenv("PRELOAD_USER_AUTH_CACHE", "true").lower() in ("1", "true", "yes")

        def load_user_cache():
            """Load user cache from database (runs in thread pool)."""
            if not preload_auth_cache:
                if is_main_worker:
                    logger.info(
                        "[CacheLoader] User auth cache preloading skipped "
                        "(PRELOAD_USER_AUTH_CACHE disabled)"
                    )
                return True  # Return True to indicate skip was intentional

            try:
                # reload_cache_from_database() handles Redis lock internally
                # No need for pre-check - let the atomic lock handle coordination
                # The Redis SETNX operation is atomic, so the lock acquisition prevents race conditions
                result = reload_cache_from_database()
                return result
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Failed to load cache from database: %s", e, exc_info=True)
                return False

        def load_ip_database():
            """Initialize IP geolocation database (runs in thread pool)."""
            try:
                geolocation_service = get_geolocation_service()
                if geolocation_service.is_ready():
                    if is_main_worker:
                        logger.info("IP Geolocation Service initialized successfully")
                    return True
                else:
                    if is_main_worker:
                        logger.warning(
                            "IP Geolocation database not available "
                            "(database file missing or failed to load)"
                        )
                    return False
            except Exception as e:  # pylint: disable=broad-except
                if is_main_worker:
                    logger.warning("Failed to initialize IP Geolocation Service: %s", e)
                return False

        # Run both operations in parallel using thread pool
        cache_result, ip_db_result = await asyncio.gather(
            asyncio.to_thread(load_user_cache),
            asyncio.to_thread(load_ip_database),
            return_exceptions=True
        )


        # Handle results
        if isinstance(cache_result, Exception):
            if is_main_worker:
                logger.error("Failed to load cache from database: %s", cache_result, exc_info=True)
        elif cache_result:
            # Cache loading completed (either by this worker or another worker via lock)
            # The actual loading logs come from reload_cache_from_database() itself
            if preload_auth_cache and is_main_worker:
                logger.info("[CacheLoader] User cache loading completed successfully")
        else:
            # cache_result is False - cache loading failed
            if preload_auth_cache:
                if is_main_worker:
                    logger.warning(
                        "[CacheLoader] Cache loading returned False - cache may not be preloaded"
                    )
                    logger.warning(
                        "[CacheLoader] WARNING: User authentication data may not be "
                        "preloaded into Redis cache"
                    )

        if isinstance(ip_db_result, Exception):
            if is_main_worker:
                logger.warning("Failed to initialize IP Geolocation Service: %s", ip_db_result)
        elif not ip_db_result:
            # Already logged in load_ip_database
            pass

        # Load IP whitelist from env var into Redis (uses Redis lock to ensure only one worker loads)
        # Note: Removed worker_id check - Redis lock handles multi-worker coordination
        try:
            if AUTH_MODE == "bayi":
                whitelist = get_bayi_whitelist()
                count = whitelist.load_from_env()
                # Only log from first worker to avoid duplicate messages
                if count > 0 and is_main_worker:
                    logger.info("Loaded %s IP(s) from BAYI_IP_WHITELIST into Redis", count)
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to load IP whitelist into Redis: %s", e)
            # Don't fail startup - system can work with in-memory whitelist
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.error("Failed to initialize database: %s", e)

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
            logger.error("=" * 80)
            logger.error("CRITICAL: Playwright browsers are not installed!")
            logger.error(
                "PNG generation endpoints (/api/generate_png, /api/generate_dingtalk) will fail."
            )
            logger.error("To fix: conda activate python3.13 && playwright install chromium")
            logger.error("=" * 80)
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

    # Start workshop cleanup scheduler (removes expired workshop codes from database)
    workshop_cleanup_task = None
    try:
        workshop_cleanup_task = asyncio.create_task(
            start_workshop_cleanup_scheduler(interval_hours=6)
        )
        if is_main_worker:
            logger.debug("Workshop cleanup scheduler started")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to start workshop cleanup scheduler: %s", e)

    # Start database backup scheduler (daily automatic backups)
    # Backs up database daily, keeps configurable retention (default: 2 backups)
    # Uses Redis distributed lock to ensure only ONE worker runs backups across all workers
    # All workers start the scheduler, but only the lock holder executes backups
    backup_scheduler_task: Optional[asyncio.Task] = None
    try:
        backup_scheduler_task = asyncio.create_task(start_backup_scheduler())
        # Don't log here - the scheduler will log whether it acquired the lock
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to start backup scheduler: %s", e)

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
        diagram_cache = get_diagram_cache()
        if is_main_worker:
            logger.debug("Diagram cache initialized")
    except Exception as e:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to initialize diagram cache: %s", e)

    # Send startup notification SMS to admin phones
    if is_main_worker:
        try:
            # Skip SMS notifications in debug mode (frequent restarts during development)
            is_debug_mode = os.getenv("DEBUG", "").lower() == "true"
            if is_debug_mode:
                logger.debug("[LIFESPAN] Startup SMS notification skipped (DEBUG mode enabled)")
            else:
                # Check if startup SMS notification is enabled
                sms_startup_enabled = os.getenv(
                    "SMS_STARTUP_NOTIFICATION_ENABLED", "true"
                ).lower() in ("true", "1", "yes")
                if not sms_startup_enabled:
                    logger.debug(
                        "[LIFESPAN] Startup SMS notification disabled "
                        "(SMS_STARTUP_NOTIFICATION_ENABLED=false)"
                    )
                else:
                    sms_middleware = get_sms_middleware()
                    if sms_middleware.is_available:
                        admin_phones = [phone.strip() for phone in ADMIN_PHONES if phone.strip()]
                        if admin_phones:
                            # Get startup notification template ID from environment variable
                            startup_template_id = os.getenv("TENCENT_SMS_TEMPLATE_STARTUP", "").strip()
                            if not startup_template_id:
                                logger.warning(
                                    "[LIFESPAN] TENCENT_SMS_TEMPLATE_STARTUP not configured, "
                                    "skipping startup SMS notification"
                                )
                            else:
                                # Message: "MindGraph已在主服务器启动，短信通知系统启用成功。"
                                success, message = await sms_middleware.send_notification(
                                    phones=admin_phones,
                                    template_id=startup_template_id,
                                    template_params=[],  # Template has no parameters
                                    lang="zh"
                                )
                                if success:
                                    logger.info("[LIFESPAN] Startup SMS notification sent successfully: %s", message)
                                else:
                                    logger.warning("[LIFESPAN] Failed to send startup SMS notification: %s", message)
                        else:
                            logger.debug("[LIFESPAN] No admin phones configured, skipping startup SMS notification")
                    else:
                        logger.debug("[LIFESPAN] SMS service not available, skipping startup SMS notification")
        except Exception as e:  # pylint: disable=broad-except
            # Don't fail startup if SMS notification fails
            logger.warning("[LIFESPAN] Failed to send startup SMS notification (non-critical): %s", e)

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

    # Yield control to application
    try:
        yield
    finally:
        # Shutdown - clean up resources gracefully
        fastapi_app.state.is_shutting_down = True

        # Give ongoing requests a brief moment to complete
        await asyncio.sleep(0.1)

        # Stop cleanup tasks
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            if is_main_worker:
                logger.debug("Temp image cleanup scheduler stopped")

        # Stop workshop cleanup scheduler
        if workshop_cleanup_task:
            workshop_cleanup_task.cancel()
            try:
                await workshop_cleanup_task
            except asyncio.CancelledError:
                pass
            if is_main_worker:
                logger.debug("Workshop cleanup scheduler stopped")

        # Stop backup scheduler (runs on all workers, but only lock holder executes)
        if backup_scheduler_task:
            backup_scheduler_task.cancel()
            try:
                await backup_scheduler_task
            except asyncio.CancelledError:
                pass
            # Only log on worker that was the lock holder (scheduler handles this internally)

        # Library auto-import scheduler no longer runs (removed periodic checking)

        # Stop process monitor
        if process_monitor_task:
            try:
                process_monitor = get_process_monitor()
                await process_monitor.stop()
            except Exception as e:  # pylint: disable=broad-except
                if is_main_worker:
                    logger.warning("Failed to stop process monitor: %s", e)
            process_monitor_task.cancel()
            try:
                await process_monitor_task
            except asyncio.CancelledError:
                pass
            if is_main_worker:
                logger.info("Process monitor stopped")

        # Stop health monitor
        if health_monitor_task:
            try:
                health_monitor = get_health_monitor()
                await health_monitor.stop()
            except Exception as e:  # pylint: disable=broad-except
                if is_main_worker:
                    logger.warning("Failed to stop health monitor: %s", e)
            health_monitor_task.cancel()
            try:
                await health_monitor_task
            except asyncio.CancelledError:
                pass
            if is_main_worker:
                logger.info("Health monitor stopped")

        # Cleanup LLM Service
        try:
            llm_service.cleanup()
            if is_main_worker:
                logger.info("LLM Service cleaned up")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to cleanup LLM Service: %s", e)

        # Flush update notification dismiss buffer
        try:
            update_notifier.shutdown()
            if is_main_worker:
                logger.info("Update notifier flushed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to flush update notifier: %s", e)

        # Flush TokenTracker before closing database
        try:
            token_tracker = get_token_tracker()
            await token_tracker.flush()
            if is_main_worker:
                logger.info("TokenTracker flushed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to flush TokenTracker: %s", e)

        # Flush Diagram Cache before closing database
        try:
            diagram_cache = get_diagram_cache()
            await diagram_cache.flush()
            if is_main_worker:
                logger.info("Diagram cache flushed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to flush diagram cache: %s", e)

        # Shutdown SMS service (close httpx async client)
        try:
            await shutdown_sms_service()
            if is_main_worker:
                logger.info("SMS service shut down")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to shutdown SMS service: %s", e)

        # Close httpx clients (LLM HTTP/2 connection pools)
        try:
            await close_httpx_clients()
            if is_main_worker:
                logger.info("LLM httpx clients closed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to close httpx clients: %s", e)

        # Cleanup Database
        try:
            close_db()
            if is_main_worker:
                logger.info("Database connections closed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to close database: %s", e)

        # Close Redis connection
        try:
            close_redis_sync()
            if is_main_worker:
                logger.info("Redis connection closed")
        except Exception as e:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to close Redis: %s", e)

        # Don't try to cancel tasks - let uvicorn handle the shutdown
        # This prevents CancelledError exceptions during multiprocess shutdown
