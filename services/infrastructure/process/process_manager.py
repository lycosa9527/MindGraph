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
import socket
import urllib.request
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis as redis_module
    import psycopg2
    from psycopg2 import sql
    from config.celery import celery_app
else:
    try:
        import redis as redis_module
    except ImportError:
        redis_module = None

    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        psycopg2 = None
        sql = None

    try:
        from config.celery import celery_app
    except ImportError:
        celery_app = None


class ServerState:
    """Module-level state for server processes"""
    celery_worker_process: Optional[subprocess.Popen[bytes]] = None
    celery_stdout_file: Optional[Any] = None
    celery_stderr_file: Optional[Any] = None
    qdrant_process: Optional[subprocess.Popen[bytes]] = None
    postgresql_process: Optional[subprocess.Popen[bytes]] = None
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
    if celery_app is None:
        raise RuntimeError("Celery app not available")
    for attempt in range(3):
        try:
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

        # Wait a moment for worker to initialize
        time.sleep(2)

        # Verify Celery worker is actually running and ready
        for i in range(10):
            try:
                if celery_app is None:
                    raise RuntimeError("Celery app not available")
                inspect = celery_app.control.inspect(timeout=2.0)
                active_workers = inspect.active()

                if active_workers is not None and active_workers:
                    if start_new_session:
                        worker_pid = ServerState.celery_worker_process.pid
                        log_path = os.path.join(celery_log_dir, 'celery_worker.log')
                        print(f"[CELERY] Worker started in detached mode (PID: {worker_pid})")
                        print(f"[CELERY] Logs: {log_path}")
                    else:
                        print(f"[CELERY] Worker started (PID: {ServerState.celery_worker_process.pid})")
                    print("[CELERY] Worker verified as ready")
                    return ServerState.celery_worker_process
            except Exception:
                if i < 9:
                    time.sleep(1)
                else:
                    break

        # Worker process started but not responding
        print("[ERROR] Celery worker process started but not responding")
        print("        Check Celery logs for errors")
        print("        Application cannot start without Celery.")
        sys.exit(1)

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


