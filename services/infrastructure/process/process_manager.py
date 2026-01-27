"""
Process management utilities for MindGraph application.

Handles starting and stopping required services:
- Redis server (via systemctl or manual)
- Celery worker (subprocess)
- Qdrant server (subprocess or systemd service)
- PostgreSQL server (subprocess or systemd service)
- Signal handlers for graceful shutdown
"""

import os
import sys
import signal
from typing import Optional, Any

from services.infrastructure.process._redis_manager import start_redis_server as _start_redis_server
from services.infrastructure.process._celery_manager import (
    start_celery_worker as _start_celery_worker,
    stop_celery_worker as _stop_celery_worker
)
from services.infrastructure.process._qdrant_manager import (
    start_qdrant_server as _start_qdrant_server,
    stop_qdrant_server as _stop_qdrant_server
)
from services.infrastructure.process._postgresql_manager import (
    start_postgresql_server as _start_postgresql_server,
    stop_postgresql_server as _stop_postgresql_server
)


class ServerState:
    """Module-level state for server processes"""
    celery_worker_process: Optional[Any] = None
    celery_stdout_file: Optional[Any] = None
    celery_stderr_file: Optional[Any] = None
    qdrant_process: Optional[Any] = None
    postgresql_process: Optional[Any] = None
    redis_started_by_app: bool = False
    shutdown_in_progress: bool = False


def start_redis_server() -> None:
    """
    Start Redis server if not already running (REQUIRED).

    Assumes Redis installation has been verified. Checks if Redis is running,
    and if not, attempts to start it via systemctl. Application will exit if
    Redis cannot be started.
    """
    _start_redis_server(ServerState)


def start_celery_worker() -> Optional[Any]:
    """
    Start Celery worker as a subprocess (REQUIRED).

    Assumes Celery installation and dependencies have been verified. Checks
    if a worker is already running before starting a new one. Application will
    exit if Celery cannot be started.

    Returns:
        Optional[subprocess.Popen[bytes]]: Celery worker process or None if using existing
    """
    return _start_celery_worker(ServerState)


def stop_celery_worker() -> None:
    """Stop the Celery worker subprocess"""
    _stop_celery_worker(ServerState)


def start_qdrant_server() -> Optional[Any]:
    """
    Start Qdrant server as a subprocess if not already running (REQUIRED).

    Assumes Qdrant installation has been verified. Checks if Qdrant is running,
    and if not, attempts to start it. Application will exit if Qdrant cannot be started.

    Returns:
        Optional[subprocess.Popen[bytes]]: Qdrant process or None if using existing
    """
    return _start_qdrant_server(ServerState)


def stop_qdrant_server() -> None:
    """Stop the Qdrant server subprocess"""
    _stop_qdrant_server(ServerState)


def start_postgresql_server() -> Optional[Any]:
    """
    Start PostgreSQL server as a subprocess if not already running (REQUIRED).

    Assumes PostgreSQL installation has been verified. Checks if PostgreSQL is running,
    and if not, attempts to start it. Application will exit if PostgreSQL cannot be started.

    Returns:
        Optional[subprocess.Popen[bytes]]: PostgreSQL process or None if using existing
    """
    return _start_postgresql_server(ServerState)


def stop_postgresql_server() -> None:
    """Stop the PostgreSQL server subprocess"""
    _stop_postgresql_server(ServerState)


def setup_signal_handlers() -> None:
    """
    Setup signal handlers for graceful shutdown (Unix only).

    This ensures SIGTERM/SIGINT kills all worker processes, not just the main process.
    """
    if sys.platform == 'win32':
        return

    def signal_handler(signum, _frame) -> None:
        """Handle SIGTERM/SIGINT by killing entire process group"""
        if ServerState.shutdown_in_progress:
            return

        ServerState.shutdown_in_progress = True
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        try:
            print(f"\n[SHUTDOWN] Received {sig_name}, stopping all workers...")
        except (ValueError, OSError):
            pass

        stop_celery_worker()
        stop_qdrant_server()
        stop_postgresql_server()

        try:
            if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                pgid = os.getpgid(os.getpid())
                sigkill = getattr(signal, 'SIGKILL', signal.SIGTERM)
                os.killpg(pgid, sigkill)
            else:
                sys.exit(0)
        except ProcessLookupError:
            pass
        except OSError as e:
            try:
                print(f"[SHUTDOWN] Error killing process group: {e}")
            except (ValueError, OSError):
                pass

        sys.exit(0)

    try:
        if hasattr(os, 'setpgrp'):
            os.setpgrp()
    except OSError:
        pass

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def get_qdrant_process() -> Optional[Any]:
    """
    Get Qdrant process object for monitoring.

    Returns:
        Qdrant process object or None if not managed by app
    """
    return ServerState.qdrant_process


def get_celery_process() -> Optional[Any]:
    """
    Get Celery worker process object for monitoring.

    Returns:
        Celery process object or None if not managed by app
    """
    return ServerState.celery_worker_process


def get_postgresql_process() -> Optional[Any]:
    """
    Get PostgreSQL process object for monitoring.

    Returns:
        PostgreSQL process object or None if not managed by app
    """
    return ServerState.postgresql_process


def is_qdrant_managed() -> bool:
    """
    Check if Qdrant is managed by the application (subprocess).

    Returns:
        True if Qdrant is managed as subprocess, False if external/systemd
    """
    return ServerState.qdrant_process is not None


def is_celery_managed() -> bool:
    """
    Check if Celery is managed by the application (subprocess).

    Returns:
        True if Celery is managed as subprocess, False if external/systemd
    """
    return ServerState.celery_worker_process is not None


def is_postgresql_managed() -> bool:
    """
    Check if PostgreSQL is managed by the application (subprocess).

    Returns:
        True if PostgreSQL is managed as subprocess, False if external/systemd
    """
    return ServerState.postgresql_process is not None
