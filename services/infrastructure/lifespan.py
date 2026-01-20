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

from fastapi import FastAPI

from clients.llm import close_httpx_clients
from config.celery import CeleryStartupError, init_celery_worker_check
from config.database import close_db, init_db
from services.auth.sms_middleware import shutdown_sms_service
from services.infrastructure.recovery_startup import check_database_on_startup
from services.infrastructure.startup import _handle_shutdown_signal
from services.llm.qdrant_service import QdrantStartupError, init_qdrant_sync
from services.redis.redis_client import RedisStartupError, close_redis_sync, init_redis_sync
from services.utils.backup_scheduler import start_backup_scheduler
from services.utils.temp_image_cleaner import start_cleanup_scheduler
from utils.auth import display_demo_info
from utils.dependency_checker import DependencyError, check_system_dependencies

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Handles application initialization and cleanup.
    """
    # Startup
    logger.info("[LIFESPAN] Starting lifespan initialization...")
    fastapi_app.state.start_time = time.time()
    fastapi_app.state.is_shutting_down = False

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    logger.info("[LIFESPAN] Signal handlers registered")

    # Only log startup banner from first worker to avoid repetition
    worker_id = os.getenv('UVICORN_WORKER_ID', '0')
    if worker_id == '0' or not worker_id:
        logger.info("=" * 80)
        logger.info("FastAPI Application Starting")
        logger.info("=" * 80)

    # Initialize Redis (REQUIRED for caching, rate limiting, sessions)
    # Application will exit if Redis is not available
    logger.info("[LIFESPAN] Initializing Redis...")
    try:
        init_redis_sync()
        if worker_id == '0' or not worker_id:
            logger.info("Redis initialized successfully")
    except RedisStartupError:
        # Error message already logged by init_redis_sync with instructions
        # Exit cleanly without traceback using os._exit to prevent Starlette
        # from catching and logging the full stack trace
        logger.error("Application startup failed. Exiting.")
        os._exit(1)  # pylint: disable=protected-access

    # Initialize Qdrant (REQUIRED for Knowledge Space vector storage)
    # Application will exit if Qdrant is not available
    logger.info("[LIFESPAN] Initializing Qdrant...")
    try:
        init_qdrant_sync()
        if worker_id == '0' or not worker_id:
            logger.info("Qdrant initialized successfully")
    except QdrantStartupError:
        # Error message already logged by init_qdrant_sync with instructions
        # Exit cleanly without traceback using os._exit to prevent Starlette
        # from catching and logging the full stack trace
        logger.error("Application startup failed. Exiting.")
        os._exit(1)  # pylint: disable=protected-access

    # Check Celery worker availability (REQUIRED for background task processing)
    # Application will exit if Celery worker is not available
    logger.info("[LIFESPAN] Checking Celery worker availability...")
    try:
        init_celery_worker_check()
        if worker_id == '0' or not worker_id:
            logger.info("Celery worker is available")
    except CeleryStartupError:
        # Error message already logged by init_celery_worker_check with instructions
        # Exit cleanly without traceback using os._exit to prevent Starlette
        # from catching and logging the full stack trace
        logger.error("Application startup failed. Exiting.")
        os._exit(1)  # pylint: disable=protected-access

    # Check system dependencies for Knowledge Space feature (Tesseract OCR)
    # Application will exit if required dependencies are missing
    logger.info("[LIFESPAN] Checking system dependencies...")
    if worker_id == '0' or not worker_id:
        try:
            if not check_system_dependencies(exit_on_error=True):
                # check_system_dependencies already exits, but this is a safety check
                logger.error("System dependency check failed. Exiting.")
                os._exit(1)  # pylint: disable=protected-access
            logger.info("System dependencies check passed")
        except DependencyError as e:
            logger.error("Dependency check failed: %s", e)
            os._exit(1)  # pylint: disable=protected-access
        except Exception as e:  # pylint: disable=broad-except
            # Log but don't exit on unexpected errors during dependency check
            # This allows the app to start even if dependency check has issues
            logger.warning("Error during dependency check (non-fatal): %s", e)

    # Note: Legacy JavaScript cache removed in v5.0.0 (Vue migration)
    # Frontend assets are now served from frontend/dist/ via Vue SPA handler

    # Initialize Database with corruption detection and recovery
    logger.info("[LIFESPAN] Initializing database...")
    try:
        # Check database integrity on startup (uses Redis lock to ensure only one worker checks)
        # Note: Removed worker_id check - Redis lock handles multi-worker coordination
        # If corruption is detected, interactive recovery wizard is triggered
        logger.info("[LIFESPAN] Checking database integrity...")
        if not check_database_on_startup():
            logger.critical("Database recovery failed or was aborted. Shutting down.")
            raise SystemExit(1)
        # Only log from first worker to avoid duplicate messages
        if worker_id == '0' or not worker_id:
            logger.info("Database integrity verified")

        logger.info("[LIFESPAN] Initializing database connection...")
        init_db()
        if worker_id == '0' or not worker_id:
            logger.info("Database initialized successfully")
            # Display demo info if in demo mode
            display_demo_info()

        # Load cache from SQLite and IP geolocation database in parallel to save startup time
        # Note: Both use Redis lock/distributed coordination to ensure only one worker loads
        logger.info("[LIFESPAN] Loading cache and IP database...")
        
        # Check if user auth cache preloading is enabled
        preload_auth_cache = os.getenv("PRELOAD_USER_AUTH_CACHE", "true").lower() in ("1", "true", "yes")
        
        def load_user_cache():
            """Load user cache from SQLite (runs in thread pool)."""
            if not preload_auth_cache:
                if worker_id == '0' or not worker_id:
                    logger.info("[CacheLoader] User auth cache preloading skipped (PRELOAD_USER_AUTH_CACHE disabled)")
                return True  # Return True to indicate skip was intentional
            
            try:
                # pylint: disable=import-outside-toplevel
                from services.redis.redis_cache_loader import reload_cache_from_sqlite
                logger.debug("[CacheLoader] Starting cache loading process...")
                result = reload_cache_from_sqlite()
                logger.debug("[CacheLoader] Cache loading process completed with result: %s", result)
                return result
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Failed to load cache from SQLite: %s", e, exc_info=True)
                return False

        def load_ip_database():
            """Initialize IP geolocation database (runs in thread pool)."""
            try:
                # pylint: disable=import-outside-toplevel
                from services.auth.ip_geolocation import get_geolocation_service
                geolocation_service = get_geolocation_service()
                if geolocation_service.is_ready():
                    if worker_id == '0' or not worker_id:
                        logger.info("IP Geolocation Service initialized successfully")
                    return True
                else:
                    if worker_id == '0' or not worker_id:
                        logger.warning(
                            "IP Geolocation database not available "
                            "(database file missing or failed to load)"
                        )
                    return False
            except Exception as e:  # pylint: disable=broad-except
                if worker_id == '0' or not worker_id:
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
            logger.error("Failed to load cache from SQLite: %s", cache_result, exc_info=True)
        elif cache_result:
            # Cache loading completed (either by this worker or another worker via lock)
            # The actual loading logs come from reload_cache_from_sqlite() itself
            if preload_auth_cache and (worker_id == '0' or not worker_id):
                logger.info("[CacheLoader] User cache loading completed successfully")
        else:
            # cache_result is False - cache loading failed
            if preload_auth_cache:
                logger.warning("[CacheLoader] Cache loading returned False - cache may not be preloaded")
                if worker_id == '0' or not worker_id:
                    logger.warning("[CacheLoader] WARNING: User authentication data may not be preloaded into Redis cache")

        if isinstance(ip_db_result, Exception):
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to initialize IP Geolocation Service: %s", ip_db_result)
        elif not ip_db_result:
            # Already logged in load_ip_database
            pass

        # Load IP whitelist from env var into Redis (uses Redis lock to ensure only one worker loads)
        # Note: Removed worker_id check - Redis lock handles multi-worker coordination
        try:
            # pylint: disable=import-outside-toplevel
            from services.redis.redis_bayi_whitelist import get_bayi_whitelist
            from utils.auth import AUTH_MODE
            if AUTH_MODE == "bayi":
                whitelist = get_bayi_whitelist()
                count = whitelist.load_from_env()
                # Only log from first worker to avoid duplicate messages
                if count > 0 and (worker_id == '0' or not worker_id):
                    logger.info("Loaded %s IP(s) from BAYI_IP_WHITELIST into Redis", count)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Failed to load IP whitelist into Redis: %s", e)
            # Don't fail startup - system can work with in-memory whitelist
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.error("Failed to initialize database: %s", e)

    # Initialize LLM Service
    try:
        # pylint: disable=import-outside-toplevel
        from services.llm import llm_service
        llm_service.initialize()
        if worker_id == '0' or not worker_id:
            logger.info("LLM Service initialized")
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to initialize LLM Service: %s", e)

    # Verify Playwright installation (for PNG generation)
    if worker_id == '0' or not worker_id:
        try:
            # pylint: disable=import-outside-toplevel
            from services.infrastructure.browser import log_browser_diagnostics
            await log_browser_diagnostics()
        except NotImplementedError:
            logger.error("=" * 80)
            logger.error("CRITICAL: Playwright browsers are not installed!")
            logger.error("PNG generation endpoints (/api/generate_png, /api/generate_dingtalk) will fail.")
            logger.error("To fix: conda activate python3.13 && playwright install chromium")
            logger.error("=" * 80)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not verify Playwright installation: %s", e)

    # Start temp image cleanup task
    cleanup_task = None
    try:
        cleanup_task = asyncio.create_task(start_cleanup_scheduler(interval_hours=1))
        if worker_id == '0' or not worker_id:
            logger.info("Temp image cleanup scheduler started")
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to start cleanup scheduler: %s", e)

    # Start WAL checkpoint scheduler (checkpoints SQLite WAL every 5 minutes)
    # This is critical for database safety, especially when using kill -9 (SIGKILL)
    # which bypasses graceful shutdown. Periodic checkpointing ensures WAL file
    # doesn't grow too large and reduces corruption risk.
    wal_checkpoint_task = None
    try:
        # pylint: disable=import-outside-toplevel
        from config.database import start_wal_checkpoint_scheduler
        wal_checkpoint_task = asyncio.create_task(start_wal_checkpoint_scheduler(interval_minutes=5))
        if worker_id == '0' or not worker_id:
            logger.info("WAL checkpoint scheduler started (every 5 min)")
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to start WAL checkpoint scheduler: %s", e)

    # Start database backup scheduler (daily automatic backups)
    # Backs up SQLite database daily, keeps configurable retention (default: 2 backups)
    # Uses Redis distributed lock to ensure only ONE worker runs backups across all workers
    # All workers start the scheduler, but only the lock holder executes backups
    backup_scheduler_task = None
    try:
        backup_scheduler_task = asyncio.create_task(start_backup_scheduler())
        # Don't log here - the scheduler will log whether it acquired the lock
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to start backup scheduler: %s", e)

    # Initialize Diagram Cache (Redis with SQLite persistence)
    # Starts background sync worker for dirty tracking
    try:
        # pylint: disable=import-outside-toplevel
        from services.redis.redis_diagram_cache import get_diagram_cache
        diagram_cache = get_diagram_cache()
        if worker_id == '0' or not worker_id:
            logger.info("Diagram cache initialized")
    except Exception as e:  # pylint: disable=broad-except
        if worker_id == '0' or not worker_id:
            logger.warning("Failed to initialize diagram cache: %s", e)

    # Yield control to application
    logger.info("[LIFESPAN] Startup complete, yielding to application...")
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
            if worker_id == '0' or not worker_id:
                logger.info("Temp image cleanup scheduler stopped")

        # Stop WAL checkpoint scheduler
        if wal_checkpoint_task:
            wal_checkpoint_task.cancel()
            try:
                await wal_checkpoint_task
            except asyncio.CancelledError:
                pass
            if worker_id == '0' or not worker_id:
                logger.info("WAL checkpoint scheduler stopped")

        # Stop backup scheduler (runs on all workers, but only lock holder executes)
        if backup_scheduler_task:
            backup_scheduler_task.cancel()
            try:
                await backup_scheduler_task
            except asyncio.CancelledError:
                pass
            # Only log on worker that was the lock holder (scheduler handles this internally)

        # Cleanup LLM Service
        try:
            # pylint: disable=import-outside-toplevel
            from services.llm import llm_service
            llm_service.cleanup()
            if worker_id == '0' or not worker_id:
                logger.info("LLM Service cleaned up")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to cleanup LLM Service: %s", e)

        # Flush update notification dismiss buffer
        try:
            # pylint: disable=import-outside-toplevel
            from services.utils.update_notifier import update_notifier
            update_notifier.shutdown()
            if worker_id == '0' or not worker_id:
                logger.info("Update notifier flushed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to flush update notifier: %s", e)

        # Flush TokenTracker before closing database
        try:
            # pylint: disable=import-outside-toplevel
            from services.redis.redis_token_buffer import get_token_tracker
            token_tracker = get_token_tracker()
            await token_tracker.flush()
            if worker_id == '0' or not worker_id:
                logger.info("TokenTracker flushed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to flush TokenTracker: %s", e)

        # Flush Diagram Cache before closing database
        try:
            # pylint: disable=import-outside-toplevel
            from services.redis.redis_diagram_cache import get_diagram_cache
            diagram_cache = get_diagram_cache()
            await diagram_cache.flush()
            if worker_id == '0' or not worker_id:
                logger.info("Diagram cache flushed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to flush diagram cache: %s", e)

        # Shutdown SMS service (close httpx async client)
        try:
            await shutdown_sms_service()
            if worker_id == '0' or not worker_id:
                logger.info("SMS service shut down")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to shutdown SMS service: %s", e)

        # Close httpx clients (LLM HTTP/2 connection pools)
        try:
            await close_httpx_clients()
            if worker_id == '0' or not worker_id:
                logger.info("LLM httpx clients closed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to close httpx clients: %s", e)

        # Cleanup Database
        try:
            close_db()
            if worker_id == '0' or not worker_id:
                logger.info("Database connections closed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to close database: %s", e)

        # Close Redis connection
        try:
            close_redis_sync()
            if worker_id == '0' or not worker_id:
                logger.info("Redis connection closed")
        except Exception as e:  # pylint: disable=broad-except
            if worker_id == '0' or not worker_id:
                logger.warning("Failed to close Redis: %s", e)

        # Don't try to cancel tasks - let uvicorn handle the shutdown
        # This prevents CancelledError exceptions during multiprocess shutdown