def start_postgresql_server() -> Optional[subprocess.Popen[bytes]]:
    """
    Start PostgreSQL server as a subprocess if not already running (REQUIRED).

    Assumes PostgreSQL installation has been verified. Checks if PostgreSQL is running,
    and if not, attempts to start it. Application will exit if PostgreSQL cannot be started.

    For subprocess mode:
    - Initializes data directory with initdb if needed
    - Generates postgresql.conf and pg_hba.conf
    - Creates database/user on first startup
    - Starts postgres binary as subprocess
    """
    if psycopg2 is None:
        print("[ERROR] psycopg2 is not available")
        print("        Install with: pip install psycopg2-binary")
        print("        Application cannot start without PostgreSQL.")
        sys.exit(1)

    # Check if PostgreSQL is already running (connection test)
    db_url = os.getenv('DATABASE_URL', '')
    if db_url and 'postgresql' in db_url:
        try:
            conn = psycopg2.connect(db_url, connect_timeout=2)
            conn.close()
            try:
                print("[POSTGRESQL] PostgreSQL server is already running")
                print("[POSTGRESQL] Using existing PostgreSQL instance")
            except (ValueError, OSError):
                pass
            return None
        except Exception:
            pass

    # Get PostgreSQL configuration
    port = os.getenv('POSTGRESQL_PORT', '5432')
    user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
    password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
    database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

    # Check if port is already in use (might be system PostgreSQL)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', int(port)))
        sock.close()
        if result == 0:
            # Port is in use - check if it's PostgreSQL
            # Try connecting with configured credentials first
            try:
                if db_url and 'postgresql' in db_url:
                    test_conn = psycopg2.connect(db_url, connect_timeout=2)
                    test_conn.close()
                    try:
                        print(f"[POSTGRESQL] Port {port} is in use - connection successful")
                        print("[POSTGRESQL] Using existing PostgreSQL instance")
                    except (ValueError, OSError):
                        pass
                    return None
            except Exception:
                pass

            # If configured connection failed, try connecting as postgres superuser
            # This might work if system PostgreSQL allows local connections
            # Fallback to current Linux user if postgres role doesn't exist
            superuser_name = 'postgres'
            current_user = os.getenv('USER') or os.getenv('USERNAME') or 'postgres'
            existing_pg_detected = False
            try:
                test_conn = psycopg2.connect(
                    f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                    connect_timeout=2
                )
                test_conn.close()
                existing_pg_detected = True
            except Exception as e:
                # Try current Linux user if postgres doesn't exist
                if 'role "postgres" does not exist' in str(e) and current_user != 'postgres':
                    try:
                        test_conn = psycopg2.connect(
                            f'postgresql://{current_user}@127.0.0.1:{port}/postgres',
                            connect_timeout=2
                        )
                        test_conn.close()
                        superuser_name = current_user
                        existing_pg_detected = True
                    except Exception as inner_exc:
                        raise inner_exc from e
                else:
                    raise

            if existing_pg_detected:
                try:
                    print(f"[POSTGRESQL] Port {port} is in use by existing PostgreSQL instance")
                    print("[POSTGRESQL] Using existing PostgreSQL (system or external service)")
                except (ValueError, OSError):
                    pass

                # Use existing PostgreSQL - create database/user if needed
                try:
                    if sql is None:
                        raise RuntimeError("psycopg2.sql not available")

                    # Connect as superuser (postgres or current Linux user)
                    conn = psycopg2.connect(
                        f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                        connect_timeout=5
                    )
                    conn.autocommit = True
                    cursor = conn.cursor()

                    # Check if user exists
                    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
                    if not cursor.fetchone():
                        create_user_query = sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                            sql.Identifier(user)
                        )
                        cursor.execute(create_user_query, (password,))
                        try:
                            print(f"[POSTGRESQL] Created user: {user}")
                        except (ValueError, OSError):
                            pass

                    # Check if database exists
                    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
                    if not cursor.fetchone():
                        create_db_query = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(database),
                            sql.Identifier(user)
                        )
                        cursor.execute(create_db_query)
                        try:
                            print(f"[POSTGRESQL] Created database: {database}")
                        except (ValueError, OSError):
                            pass

                    cursor.close()
                    conn.close()

                    # Verify connection with configured credentials
                    conn = psycopg2.connect(db_url, connect_timeout=5)
                    conn.close()
                    try:
                        print("[POSTGRESQL] ✓ Using existing PostgreSQL instance")
                    except (ValueError, OSError):
                        pass
                    return None
                except Exception as e:
                    try:
                        print(f"[WARNING] Failed to create database/user (may already exist): {e}")
                        # Try to connect anyway - might already exist
                        conn = psycopg2.connect(db_url, connect_timeout=5)
                        conn.close()
                        try:
                            print("[POSTGRESQL] ✓ Using existing PostgreSQL instance")
                        except (ValueError, OSError):
                            pass
                        return None
                    except Exception:
                        # If connection fails, try using a different port for subprocess
                        try:
                            print(f"[POSTGRESQL] Cannot connect to existing PostgreSQL on port {port}")
                            print("[POSTGRESQL] Will try to start subprocess on different port")
                            # Try port 5433 as fallback
                            port = '5433'
                            # Update DATABASE_URL if it was using default port
                            if db_url and f':{os.getenv("POSTGRESQL_PORT", "5432")}/' in db_url:
                                new_db_url = db_url.replace(f':{os.getenv("POSTGRESQL_PORT", "5432")}/', f':{port}/')
                                os.environ['DATABASE_URL'] = new_db_url
                                print(f"[POSTGRESQL] Updated DATABASE_URL to use port {port}")
                        except (ValueError, OSError):
                            pass
                        # Continue to start subprocess
    except Exception:
        # Socket check failed, continue with normal startup
        pass

    # Check if port is already in use (might be system PostgreSQL)
    port = os.getenv('POSTGRESQL_PORT', '5432')
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', int(port)))
        sock.close()
        if result == 0:
            try:
                # Check if it's PostgreSQL
                # Try postgres superuser first, then fallback to current Linux user
                superuser_name = 'postgres'
                current_user = os.getenv('USER') or os.getenv('USERNAME') or 'postgres'
                try:
                    test_conn = psycopg2.connect(
                        f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                        connect_timeout=2
                    )
                    test_conn.close()
                except Exception as e:
                    # Try current Linux user if postgres doesn't exist
                    if 'role "postgres" does not exist' in str(e) and current_user != 'postgres':
                        test_conn = psycopg2.connect(
                            f'postgresql://{current_user}@127.0.0.1:{port}/postgres',
                            connect_timeout=2
                        )
                        test_conn.close()
                        superuser_name = current_user
                    else:
                        # Not PostgreSQL or can't connect
                        raise

                try:
                    print(f"[POSTGRESQL] Port {port} is in use by existing PostgreSQL instance")
                    print("[POSTGRESQL] Using existing PostgreSQL (will create database/user if needed)")
                except (ValueError, OSError):
                    pass
                # Use existing PostgreSQL - skip subprocess startup
                # Database/user creation will happen later
                return None
            except Exception:
                # Port is in use but not PostgreSQL - this is a problem
                try:
                    print(f"[ERROR] Port {port} is in use but not by PostgreSQL")
                    print(f"        Stop the service using port {port} or use a different port")
                    print(f"        Check: sudo lsof -i :{port} or sudo netstat -tuln | grep {port}")
                except (ValueError, OSError):
                    pass
                sys.exit(1)
    except Exception:
        # Socket check failed, continue with normal startup
        pass

    # Check if managed by app (subprocess mode)
    postgresql_managed = os.getenv('POSTGRESQL_MANAGED_BY_APP', 'true').lower() not in ('false', '0', 'no')
    if not postgresql_managed:
        # Check for systemd service
        if sys.platform != 'win32':
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', '--quiet', 'postgresql'],
                    capture_output=True,
                    timeout=1,
                    check=False
                )
                if result.returncode == 0:
                    try:
                        print("[POSTGRESQL] PostgreSQL systemd service is active (waiting for readiness...)")
                    except (ValueError, OSError):
                        pass
                    # Wait for PostgreSQL to be ready
                    for i in range(10):
                        try:
                            conn = psycopg2.connect(db_url, connect_timeout=2)
                            conn.close()
                            try:
                                print("[POSTGRESQL] PostgreSQL systemd service is ready")
                            except (ValueError, OSError):
                                pass
                            return None
                        except Exception:
                            if i < 9:
                                time.sleep(1)
                            else:
                                break
                    try:
                        print("[ERROR] PostgreSQL systemd service is active but not responding after 10 seconds")
                        print("        Check PostgreSQL logs: sudo journalctl -u postgresql -n 50")
                        print("        Application cannot start without PostgreSQL.")
                    except (ValueError, OSError):
                        pass
                    sys.exit(1)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    # Find PostgreSQL binaries
    postgres_paths = [
        '/usr/lib/postgresql/18/bin/postgres',
        '/usr/lib/postgresql/16/bin/postgres',
        '/usr/lib/postgresql/15/bin/postgres',
        '/usr/lib/postgresql/14/bin/postgres',
        '/usr/local/pgsql/bin/postgres',
        '/usr/bin/postgres',
    ]

    postgres_binary = None
    initdb_binary = None
    for path in postgres_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            postgres_binary = path
            # Find initdb in same directory
            postgres_dir = os.path.dirname(path)
            initdb_path = os.path.join(postgres_dir, 'initdb')
            if os.path.exists(initdb_path) and os.access(initdb_path, os.X_OK):
                initdb_binary = initdb_path
            break

    if not postgres_binary:
        try:
            print("[ERROR] PostgreSQL postgres binary not found despite installation check passing.")
            print("        This may indicate a configuration issue.")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    if not initdb_binary:
        try:
            print("[ERROR] PostgreSQL initdb binary not found.")
            print("        Install PostgreSQL with: sudo apt-get install postgresql postgresql-contrib")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # Get configuration from environment
    data_dir = os.getenv('POSTGRESQL_DATA_DIR', './storage/postgresql')
    port = os.getenv('POSTGRESQL_PORT', '5432')
    user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
    password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
    database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

    data_path = Path(data_dir).resolve()

    # Check if we're on WSL with Windows-mounted filesystem
    # This includes symlinks that point to /mnt/ (common in WSL)
    resolved_str = str(data_path)
    is_wsl_windows_fs = resolved_str.startswith('/mnt/')

    # Also check if the resolved path follows a symlink to Windows filesystem
    if not is_wsl_windows_fs:
        try:
            # Check if any parent directory is a symlink pointing to /mnt/
            current = data_path
            while current != current.parent:
                if current.is_symlink():
                    link_target = current.readlink()
                    if str(link_target.resolve()).startswith('/mnt/'):
                        is_wsl_windows_fs = True
                        break
                current = current.parent
        except Exception:
            # If symlink checking fails, rely on path string check
            pass

    # Auto-fix: If on Windows filesystem, automatically use Linux-native alternative
    if is_wsl_windows_fs:
        # Use Linux-native path in user's home directory
        # This avoids permission issues with Windows-mounted filesystems
        linux_native_dir = Path.home() / '.mindgraph' / 'postgresql'
        linux_native_dir.mkdir(parents=True, exist_ok=True)

        try:
            print("[POSTGRESQL] Detected Windows-mounted filesystem - using Linux-native path")
            print(f"[POSTGRESQL] Original path: {data_path}")
            print(f"[POSTGRESQL] Using Linux-native path: {linux_native_dir}")
            print("[POSTGRESQL] (To use a custom path, set POSTGRESQL_DATA_DIR to a Linux-native location)")
        except (ValueError, OSError):
            pass

        data_path = linux_native_dir.resolve()

    data_path.mkdir(parents=True, exist_ok=True)

    # Set proper permissions for PostgreSQL data directory (required: 0700 or 0750)
    # PostgreSQL is strict about permissions - must be u=rwx (0700) or u=rwx,g=rx (0750)
    try:
        os.chmod(data_path, 0o700)
    except OSError:
        # On some systems, chmod might fail - log warning but continue
        # initdb will fail with clear error if permissions are wrong
        pass

    # Initialize data directory if needed
    pg_version_file = data_path / 'PG_VERSION'
    if not pg_version_file.exists():
        try:
            print("[POSTGRESQL] Initializing PostgreSQL data directory...")
        except (ValueError, OSError):
            pass
        try:
            # Use -U postgres to explicitly create postgres superuser
            # This ensures consistent superuser name across all platforms (WSL, Linux, etc.)
            initdb_result = subprocess.run(
                [initdb_binary, '-D', str(data_path), '-U', 'postgres', '--locale=C', '--encoding=UTF8'],
                capture_output=True,
                timeout=30,
                check=False,
                text=True
            )
            if initdb_result.returncode != 0:
                error_msg = initdb_result.stderr
                try:
                    print(f"[ERROR] Failed to initialize PostgreSQL data directory: {error_msg}")
                    print("        Application cannot start without PostgreSQL.")
                except (ValueError, OSError):
                    pass
                sys.exit(1)
            try:
                print("[POSTGRESQL] Data directory initialized")
            except (ValueError, OSError):
                pass
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
            try:
                print(f"[ERROR] Failed to initialize PostgreSQL data directory: {e}")
                print("        Application cannot start without PostgreSQL.")
            except (ValueError, OSError):
                pass
            sys.exit(1)

    # Generate postgresql.conf if needed
    postgresql_conf = data_path / 'postgresql.conf'
    # Socket directory within data directory (user-owned, avoids /var/run permission issues)
    socket_dir = data_path / 'sockets'
    socket_dir.mkdir(exist_ok=True)
    # Ensure socket directory has proper permissions (user read/write/execute)
    try:
        os.chmod(socket_dir, 0o700)
    except OSError:
        # chmod might fail on some filesystems, but that's okay
        pass

    # Always update postgresql.conf to use our socket directory (not /var/run/postgresql/)
    # This prevents PostgreSQL from trying to use /var/run/postgresql/ which requires root
    try:
        config_needs_update = True
        if postgresql_conf.exists():
            # Check if config already has correct socket directory and locale settings
            with open(postgresql_conf, 'r', encoding='utf-8') as f:
                content = f.read()
                has_correct_socket = f'unix_socket_directories = \'{socket_dir}\'' in content
                has_c_locale = 'lc_messages = \'C\'' in content
                if has_correct_socket and has_c_locale:
                    config_needs_update = False

        if config_needs_update:
            # Always rewrite config to ensure correct settings
            with open(postgresql_conf, 'w', encoding='utf-8') as f:
                f.write(f"""# PostgreSQL configuration for MindGraph subprocess mode
port = {port}
listen_addresses = '127.0.0.1'
# Use our socket directory (user-owned) instead of /var/run/postgresql/
unix_socket_directories = '{socket_dir}'
max_connections = 100
shared_buffers = 128MB
dynamic_shared_memory_type = posix
log_destination = 'stderr'
logging_collector = off
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_timezone = 'UTC'
datestyle = 'iso, mdy'
timezone = 'UTC'
# Locale settings - use C locale to avoid locale validation issues
lc_messages = 'C'
lc_monetary = 'C'
lc_numeric = 'C'
lc_time = 'C'
default_text_search_config = 'pg_catalog.english'
""")
            try:
                print(f"[POSTGRESQL] Updated postgresql.conf with socket directory: {socket_dir}")
            except (ValueError, OSError):
                pass
    except Exception as e:
        try:
            print(f"[ERROR] Failed to update postgresql.conf: {e}")
        except (ValueError, OSError):
            pass

    # Generate pg_hba.conf if needed
    pg_hba_conf = data_path / 'pg_hba.conf'
    if not pg_hba_conf.exists():
        try:
            with open(pg_hba_conf, 'w', encoding='utf-8') as f:
                f.write("""# PostgreSQL host-based authentication configuration
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
""")
        except Exception as e:
            try:
                print(f"[ERROR] Failed to create pg_hba.conf: {e}")
            except (ValueError, OSError):
                pass

    # Start PostgreSQL server
    try:
        print("[POSTGRESQL] Starting PostgreSQL server as subprocess...")
    except (ValueError, OSError):
        pass

    # Verify socket directory exists and is writable
    if not socket_dir.exists():
        socket_dir.mkdir(parents=True, exist_ok=True)
    # Ensure socket directory has proper permissions
    try:
        os.chmod(socket_dir, 0o700)
    except OSError:
        pass

    if not os.access(socket_dir, os.W_OK):
        try:
            print(f"[ERROR] Socket directory is not writable: {socket_dir}")
            print(f"        Fix permissions: chmod 700 {socket_dir}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # Use absolute path for socket directory to avoid any path resolution issues
    socket_dir_abs = str(socket_dir.resolve())

    # Create a test file in socket directory to verify write permissions
    test_file = socket_dir / '.test_write'
    try:
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        try:
            print(f"[ERROR] Cannot write to socket directory {socket_dir_abs}: {e}")
            print(f"        Fix permissions: chmod 700 {socket_dir_abs}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # Pass socket directory as command-line argument to override any defaults
    # This ensures PostgreSQL uses our socket directory, not /var/run/postgresql/
    # Also set environment variable PGHOST to prevent fallback to /var/run/postgresql/
    postgres_env = os.environ.copy()
    postgres_env['PGHOST'] = socket_dir_abs  # Set socket directory via env var too

    postgres_cmd = [
        postgres_binary,
        '-D', str(data_path),
        '-c', f'unix_socket_directories={socket_dir_abs}',  # Use our socket directory
        '-c', 'listen_addresses=127.0.0.1'
    ]

    try:
        print(f"[POSTGRESQL] Socket directory: {socket_dir_abs}")
    except (ValueError, OSError):
        pass

    try:
        # Create logs directory
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        postgres_log = logs_dir / 'postgresql.log'

        postgres_stdout = open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stdout
        postgres_stderr = open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stderr

        ServerState.postgresql_process = subprocess.Popen(
            postgres_cmd,
            stdout=postgres_stdout,
            stderr=postgres_stderr,
            cwd=str(data_path),
            env=postgres_env,
            start_new_session=sys.platform != 'win32',
            bufsize=1,
        )

        atexit.register(stop_postgresql_server)

        # Wait for PostgreSQL to be ready (up to 30 seconds)
        # PostgreSQL can take a few seconds to start, especially on first initialization
        # Try connecting as postgres superuser first, then fallback to current Linux user
        # (for backward compatibility with existing installations)
        last_error = None
        superuser_name = 'postgres'
        current_user = os.getenv('USER') or os.getenv('USERNAME') or 'postgres'

        for i in range(30):
            try:
                # Try connecting as postgres superuser first
                conn = psycopg2.connect(
                    f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                    connect_timeout=2
                )
                conn.close()
                break
            except Exception as e:
                # If postgres user doesn't exist, try current Linux user (for existing installations)
                if 'role "postgres" does not exist' in str(e) and current_user != 'postgres':
                    try:
                        conn = psycopg2.connect(
                            f'postgresql://{current_user}@127.0.0.1:{port}/postgres',
                            connect_timeout=2
                        )
                        conn.close()
                        superuser_name = current_user
                        try:
                            print(
                                f"[POSTGRESQL] Using current Linux user '{current_user}' "
                                "as superuser (postgres role not found)"
                            )
                        except (ValueError, OSError):
                            pass
                        break
                    except Exception:
                        # Fall through to error handling
                        pass
                last_error = e
                if i < 29:
                    time.sleep(1)
                else:
                    # Check if process is still running
                    if ServerState.postgresql_process.poll() is not None:
                        # Process has terminated - read error from logs
                        try:
                            if postgres_log.exists():
                                with open(postgres_log, 'r', encoding='utf-8') as f:
                                    log_lines = f.readlines()
                                    if log_lines:
                                        last_log_lines = '\n'.join(log_lines[-10:])
                                        print("[ERROR] PostgreSQL server process terminated")
                                        print(f"[ERROR] Last log entries:\n{last_log_lines}")
                        except Exception:
                            pass
                    else:
                        # Process is running but not responding
                        try:
                            print("[ERROR] PostgreSQL server process started but not responding after 30 seconds")
                            print(f"[ERROR] Last connection error: {last_error}")
                            print(f"[ERROR] Check PostgreSQL logs: tail -f {postgres_log}")
                            print(f"[ERROR] Data directory: {data_path}")
                            print(f"[ERROR] Try manually: psql -U {superuser_name} -h 127.0.0.1 -p {port} -d postgres")
                        except (ValueError, OSError):
                            pass
                    sys.exit(1)

        # Create database and user if needed
        try:
            if sql is None:
                raise RuntimeError("psycopg2.sql not available")

            # Connect as superuser (postgres or current Linux user)
            conn = psycopg2.connect(
                f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                connect_timeout=5
            )
            conn.autocommit = True
            cursor = conn.cursor()

            # Check if user exists
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
            if not cursor.fetchone():
                # Use sql.Identifier for proper escaping of user name
                create_user_query = sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(user)
                )
                cursor.execute(create_user_query, (password,))
                try:
                    print(f"[POSTGRESQL] Created user: {user}")
                except (ValueError, OSError):
                    pass

            # Check if database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if not cursor.fetchone():
                # Use sql.Identifier for proper escaping of database and user names
                create_db_query = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database),
                    sql.Identifier(user)
                )
                cursor.execute(create_db_query)
                try:
                    print(f"[POSTGRESQL] Created database: {database}")
                except (ValueError, OSError):
                    pass

            cursor.close()
            conn.close()
        except Exception as e:
            try:
                print(f"[WARNING] Failed to create database/user (may already exist): {e}")
            except (ValueError, OSError):
                pass

        # Verify connection with configured credentials
        try:
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.close()
            try:
                print(f"[POSTGRESQL] Server started successfully (PID: {ServerState.postgresql_process.pid})")
                if sys.platform != 'win32':
                    print(f"[POSTGRESQL] Logs: {postgres_log}")
            except (ValueError, OSError):
                pass
            return ServerState.postgresql_process
        except Exception as e:
            try:
                print(f"[ERROR] PostgreSQL server started but connection test failed: {e}")
                print("        Check PostgreSQL logs: tail -f logs/postgresql.log")
                print("        Application cannot start without PostgreSQL.")
            except (ValueError, OSError):
                pass
            sys.exit(1)

    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        try:
            print(f"[ERROR] Failed to start PostgreSQL server: {e}")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)


def stop_postgresql_server() -> None:
    """Stop the PostgreSQL server subprocess"""
    if ServerState.postgresql_process is not None:
        try:
            print("[POSTGRESQL] Stopping PostgreSQL server...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                ServerState.postgresql_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(ServerState.postgresql_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    ServerState.postgresql_process.terminate()
            ServerState.postgresql_process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[POSTGRESQL] Error stopping server: {e}")
            except (ValueError, OSError):
                pass
            try:
                ServerState.postgresql_process.kill()
            except (OSError, ProcessLookupError):
                pass
        ServerState.postgresql_process = None
        try:
            print("[POSTGRESQL] Server stopped")
        except (ValueError, OSError):
            pass


def get_postgresql_process() -> Optional[subprocess.Popen[bytes]]:
    """
    Get PostgreSQL process object for monitoring.

    Returns:
        PostgreSQL process object or None if not managed by app
    """
    return ServerState.postgresql_process


def is_postgresql_managed() -> bool:
    """
    Check if PostgreSQL is managed by the application (subprocess).

    Returns:
        True if PostgreSQL is managed as subprocess, False if external/systemd
    """
    return ServerState.postgresql_process is not None
