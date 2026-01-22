"""
Process management utilities for MindGraph application.

Handles starting and stopping required services:
- Redis server (via systemctl or manual)
- Celery worker (subprocess)
- Qdrant server (subprocess or systemd service)
- Signal handlers for graceful shutdown
"""

import os
import sys
import time
import signal
import atexit
import subprocess
import urllib.request
from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis as redis_module
else:
    try:
        import redis as redis_module
    except ImportError:
        redis_module = None


class ServerState:
    """Module-level state for server processes"""
    celery_worker_process: Optional[subprocess.Popen[bytes]] = None
    celery_stdout_file: Optional[Any] = None
    celery_stderr_file: Optional[Any] = None
    qdrant_process: Optional[subprocess.Popen[bytes]] = None
    redis_started_by_app: bool = False
    shutdown_in_progress: bool = False


def _get_redis_client(host: str, port: int, timeout: int = 2):
    """Helper function to create Redis client with proper type narrowing"""
    if redis_module is None:
        raise RuntimeError("Redis module not available")
    redis_client_class = getattr(redis_module, 'Redis')
    return redis_client_class(host=host, port=port, socket_connect_timeout=timeout)


def start_redis_server() -> None:
    """
    Start Redis server if not already running (REQUIRED).

    Assumes Redis installation has been verified. Checks if Redis is running,
    and if not, attempts to start it via systemctl. Application will exit if
    Redis cannot be started.
    """
    # Type guard: redis should be available after check_redis_installed()
    if redis_module is None:
        print("[ERROR] Redis module not available despite installation check passing.")
        sys.exit(1)

    # Check if Redis is already running
    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port_str = os.getenv('REDIS_PORT', '6379')
        redis_port = int(redis_port_str)
        r = _get_redis_client(redis_host, redis_port, 2)
        r.ping()
        print("[REDIS] Redis server is already running")
        return
    except Exception:
        pass

    # On Linux, try to start Redis via systemctl
    if sys.platform != 'win32':
        try:
            print("[REDIS] Starting Redis server via systemctl...")
            start_result = subprocess.run(
                ['sudo', 'systemctl', 'start', 'redis-server'],
                capture_output=True,
                timeout=5,
                check=False
            )

            if start_result.returncode != 0:
                error_msg = start_result.stderr.decode('utf-8', errors='ignore')
                if 'already active' not in error_msg.lower() and 'already started' not in error_msg.lower():
                    print("[ERROR] Failed to start Redis server via systemctl.")
                    print(f"        Error: {error_msg}")
                    print("        Try manually: sudo systemctl start redis-server")
                    print("        Application cannot start without Redis.")
                    sys.exit(1)

            ServerState.redis_started_by_app = True
            print("[REDIS] Redis server started via systemctl")

            # Wait for Redis to be ready (up to 10 seconds)
            for i in range(10):
                try:
                    r = _get_redis_client(redis_host, redis_port, 1)
                    r.ping()
                    print("[REDIS] Redis server is ready")
                    return
                except Exception:
                    if i < 9:
                        time.sleep(1)
                    else:
                        break

            print("[ERROR] Redis server started but not responding after 10 seconds")
            print("        Check Redis logs: sudo journalctl -u redis-server -n 50")
            print("        Application cannot start without Redis.")
            sys.exit(1)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"[ERROR] Cannot start Redis server: {e}")
            print("        Redis is REQUIRED. Please start Redis manually:")
            print("        sudo systemctl start redis-server")
            print("        Application cannot start without Redis.")
            sys.exit(1)
    else:
        print("[ERROR] Redis is REQUIRED but not running on Windows.")
        print("        Please start Redis manually or install Redis for Windows.")
        print("        Application cannot start without Redis.")
        sys.exit(1)


