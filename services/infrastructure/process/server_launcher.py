"""
Server launcher for MindGraph FastAPI application.

Orchestrates the startup sequence:
- Dependency checking
- Process management (Redis, Celery, Qdrant)
- Uvicorn server startup
- Graceful shutdown handling
"""

import os
import sys
import asyncio
import multiprocessing
import traceback
import logging

try:
    import uvicorn
except ImportError:
    uvicorn = None

try:
    from uvicorn_config import LOGGING_CONFIG
except ImportError:
    LOGGING_CONFIG = None

try:
    import main as main_module
except ImportError:
    main_module = None

from config.settings import config
from services.infrastructure.utils.dependency_checker import (
    check_redis_installed,
    check_celery_installed,
    check_qdrant_installed,
    check_postgresql_installed,
)
from services.infrastructure.process.process_manager import (
    start_redis_server,
    start_celery_worker,
    start_qdrant_server,
    start_postgresql_server,
    stop_celery_worker,
    stop_qdrant_server,
    stop_postgresql_server,
    setup_signal_handlers,
)
from services.infrastructure.utils.launch_commands import lines_http_port_in_use
from services.infrastructure.utils.port_manager import ShutdownErrorFilter
from services.infrastructure.lifecycle.startup import MINDGRAPH_LAUNCHER_PID_ENV
from services.infrastructure.process import _port_utils
from services.infrastructure.process.uvicorn_signal_diag import (
    log_uvicorn_supervisor_boot,
    patch_signal_for_uvicorn_sighup_trace,
)

logger = logging.getLogger(__name__)


