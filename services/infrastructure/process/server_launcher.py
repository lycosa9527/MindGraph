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

from config.settings import config
from services.infrastructure.utils.dependency_checker import (
    check_redis_installed,
    check_celery_installed,
    check_qdrant_installed
)
from services.infrastructure.process.process_manager import (
    start_redis_server,
    start_celery_worker,
    start_qdrant_server,
    stop_celery_worker,
    stop_qdrant_server,
    setup_signal_handlers
)
from services.infrastructure.utils.port_manager import ShutdownErrorFilter

logger = logging.getLogger(__name__)


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

        environment = 'development' if debug else 'production'
        reload = debug

        default_workers = 1 if sys.platform == 'win32' else min(multiprocessing.cpu_count(), 4)
        workers_str = os.getenv('UVICORN_WORKERS')
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

        print("[REDIS] Checking Redis installation...")
        is_installed, message = check_redis_installed()
        if not is_installed:
            print("[ERROR] Redis is REQUIRED but not installed.")
            print(f"        {message}")
            print("        Application cannot start without Redis.")
            sys.exit(1)
        print(f"[REDIS] {message}")
        print("[REDIS] Starting Redis server...")
        start_redis_server()
        print()

        config.print_config_summary()

        print("[QDRANT] Checking Qdrant installation...")
        is_installed, message = check_qdrant_installed()
        if not is_installed:
            print("[ERROR] Qdrant is REQUIRED but not installed.")
            print(f"        {message}")
            print("        Application cannot start without Qdrant.")
            sys.exit(1)
        print(f"[QDRANT] {message}")
        print("[QDRANT] Starting Qdrant server...")
        qdrant_server = start_qdrant_server()
        if qdrant_server:
            print("[QDRANT] Qdrant server started as subprocess")
        else:
            print("[QDRANT] Qdrant server is running (external or systemd service)")
        print()

        print("[CELERY] Checking Celery installation...")
        is_installed, message = check_celery_installed()
        if not is_installed:
            print("[ERROR] Celery is REQUIRED but not installed or dependencies are missing.")
            print(f"        {message}")
            print("        Application cannot start without Celery.")
            sys.exit(1)
        print(f"[CELERY] {message}")
        print("[CELERY] Starting Celery worker...")
        celery_worker = start_celery_worker()
        if celery_worker:
            print("[CELERY] Celery worker started successfully")
        else:
            print("[CELERY] Using existing Celery worker")
        print()

        try:
            print("[DEBUG] Testing FastAPI app import...")
            try:
                import main as main_module
                try:
                    print(f"[DEBUG] App imported successfully: {main_module.app}")
                except (ValueError, OSError):
                    pass
            except Exception as e:
                try:
                    print(f"[ERROR] Failed to import app: {e}")
                    traceback.print_exc()
                except (ValueError, OSError):
                    pass
                sys.exit(1)

            # Setup stderr filtering AFTER logging is configured
            # This ensures logging handlers are created before we wrap sys.stderr
            original_stderr = sys.stderr
            sys.stderr = ShutdownErrorFilter(original_stderr)

            original_excepthook = sys.excepthook

            def custom_excepthook(exc_type, exc_value, exc_traceback) -> None:
                """Custom exception hook to suppress expected shutdown errors"""
                if exc_type == asyncio.CancelledError:
                    return
                if exc_type in (BrokenPipeError, ConnectionResetError):
                    return
                original_excepthook(exc_type, exc_value, exc_traceback)

            sys.excepthook = custom_excepthook

            print("[DEBUG] Starting Uvicorn server...")
            sys.stdout.flush()

            worker_count = 1 if reload else workers
            print(f"[DEBUG] Uvicorn configuration: host={host}, port={port}, workers={worker_count}, reload={reload}")
            sys.stdout.flush()

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
                access_log=False,
                limit_concurrency=1000 if not reload else None,
            )
        except OSError as e:
            if e.errno == 98 or "Address already in use" in str(e) or "address is already in use" in str(e).lower():
                print(f"\n[ERROR] Port {port} is already in use!")
                print(f"        Another process is using port {port}.")
                print("\n        Solutions:")
                print(f"        1. Stop the process using port {port}:")
                if sys.platform == 'win32':
                    print(f"           netstat -ano | findstr :{port}")
                    print("           taskkill /PID <PID> /F")
                else:
                    print(f"           lsof -ti:{port} | xargs kill -9")
                    print(f"           or: sudo fuser -k {port}/tcp")
                print("        2. Use a different port:")
                print("           Set PORT=<different_port> in .env")
                print("           Example: PORT=9528")
                print("        3. Check if another MindGraph instance is running")
                sys.exit(1)
            else:
                raise
        except KeyboardInterrupt:
            print("\n" + "=" * 80)
            print("Shutting down gracefully...")
            stop_celery_worker()
            stop_qdrant_server()
            print("=" * 80)
        finally:
            sys.stderr = original_stderr
            sys.excepthook = original_excepthook
            stop_celery_worker()
            stop_qdrant_server()

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