def start_celery_worker() -> Optional[subprocess.Popen[bytes]]:
    """
    Start Celery worker as a subprocess (REQUIRED).

    Assumes Celery installation and dependencies have been verified. Checks
    if a worker is already running before starting a new one. Application will
    exit if Celery cannot be started.
    """
    # Check if a Celery worker is already running
    # Retry a few times in case Redis is still initializing
    for attempt in range(3):
        try:
            from config.celery import celery_app
            inspect = celery_app.control.inspect(timeout=2.0)
            active_workers = inspect.active()
            
            if active_workers is not None and active_workers:
                worker_count = len(active_workers)
                print(f"[CELERY] Found {worker_count} existing Celery worker(s), reusing...")
                print("[CELERY] Celery worker is already running, skipping startup")
                return None
            # If active_workers is None or empty, break and start a new worker
            break
        except Exception:
            # If check fails, wait a bit and retry (Redis might still be initializing)
            if attempt < 2:
                time.sleep(0.5)
                continue
            # On final attempt failure, proceed to start a new worker
            break
    
    print("[CELERY] Starting Celery worker for background task processing...")

    python_exe = sys.executable

    celery_cmd = [
        python_exe, '-m', 'celery',
        '-A', 'config.celery',
        'worker',
        '--loglevel=debug',
        '--concurrency=2',
        '-Q', 'default,knowledge',
    ]

    if sys.platform == 'win32':
        celery_cmd.extend(['--pool=solo'])

    try:
        # Detach from terminal on Linux/Unix so worker survives terminal closure
        # On Windows, CREATE_NEW_PROCESS_GROUP already provides some isolation
        start_new_session = sys.platform != 'win32'

        # Redirect output to files for detached processes (optional but recommended)
        # If detached, stdout/stderr won't be visible in terminal anyway
        celery_log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'logs'
        )
        os.makedirs(celery_log_dir, exist_ok=True)

        celery_stdout = None
        celery_stderr = None
        if start_new_session:
            # When detached, redirect to log files
            ServerState.celery_stdout_file = open(
                os.path.join(celery_log_dir, 'celery_worker.log'),
                'a',
                encoding='utf-8',
                buffering=1
            )
            ServerState.celery_stderr_file = open(
                os.path.join(celery_log_dir, 'celery_worker_error.log'),
                'a',
                encoding='utf-8',
                buffering=1
            )
            celery_stdout = ServerState.celery_stdout_file
            celery_stderr = ServerState.celery_stderr_file
        else:
            # On Windows, keep stdout/stderr attached for debugging
            celery_stdout = sys.stdout
            celery_stderr = sys.stderr

        ServerState.celery_worker_process = subprocess.Popen(
            celery_cmd,
            stdout=celery_stdout,
            stderr=celery_stderr,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
            start_new_session=start_new_session,
            bufsize=1,
        )

        # Only register atexit handler if CELERY_MANAGED_BY_APP is not set to 'false'
        # When using nohup/systemd, you might want Celery to survive main process restarts
        celery_managed = os.getenv('CELERY_MANAGED_BY_APP', 'true').lower() not in ('false', '0', 'no')
        if celery_managed:
            atexit.register(stop_celery_worker)
        else:
            print(
                "[CELERY] Celery worker is running independently "
                "(CELERY_MANAGED_BY_APP=false). It will not be stopped when main process exits."
            )

        if start_new_session:
            print(f"[CELERY] Worker started in detached mode (PID: {ServerState.celery_worker_process.pid})")
            print(f"[CELERY] Logs: {os.path.join(celery_log_dir, 'celery_worker.log')}")
        else:
            print(f"[CELERY] Worker started (PID: {ServerState.celery_worker_process.pid})")
        return ServerState.celery_worker_process

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to start Celery worker: {e}")
        print("        Application cannot start without Celery.")
        sys.exit(1)