def _positive_float_os_env_optional(name: str, default_positive: float) -> float | None:
    """
    Parse a positive-float env var suitable for uvicorn websocket ping knobs.

    Blanks defer to ``default_positive``; explicit ``<= 0`` maps to disabling
    the corresponding Uvicorn option (returns ``None`` so keepalive pings are off).
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default_positive
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default_positive
    if parsed <= 0:
        return None
    return parsed


def _exit_port_in_use(port: int, pid: int | None = None) -> None:
    """Print port conflict help and exit with status 1."""
    lines = lines_http_port_in_use(port, pid)
    print()
    print("[ERROR] " + lines[0])
    for line in lines[1:]:
        print(line)
    sys.exit(1)


def _ensure_http_port_free(host: str, port: int) -> None:
    """Exit if the configured HTTP listen port is already bound."""
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::", "::0") else host
    in_use, occupant_pid = _port_utils.check_port_in_use(connect_host, port)
    if in_use:
        _exit_port_in_use(port, occupant_pid)


def run_server() -> None:
    """
    Run MindGraph with Uvicorn (FastAPI async server).

    Orchestrates the complete startup sequence:
    1. Check and start dependencies (Redis, Qdrant, Celery)
    2. Setup error filtering and signal handlers
    3. Start Uvicorn server
    4. Handle graceful shutdown
    """
    if uvicorn is None:
        print("[ERROR] Uvicorn not installed. Install with: pip install uvicorn[standard]>=0.24.0")
        sys.exit(1)

    # Workers spawned by Uvicorn inherit this and skip duplicate banner / early prints
    os.environ[MINDGRAPH_LAUNCHER_PID_ENV] = str(os.getpid())

    if config is None:
        print("[ERROR] Failed to import config.settings.config")
        sys.exit(1)

    setup_signal_handlers()

    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        os.chdir(script_dir)

        os.makedirs("logs", exist_ok=True)

        host = config.host
        port = config.port
        debug = config.debug
        log_level = config.log_level.lower()

        environment = "development" if debug else "production"
        reload = debug

        default_workers = 1 if sys.platform == "win32" else min(multiprocessing.cpu_count(), 4)
        workers_str = os.getenv("UVICORN_WORKERS")
        workers = int(workers_str) if workers_str else default_workers

        # Banner is now printed in setup_early_configuration() before logging
        # Print server configuration summary
        print(f"Environment: {environment} (DEBUG={debug})")
        print(f"Host: {host}")
        print(f"Port: {port}")
        print(f"Workers: {workers}")
        print(f"Log Level: {log_level.upper()}")
        print(f"Auto-reload: {reload}")
        print("Expected Capacity: 4,000+ concurrent SSE connections")
        print("=" * 80)
        print(f"Server ready at: http://localhost:{port}")
        print(f"API Docs: http://localhost:{port}/docs")
        print()
        print("Frontend (Vue SPA):")
        print("  Development: Run 'npm run dev' in frontend/ → http://localhost:3000")
        print(f"  Production:  Run 'npm run build' in frontend/ → http://localhost:{port}")
        print("=" * 80)
        print("Press Ctrl+C to stop the server")
        print()

        _ensure_http_port_free(host, port)

        # ========================================================================
        # DEPENDENCY CHECKING AND STARTUP SEQUENCE
        # ========================================================================
        # All services (Redis, PostgreSQL, Qdrant, Celery) must be verified
        # as running before the application continues. This ensures the app
        # doesn't start in a partially-ready state.
        # ========================================================================

        # 1. Redis (REQUIRED - always checked)
        logger.debug("[REDIS] Checking Redis installation...")
        is_installed, message = check_redis_installed()
        if not is_installed:
            print("[ERROR] Redis is REQUIRED but not installed.")
            print(f"        {message}")
            print("        Application cannot start without Redis.")
            sys.exit(1)
        logger.debug("[REDIS] %s", message)
        logger.debug("[REDIS] Starting Redis server...")
        start_redis_server()  # Verifies Redis is running (exits if not ready)
        logger.debug("[REDIS] ✓ Redis is ready")

        # 2. PostgreSQL (REQUIRED if DATABASE_URL contains postgresql)
        db_url = os.getenv("DATABASE_URL", "")
        using_postgresql = "postgresql" in db_url.lower()

        if using_postgresql:
            logger.debug("[POSTGRESQL] Checking PostgreSQL installation...")
            is_installed, message = check_postgresql_installed()
            if not is_installed:
                print("[ERROR] PostgreSQL is REQUIRED but not installed.")
                print(f"        {message}")
                print("        Application cannot start without PostgreSQL.")
                sys.exit(1)
            logger.debug("[POSTGRESQL] %s", message)
            logger.debug("[POSTGRESQL] Starting PostgreSQL server...")
            postgresql_server = start_postgresql_server()  # Verifies PostgreSQL is running (exits if not ready)
            if postgresql_server:
                logger.debug("[POSTGRESQL] ✓ PostgreSQL server started as subprocess")
            else:
                logger.debug("[POSTGRESQL] ✓ PostgreSQL server is running (external or systemd service)")

        # 3. Qdrant (REQUIRED only if Knowledge Space feature is enabled)
        qdrant_server = None
        if config.FEATURE_KNOWLEDGE_SPACE:
            logger.debug("[QDRANT] Checking Qdrant installation...")
            is_installed, message = check_qdrant_installed()
            if not is_installed:
                print("[ERROR] Qdrant is REQUIRED for Knowledge Space feature but not installed.")
                print(f"        {message}")
                print("        Application cannot start without Qdrant when FEATURE_KNOWLEDGE_SPACE is enabled.")
                sys.exit(1)
            logger.debug("[QDRANT] %s", message)
            logger.debug("[QDRANT] Starting Qdrant server...")
            qdrant_server = start_qdrant_server()  # Verifies Qdrant is running (exits if not ready)
            if qdrant_server:
                logger.debug("[QDRANT] ✓ Qdrant server started as subprocess")
            else:
                logger.debug("[QDRANT] ✓ Qdrant server is running (external or systemd service)")
        else:
            logger.debug("[QDRANT] Skipping Qdrant (Knowledge Space feature is disabled)")

        # 4. Celery (REQUIRED only if Knowledge Space feature is enabled)
        celery_worker = None
        if config.FEATURE_KNOWLEDGE_SPACE:
            logger.debug("[CELERY] Checking Celery installation...")
            is_installed, message = check_celery_installed()
            if not is_installed:
                print(
                    "[ERROR] Celery is REQUIRED for Knowledge Space feature but not installed "
                    "or dependencies are missing."
                )
                print(f"        {message}")
                print("        Application cannot start without Celery when FEATURE_KNOWLEDGE_SPACE is enabled.")
                sys.exit(1)
            logger.debug("[CELERY] %s", message)
            logger.debug("[CELERY] Starting Celery worker...")
            celery_worker = start_celery_worker()  # Verifies Celery is running (exits if not ready)
            if celery_worker:
                logger.debug("[CELERY] ✓ Celery worker started successfully")
            else:
                logger.debug("[CELERY] ✓ Using existing Celery worker")
        else:
            logger.debug("[CELERY] Skipping Celery (Knowledge Space feature is disabled)")

        # All services verified and running - continue with application startup
        logger.debug("=" * 80)
        logger.debug(
            "All required services are ready: Redis%s%s",
            ", PostgreSQL" if using_postgresql else "",
            ", Qdrant, Celery" if config.FEATURE_KNOWLEDGE_SPACE else "",
        )
        logger.debug("=" * 80)
        logger.info(
            "Infrastructure ready: Redis%s%s",
            " + PostgreSQL" if using_postgresql else "",
            " + Qdrant + Celery" if config.FEATURE_KNOWLEDGE_SPACE else "",
        )

        config.print_config_summary()

        # Initialize these before try block so they're available in finally
        original_stderr = sys.stderr
        original_excepthook = sys.excepthook

        try:
            logger.debug("Testing FastAPI app import...")
            if main_module is not None:
                try:
                    logger.debug("App imported successfully: %s", main_module.app)
                except (ValueError, OSError):
                    pass
            else:
                logger.debug("main module not available at import time (will be imported by uvicorn)")

            # Setup stderr filtering AFTER logging is configured
            # This ensures logging handlers are created before we wrap sys.stderr
            sys.stderr = ShutdownErrorFilter(original_stderr)

            def custom_excepthook(exc_type, exc_value, exc_traceback) -> None:
                """Custom exception hook to suppress expected shutdown errors"""
                if exc_type == asyncio.CancelledError:
                    return
                if exc_type in (BrokenPipeError, ConnectionResetError):
                    return
                original_excepthook(exc_type, exc_value, exc_traceback)

            sys.excepthook = custom_excepthook

            logger.debug("Starting Uvicorn server...")

            worker_count = 1 if reload else workers
            worker_healthcheck = int(os.getenv("UVICORN_TIMEOUT_WORKER_HEALTHCHECK", "120"))
            logger.debug(
                "Uvicorn configuration: host=%s, port=%s, workers=%s, reload=%s",
                host,
                port,
                worker_count,
                reload,
            )
            if worker_count > 1:
                logger.info(
                    "Uvicorn multi-worker: timeout_worker_healthcheck=%ss "
                    "(UVICORN_TIMEOUT_WORKER_HEALTHCHECK). "
                    "If logs show 'Child process died' during startup, it is often a "
                    "worker healthcheck ping timeout (slow import/lifespan) rather than "
                    "a crash—increase this value. For real process exits, check dmesg/OOM.",
                    worker_healthcheck,
                )
                patch_signal_for_uvicorn_sighup_trace()
                log_uvicorn_supervisor_boot(worker_count)

            uvicorn.run(
                "main:app",
                host=host,
                port=port,
                workers=worker_count,
                reload=reload,
                log_level=log_level,
                log_config=LOGGING_CONFIG,
                use_colors=False,
                timeout_keep_alive=300,
                timeout_graceful_shutdown=5,
                timeout_worker_healthcheck=worker_healthcheck,
                access_log=False,
                limit_concurrency=1000 if not reload else None,
                ws_max_size=1024 * 1024,
                ws_ping_interval=_positive_float_os_env_optional(
                    "COLLAB_UVICORN_WS_PING_INTERVAL_SEC",
                    25.0,
                ),
                ws_ping_timeout=_positive_float_os_env_optional(
                    "COLLAB_UVICORN_WS_PING_TIMEOUT_SEC",
                    40.0,
                ),
            )
        except OSError as e:
            if (
                e.errno == 98
                or e.errno == 48
                or e.errno == 10048
                or "Address already in use" in str(e)
                or "address is already in use" in str(e).lower()
            ):
                _exit_port_in_use(port)
            else:
                raise
        except KeyboardInterrupt:
            print("\n" + "=" * 80)
            print("Shutting down gracefully...")
            if config.FEATURE_KNOWLEDGE_SPACE:
                stop_celery_worker()
                stop_qdrant_server()
            if using_postgresql:
                stop_postgresql_server()
            print("=" * 80)
        finally:
            sys.stderr = original_stderr
            sys.excepthook = original_excepthook
            if config.FEATURE_KNOWLEDGE_SPACE:
                stop_celery_worker()
                stop_qdrant_server()
            if using_postgresql:
                stop_postgresql_server()

    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("Startup interrupted by user")
        print("=" * 80)
        sys.exit(0)
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        try:
            print(f"[ERROR] Failed to start Uvicorn: {e}")
            traceback.print_exc()
        except (ValueError, OSError):
            pass
        sys.exit(1)
