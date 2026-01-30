"""
PostgreSQL server management for MindGraph application.

Handles starting and stopping PostgreSQL server processes.
"""

import os
import sys
import time
import signal
import atexit
import subprocess
import shlex
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from services.infrastructure.process._port_utils import check_port_in_use
from services.infrastructure.process._postgresql_helpers import (
    verify_postgresql_on_port,
    cleanup_stale_pid_file
)
from services.infrastructure.process._postgresql_paths import (
    find_postgres_binaries,
    resolve_data_path
)
from services.infrastructure.process._postgresql_init import (
    initialize_postgresql_data_directory
)
from services.infrastructure.process._postgresql_config import (
    setup_socket_directory,
    update_postgresql_conf,
    create_pg_hba_conf
)

if TYPE_CHECKING:
    import psycopg2
    from psycopg2 import sql
else:
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        psycopg2 = None
        sql = None


def _check_existing_postgresql(port: str, port_int: int, db_url: str) -> Optional[bool]:
    """
    Check if PostgreSQL is already running.

    Returns:
        True if using existing instance, False if port conflict, None if need to start
    """
    port_in_use, pid = check_port_in_use('localhost', port_int)
    if port_in_use:
        if verify_postgresql_on_port('localhost', port_int, db_url):
            print(f"[POSTGRESQL] Port {port} is in use by existing PostgreSQL instance (PID: {pid})")
            print("[POSTGRESQL] ✓ Using existing PostgreSQL server")
            return True
        if pid is None:
            postgres_pids = []
            if sys.platform != 'win32':
                try:
                    result = subprocess.run(
                        ['pgrep', '-f', 'postgres.*-D'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False
                    )
                    if result.stdout.strip():
                        postgres_pids = [
                            p.strip() for p in result.stdout.strip().split('\n') if p.strip()
                        ]
                except Exception:
                    pass
            if postgres_pids:
                print(f"[ERROR] Port {port} is in use but no process found on port")
                print(f"        Found PostgreSQL processes: {', '.join(postgres_pids)}")
                print("        These processes may be using the port in a different namespace.")
                print("        Solutions:")
                print(f"        1. Kill PostgreSQL processes: kill -9 {' '.join(postgres_pids)}")
                print(f"        2. Check port usage: sudo netstat -tlnp | grep :{port}")
                print("        3. Use a different port: Set POSTGRESQL_PORT=<different_port> in .env")
            else:
                print(f"[ERROR] Port {port} is in use but no process found (may be in different namespace)")
                print("        This can happen in WSL or Docker environments.")
                print("        Solutions:")
                print(f"        1. Check for processes: lsof -i :{port} or sudo netstat -tlnp | grep :{port}")
                print("        2. Try killing any PostgreSQL processes: pkill -9 postgres")
                print("        3. Wait a few seconds for TIME_WAIT sockets to clear")
                print("        4. Use a different port: Set POSTGRESQL_PORT=<different_port> in .env")
            print("        Application cannot start without PostgreSQL.")
            sys.exit(1)
        else:
            print(f"[ERROR] Port {port} is in use but not by PostgreSQL")
            print(f"        Process using port: PID {pid}")
            print("        Stop the process using this port or use a different port")
            cmd = (f"        Check: lsof -i :{port} (Linux/Mac) or "
                   f"netstat -ano | findstr :{port} (Windows)")
            print(cmd)
            sys.exit(1)

    if db_url and 'postgresql' in db_url:
        try:
            conn = psycopg2.connect(db_url, connect_timeout=2)
            conn.close()
            try:
                print("[POSTGRESQL] PostgreSQL server is already running")
                print("[POSTGRESQL] Using existing PostgreSQL instance")
            except (ValueError, OSError):
                pass
            return True
        except Exception:
            pass

    return None


def _check_systemd_service(db_url: str) -> Optional[bool]:
    """
    Check if PostgreSQL systemd service is active.

    Returns:
        True if using systemd service, None otherwise
    """
    postgresql_managed = os.getenv('POSTGRESQL_MANAGED_BY_APP', 'true').lower() not in ('false', '0', 'no')
    if not postgresql_managed:
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
                    for i in range(10):
                        try:
                            conn = psycopg2.connect(db_url, connect_timeout=2)
                            conn.close()
                            try:
                                print("[POSTGRESQL] PostgreSQL systemd service is ready")
                            except (ValueError, OSError):
                                pass
                            return True
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
    return None


def _build_postgres_command(
    postgres_binary: str,
    data_path: Path,
    socket_dir: Path
) -> list[str]:
    """
    Build PostgreSQL server command with appropriate user wrapping if running as root.

    Args:
        postgres_binary: Path to postgres binary
        data_path: PostgreSQL data directory
        socket_dir: Socket directory

    Returns:
        Command list for subprocess
    """
    socket_dir_abs = str(socket_dir.resolve())
    postgres_cmd = [
        postgres_binary,
        '-D', str(data_path),
        '-c', f'unix_socket_directories={socket_dir_abs}',
        '-c', 'listen_addresses=127.0.0.1'
    ]

    # Check if running as root - if so, run postgres server as postgres user
    is_root = False
    postgres_user_exists = False
    if sys.platform != 'win32':
        try:
            is_root = os.geteuid() == 0
        except AttributeError:
            is_root = False

    if is_root:
        # Check if postgres user exists
        try:
            result = subprocess.run(
                ['id', '-u', 'postgres'],
                capture_output=True,
                timeout=2,
                check=False
            )
            postgres_user_exists = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        if postgres_user_exists:
            # Use sudo -u postgres to run the server
            try:
                sudo_result = subprocess.run(
                    ['which', 'sudo'],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                if sudo_result.returncode == 0:
                    postgres_cmd = ['sudo', '-u', 'postgres'] + postgres_cmd
                    try:
                        msg = ("[POSTGRESQL] Running PostgreSQL server as 'postgres' user "
                               "(running as root)")
                        print(msg)
                    except (ValueError, OSError):
                        pass
                else:
                    # Fallback to runuser if available
                    runuser_result = subprocess.run(
                        ['which', 'runuser'],
                        capture_output=True,
                        timeout=2,
                        check=False
                    )
                    if runuser_result.returncode == 0:
                        cmd_str = ' '.join(shlex.quote(str(arg)) for arg in postgres_cmd)
                        postgres_cmd = ['runuser', '-u', 'postgres', '--', 'sh', '-c', cmd_str]
                        try:
                            msg = ("[POSTGRESQL] Running PostgreSQL server as 'postgres' user "
                                   "(running as root)")
                            print(msg)
                        except (ValueError, OSError):
                            pass
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    return postgres_cmd


def _wait_for_postgresql_ready(port: str) -> str:
    """
    Wait for PostgreSQL server to become ready.

    Returns:
        Superuser name to use for connections
    """
    last_error = None
    superuser_name = 'postgres'
    current_user = os.getenv('USER') or os.getenv('USERNAME') or 'postgres'

    for i in range(30):
        try:
            conn = psycopg2.connect(
                f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
                connect_timeout=2
            )
            conn.close()
            break
        except Exception as e:
            if 'role "postgres" does not exist' in str(e) and current_user != 'postgres':
                try:
                    conn = psycopg2.connect(
                        f'postgresql://{current_user}@127.0.0.1:{port}/postgres',
                        connect_timeout=2
                    )
                    conn.close()
                    superuser_name = current_user
                    try:
                        msg = (f"[POSTGRESQL] Using current Linux user '{current_user}' "
                               "as superuser (postgres role not found)")
                        print(msg)
                    except (ValueError, OSError):
                        pass
                    break
                except Exception:
                    pass
            last_error = e
            if i < 29:
                time.sleep(1)
            else:
                raise RuntimeError(f"PostgreSQL not ready after 30 seconds: {last_error}")

    return superuser_name


def _create_database_and_user(
    superuser_name: str,
    port: str,
    user: str,
    password: str,
    database: str
) -> None:
    """Create database and user if they don't exist."""
    try:
        if sql is None:
            raise RuntimeError("psycopg2.sql not available")

        conn = psycopg2.connect(
            f'postgresql://{superuser_name}@127.0.0.1:{port}/postgres',
            connect_timeout=5
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Ensure "postgres" role exists (required for PostgreSQL)
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'postgres'")
        if not cursor.fetchone():
            try:
                # Create postgres role as superuser
                cursor.execute("CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN")
                try:
                    print("[POSTGRESQL] Created missing 'postgres' role")
                except (ValueError, OSError):
                    pass
            except Exception as role_error:
                # If we can't create postgres role, log warning but continue
                try:
                    print(f"[WARNING] Could not create 'postgres' role: {role_error}")
                except (ValueError, OSError):
                    pass

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
    except Exception as e:
        try:
            print(f"[WARNING] Failed to create database/user (may already exist): {e}")
        except (ValueError, OSError):
            pass


def start_postgresql_server(server_state) -> Optional[subprocess.Popen[bytes]]:
    """
    Start PostgreSQL server as a subprocess if not already running (REQUIRED).

    Assumes PostgreSQL installation has been verified. Checks if PostgreSQL is running,
    and if not, attempts to start it. Application will exit if PostgreSQL cannot be started.

    For subprocess mode:
    - Initializes data directory with initdb if needed
    - Generates postgresql.conf and pg_hba.conf
    - Creates database/user on first startup
    - Starts postgres binary as subprocess

    Args:
        server_state: ServerState instance to update

    Returns:
        Optional[subprocess.Popen[bytes]]: PostgreSQL process or None if using existing
    """
    if psycopg2 is None:
        print("[ERROR] psycopg2 is not available")
        print("        Install with: pip install psycopg2-binary")
        print("        Application cannot start without PostgreSQL.")
        sys.exit(1)

    port = os.getenv('POSTGRESQL_PORT', '5432')
    port_int = int(port)
    db_url = os.getenv('DATABASE_URL', '')
    user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
    password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
    database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

    # Check if PostgreSQL is already running
    existing = _check_existing_postgresql(port, port_int, db_url)
    if existing is True:
        return None

    # Check systemd service
    existing = _check_systemd_service(db_url)
    if existing is True:
        return None

    # Find PostgreSQL binaries
    postgres_binary, initdb_binary = find_postgres_binaries()
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

    # Resolve data path
    data_path, _ = resolve_data_path()

    # Initialize data directory if needed
    initialize_postgresql_data_directory(initdb_binary, data_path)

    # Set up configuration files
    socket_dir = setup_socket_directory(data_path)
    update_postgresql_conf(data_path, port, socket_dir)
    create_pg_hba_conf(data_path)

    # Clean up stale PID file before starting
    cleanup_stale_pid_file(data_path)

    try:
        print("[POSTGRESQL] Starting PostgreSQL server as subprocess...")
    except (ValueError, OSError):
        pass

    if not socket_dir.exists():
        socket_dir.mkdir(parents=True, exist_ok=True)
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

    socket_dir_abs = str(socket_dir.resolve())

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

    postgres_env = os.environ.copy()
    postgres_env['PGHOST'] = socket_dir_abs

    postgres_cmd = _build_postgres_command(postgres_binary, data_path, socket_dir)

    try:
        print(f"[POSTGRESQL] Socket directory: {socket_dir_abs}")
    except (ValueError, OSError):
        pass

    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        postgres_log = logs_dir / 'postgresql.log'

        # If running as postgres user, ensure logs directory is writable
        # If not, use PostgreSQL data directory for logs
        is_root = False
        postgres_user_exists = False
        if sys.platform != 'win32':
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                is_root = False

        if is_root:
            try:
                result = subprocess.run(
                    ['id', '-u', 'postgres'],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                postgres_user_exists = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        if is_root and postgres_user_exists:
            try:
                # Test if postgres user can write to logs directory
                test_result = subprocess.run(
                    ['sudo', '-u', 'postgres', 'test', '-w', str(logs_dir)],
                    check=False,
                    timeout=2,
                    capture_output=True
                )
                if test_result.returncode != 0:
                    # Use PostgreSQL data directory for logs instead
                    postgres_log = data_path / 'postgresql.log'
                    try:
                        print(f"[POSTGRESQL] Using PostgreSQL data directory for logs: {postgres_log}")
                    except (ValueError, OSError):
                        pass
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        postgres_stdout = (
            open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stdout
        )
        postgres_stderr = (
            open(postgres_log, 'a', encoding='utf-8') if sys.platform != 'win32' else sys.stderr
        )

        server_state.postgresql_process = subprocess.Popen(
            postgres_cmd,
            stdout=postgres_stdout,
            stderr=postgres_stderr,
            cwd=str(data_path),
            env=postgres_env,
            start_new_session=sys.platform != 'win32',
            bufsize=1,
        )

        def stop_wrapper():
            stop_postgresql_server(server_state)
        atexit.register(stop_wrapper)

        # Wait for PostgreSQL to become ready
        superuser_name = 'postgres'
        try:
            superuser_name = _wait_for_postgresql_ready(port)
        except RuntimeError as e:
            if server_state.postgresql_process.poll() is not None:
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
                try:
                    print("[ERROR] PostgreSQL server process started but not responding after 30 seconds")
                    print(f"[ERROR] Last connection error: {e}")
                    print(f"[ERROR] Check PostgreSQL logs: tail -f {postgres_log}")
                    print(f"[ERROR] Data directory: {data_path}")
                    cmd = (f"[ERROR] Try manually: psql -U {superuser_name} -h 127.0.0.1 "
                           f"-p {port} -d postgres")
                    print(cmd)
                except (ValueError, OSError):
                    pass
            sys.exit(1)

        # Create database and user
        _create_database_and_user(superuser_name, port, user, password, database)

        # Construct PostgreSQL URL for connection test if DATABASE_URL is SQLite or invalid
        test_db_url = db_url
        if (not test_db_url or 'sqlite' in test_db_url.lower() or
                'postgresql' not in test_db_url.lower()):
            # Construct from individual PostgreSQL settings
            test_db_url = f'postgresql://{user}:{password}@127.0.0.1:{port}/{database}'

        try:
            conn = psycopg2.connect(test_db_url, connect_timeout=5)
            conn.close()
            try:
                pid = server_state.postgresql_process.pid
                print(f"[POSTGRESQL] Server started successfully (PID: {pid})")
                if sys.platform != 'win32':
                    print(f"[POSTGRESQL] Logs: {postgres_log}")
            except (ValueError, OSError):
                pass
            return server_state.postgresql_process
        except Exception as e:
            try:
                print(f"[ERROR] PostgreSQL server started but connection test failed: {e}")
                url_part = test_db_url.split('@')[0] if '@' in test_db_url else test_db_url
                print(f"        Connection URL used: {url_part}@***")
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


def stop_postgresql_server(server_state) -> None:
    """Stop the PostgreSQL server subprocess"""
    if server_state.postgresql_process is not None:
        try:
            print("[POSTGRESQL] Stopping PostgreSQL server...")
        except (ValueError, OSError):
            pass
        try:
            if sys.platform == 'win32':
                server_state.postgresql_process.terminate()
            else:
                if hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                    pgid = os.getpgid(server_state.postgresql_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    server_state.postgresql_process.terminate()
            server_state.postgresql_process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
            try:
                print(f"[POSTGRESQL] Error stopping server: {e}")
            except (ValueError, OSError):
                pass
            try:
                server_state.postgresql_process.kill()
            except (OSError, ProcessLookupError):
                pass
        server_state.postgresql_process = None
        try:
            print("[POSTGRESQL] Server stopped")
        except (ValueError, OSError):
            pass
