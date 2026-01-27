"""
Celery worker management for MindGraph application.

Handles starting and stopping Celery worker processes.
"""

import os
import sys
import time
import signal
import atexit
import subprocess
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from config.celery import celery_app
else:
    try:
        from config.celery import celery_app
    except ImportError:
        celery_app = None


def start_celery_worker(server_state) -> Optional[subprocess.Popen[bytes]]:
    """
    Start Celery worker as a subprocess (REQUIRED).

    Assumes Celery installation and dependencies have been verified. Checks
    if a worker is already running before starting a new one. Application will
    exit if Celery cannot be started.

    Args:
        server_state: ServerState instance to update

    Returns:
        Optional[subprocess.Popen[bytes]]: Celery worker process or None if using existing
    """
    if celery_app is None:
        raise RuntimeError("Celery app not available")
    for attempt in range(3):
        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            active_workers = inspect.active()

            if active_workers is not None and active_workers:
                worker_count = len(active_workers)
                worker_names = list(active_workers.keys())
                print(f"[CELERY] Found {worker_count} existing Celery worker(s):")
                for worker_name in worker_names:
                    print(f"        - {worker_name}")
                print("[CELERY] ✓ Using existing Celery worker(s), skipping startup")
                return None
            break
        except Exception:
            if attempt < 2:
                time.sleep(0.5)
                continue
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
        start_new_session = sys.platform != 'win32'

        celery_log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'logs'
        )
        os.makedirs(celery_log_dir, exist_ok=True)

        celery_stdout = None
        celery_stderr = None
        if start_new_session:
            server_state.celery_stdout_file = open(
                os.path.join(celery_log_dir, 'celery_worker.log'),
                'a',
                encoding='utf-8',
                buffering=1
            )
            server_state.celery_stderr_file = open(
                os.path.join(celery_log_dir, 'celery_worker_error.log'),
                'a',
                encoding='utf-8',
                buffering=1
            )
            celery_stdout = server_state.celery_stdout_file
            celery_stderr = server_state.celery_stderr_file
        else:
            celery_stdout = sys.stdout
            celery_stderr = sys.stderr

        server_state.celery_worker_process = subprocess.Popen(
            celery_cmd,
            stdout=celery_stdout,
            stderr=celery_stderr,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
            start_new_session=start_new_session,
            bufsize=1,
        )

        celery_managed = os.getenv('CELERY_MANAGED_BY_APP', 'true').lower() not in ('false', '0', 'no')
        if celery_managed:
            def stop_wrapper():
                stop_celery_worker(server_state)
            atexit.register(stop_wrapper)
        else:
            print(
                "[CELERY] Celery worker is running independently "
                "(CELERY_MANAGED_BY_APP=false). It will not be stopped when main process exits."
            )

        time.sleep(2)

        for i in range(10):
            try:
                if celery_app is None:
                    raise RuntimeError("Celery app not available")
                inspect = celery_app.control.inspect(timeout=2.0)
                active_workers = inspect.active()

                if active_workers is not None and active_workers:
                    if start_new_session:
                        worker_pid = server_state.celery_worker_process.pid
                        log_path = os.path.join(celery_log_dir, 'celery_worker.log')
                        print(f"[CELERY] Worker started in detached mode (PID: {worker_pid})")
                        print(f"[CELERY] Logs: {log_path}")
                    else:
                        print(f"[CELERY] Worker started (PID: {server_state.celery_worker_process.pid})")
                    print("[CELERY] Worker verified as ready")
                    return server_state.celery_worker_process
            except Exception:
                if i < 9:
                    time.sleep(1)
                else:
                    break

        print("[ERROR] Celery worker process started but not responding")
        print("        Check Celery logs for errors")
        print("        Application cannot start without Celery.")
        sys.exit(1)

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        print(f"[ERROR] Failed to start Celery worker: {e}")
        print("        Application cannot start without Celery.")
        sys.exit(1)


def stop_celery_worker(server_state) -> None:
    """Stop the Celery worker subprocess"""
    if server_state.celery_worker_process is not None:
        try:
            print("[CELERY] Stopping Celery worker...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                server_state.celery_worker_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(server_state.celery_worker_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    server_state.celery_worker_process.terminate()
            server_state.celery_worker_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[CELERY] Error stopping worker: {e}")
            except (ValueError, OSError):
                pass
            try:
                server_state.celery_worker_process.kill()
            except (OSError, ProcessLookupError):
                pass

        if server_state.celery_stdout_file is not None:
            try:
                server_state.celery_stdout_file.close()
            except (OSError, ValueError):
                pass
            server_state.celery_stdout_file = None

        if server_state.celery_stderr_file is not None:
            try:
                server_state.celery_stderr_file.close()
            except (OSError, ValueError):
                pass
            server_state.celery_stderr_file = None

        server_state.celery_worker_process = None
        try:
            print("[CELERY] Worker stopped")
        except (ValueError, OSError):
            pass