def start_qdrant_server() -> Optional[subprocess.Popen[bytes]]:
    """
    Start Qdrant server as a subprocess if not already running (REQUIRED).

    Assumes Qdrant installation has been verified. Checks if Qdrant is running,
    and if not, attempts to start it. Application will exit if Qdrant cannot be started.
    """
    try:
        urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
        print("[QDRANT] Qdrant server is already running on port 6333")
        return None
    except Exception:
        pass

    if sys.platform != 'win32':
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'qdrant'],
                capture_output=True,
                timeout=1,
                check=False
            )
            if result.returncode == 0:
                print("[QDRANT] Qdrant systemd service is active (waiting for readiness...)")
                for i in range(10):
                    try:
                        urllib.request.urlopen('http://localhost:6333/collections', timeout=1)
                        print("[QDRANT] Qdrant systemd service is ready")
                        return None
                    except Exception:
                        if i < 9:
                            time.sleep(1)
                        else:
                            break
                print("[ERROR] Qdrant systemd service is active but not responding after 10 seconds")
                print("        Check Qdrant logs: sudo journalctl -u qdrant -n 50")
                print("        Application cannot start without Qdrant.")
                sys.exit(1)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    qdrant_paths = [
        os.path.expanduser('~/qdrant/qdrant'),
        '/usr/local/bin/qdrant',
        '/usr/bin/qdrant',
    ]

    qdrant_binary = None
    for path in qdrant_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            qdrant_binary = path
            break

    if not qdrant_binary:
        print("[ERROR] Qdrant binary not found despite installation check passing.")
        print("        This may indicate a configuration issue.")
        print("        Application cannot start without Qdrant.")
        sys.exit(1)

    qdrant_dir = os.path.dirname(qdrant_binary)
    qdrant_storage = os.path.join(qdrant_dir, 'storage')
    os.makedirs(qdrant_storage, exist_ok=True)

    print("[QDRANT] Starting Qdrant server as subprocess...")

    qdrant_cmd = [qdrant_binary]

    try:
        ServerState.qdrant_process = subprocess.Popen(
            qdrant_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=qdrant_dir,
            env={
                **os.environ,
                'QDRANT__STORAGE__STORAGE_PATH': qdrant_storage,
                'QDRANT__SERVICE__HTTP_PORT': '6333',
            },
            bufsize=1,
        )

        atexit.register(stop_qdrant_server)

        time.sleep(2)

        try:
            urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
            print(f"[QDRANT] Server started successfully (PID: {ServerState.qdrant_process.pid})")
            return ServerState.qdrant_process
        except Exception:
            print("[ERROR] Qdrant server process started but not responding on port 6333")
            print("        Check if port 6333 is available: lsof -i :6333")
            print("        Application cannot start without Qdrant.")
            sys.exit(1)

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to start Qdrant server: {e}")
        print("        Application cannot start without Qdrant.")
        sys.exit(1)


def stop_qdrant_server() -> None:
    """Stop the Qdrant server subprocess"""
    if ServerState.qdrant_process is not None:
        try:
            print("[QDRANT] Stopping Qdrant server...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                ServerState.qdrant_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(ServerState.qdrant_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    ServerState.qdrant_process.terminate()
            ServerState.qdrant_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[QDRANT] Error stopping server: {e}")
            except (ValueError, OSError):
                pass
            try:
                ServerState.qdrant_process.kill()
            except (OSError, ProcessLookupError):
                pass
        ServerState.qdrant_process = None
        try:
            print("[QDRANT] Server stopped")
        except (ValueError, OSError):
            pass


def stop_celery_worker() -> None:
    """Stop the Celery worker subprocess"""
    if ServerState.celery_worker_process is not None:
        try:
            print("[CELERY] Stopping Celery worker...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                ServerState.celery_worker_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(ServerState.celery_worker_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    ServerState.celery_worker_process.terminate()
            ServerState.celery_worker_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[CELERY] Error stopping worker: {e}")
            except (ValueError, OSError):
                pass
            try:
                ServerState.celery_worker_process.kill()
            except (OSError, ProcessLookupError):
                pass

        # Close log file handles if they were opened
        if ServerState.celery_stdout_file is not None:
            try:
                ServerState.celery_stdout_file.close()
            except (OSError, ValueError):
                pass
            ServerState.celery_stdout_file = None

        if ServerState.celery_stderr_file is not None:
            try:
                ServerState.celery_stderr_file.close()
            except (OSError, ValueError):
                pass
            ServerState.celery_stderr_file = None

        ServerState.celery_worker_process = None
        try:
            print("[CELERY] Worker stopped")
        except (ValueError, OSError):
            pass


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


def get_qdrant_process() -> Optional[subprocess.Popen[bytes]]:
    """
    Get Qdrant process object for monitoring.

    Returns:
        Qdrant process object or None if not managed by app
    """
    return ServerState.qdrant_process


def get_celery_process() -> Optional[subprocess.Popen[bytes]]:
    """
    Get Celery worker process object for monitoring.

    Returns:
        Celery process object or None if not managed by app
    """
    return ServerState.celery_worker_process


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
