"""
PostgreSQL server management for MindGraph application.

Handles starting and stopping PostgreSQL server processes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import atexit
import logging
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import psycopg
from psycopg import sql

from services.infrastructure.process._port_utils import check_port_in_use
from services.infrastructure.process._process_io import (
    close_resource_stack,
    launch_background_process,
    open_append_text,
)
from services.infrastructure.process._postgresql_config import (
    create_pg_hba_conf,
    setup_socket_directory,
    update_postgresql_conf,
)
from services.infrastructure.process._postgresql_helpers import (
    cleanup_stale_pid_file,
    try_database_url_connect,
    verify_postgresql_on_port,
)
from services.infrastructure.process._postgresql_external import (
    ensure_local_external_postgresql,
)
from services.infrastructure.process._postgresql_init import (
    initialize_postgresql_data_directory,
)
from services.infrastructure.process._postgresql_paths import (
    find_postgres_binaries,
    resolve_app_managed_data_path,
)
from services.infrastructure.process._postgresql_runtime import (
    PostgresRuntimeConfig,
    load_postgres_runtime_config,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, PG_CONNECT_ERRORS


logger = logging.getLogger(__name__)


def _check_existing_postgresql(config: PostgresRuntimeConfig) -> Optional[bool]:
    """
    Check if PostgreSQL is already running.

    Returns:
        True if using existing instance, False if port conflict, None if need to start
    """
    host = config.connection_probe_host
    port = config.port_str
    port_int = config.port
    db_url = config.database_url

    if not config.is_local:
        if try_database_url_connect(config, timeout=2):
            try:
                print("[POSTGRESQL] Remote PostgreSQL from DATABASE_URL is reachable")
                print(f"[POSTGRESQL] Using {config.host}:{config.port}/{config.database}")
            except (ValueError, OSError):
                pass
            return True
        return None

    port_in_use, pid = check_port_in_use(host, port_int)
    if port_in_use:
        if verify_postgresql_on_port(host, port_int, db_url):
            print(f"[POSTGRESQL] Port {port} is in use by existing PostgreSQL instance (PID: {pid})")
            print("[POSTGRESQL] ✓ Using existing PostgreSQL server")
            if db_url and "postgresql" in db_url:
                try:
                    with psycopg.connect(db_url, connect_timeout=2):
                        pass
                except (*PG_CONNECT_ERRORS,) as exc:
                    if "password authentication failed" in str(exc).lower():
                        print(
                            "[POSTGRESQL] Server is up but DATABASE_URL credentials failed. "
                            "Fix .env (roles/passwords) or run scripts/db/run_migrations.py option 4."
                        )
                    else:
                        logger.debug("DATABASE_URL probe after reuse: %s", exc)
            return True
        if pid is None:
            postgres_pids = []
            if sys.platform != "win32":
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", "postgres.*-D"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    if result.stdout.strip():
                        postgres_pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.debug("PostgreSQL process search (pgrep) failed: %s", exc)
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
            cmd = f"        Check: lsof -i :{port} (Linux/Mac) or netstat -ano | findstr :{port} (Windows)"
            print(cmd)
            sys.exit(1)

    if db_url and "postgresql" in db_url:
        try:
            with psycopg.connect(db_url, connect_timeout=2):
                try:
                    print("[POSTGRESQL] PostgreSQL server is already running")
                    print("[POSTGRESQL] Using existing PostgreSQL instance")
                except (ValueError, OSError):
                    pass
            return True
        except (*PG_CONNECT_ERRORS,) as exc:
            logger.debug("PostgreSQL connection check failed: %s", exc)

    return None


def _build_postgres_command(postgres_binary: str, data_path: Path, socket_dir: Path) -> list[str]:
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
        "-D",
        str(data_path),
        "-c",
        f"unix_socket_directories={socket_dir_abs}",
        "-c",
        "listen_addresses=127.0.0.1",
    ]

    # Check if running as root - if so, run postgres server as postgres user
    is_root = False
    postgres_user_exists = False
    if sys.platform != "win32":
        try:
            is_root = os.geteuid() == 0
        except AttributeError:
            is_root = False

    if is_root:
        # Check if postgres user exists
        try:
            result = subprocess.run(["id", "-u", "postgres"], capture_output=True, timeout=2, check=False)
            postgres_user_exists = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        if postgres_user_exists:
            # Use sudo -u postgres to run the server
            try:
                sudo_result = subprocess.run(["which", "sudo"], capture_output=True, timeout=2, check=False)
                if sudo_result.returncode == 0:
                    postgres_cmd = ["sudo", "-u", "postgres"] + postgres_cmd
                    try:
                        msg = "[POSTGRESQL] Running PostgreSQL server as 'postgres' user (running as root)"
                        print(msg)
                    except (ValueError, OSError):
                        pass
                else:
                    # Fallback to runuser if available
                    runuser_result = subprocess.run(
                        ["which", "runuser"],
                        capture_output=True,
                        timeout=2,
                        check=False,
                    )
                    if runuser_result.returncode == 0:
                        cmd_str = " ".join(shlex.quote(str(arg)) for arg in postgres_cmd)
                        postgres_cmd = [
                            "runuser",
                            "-u",
                            "postgres",
                            "--",
                            "sh",
                            "-c",
                            cmd_str,
                        ]
                        try:
                            msg = "[POSTGRESQL] Running PostgreSQL server as 'postgres' user (running as root)"
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
    superuser_name = "postgres"
    current_user = os.getenv("USER") or os.getenv("USERNAME") or "postgres"

    for i in range(30):
        try:
            with psycopg.connect(
                f"postgresql://{superuser_name}@127.0.0.1:{port}/postgres",
                connect_timeout=2,
            ):
                break
        except (*PG_CONNECT_ERRORS,) as e:
            if 'role "postgres" does not exist' in str(e) and current_user != "postgres":
                try:
                    with psycopg.connect(
                        f"postgresql://{current_user}@127.0.0.1:{port}/postgres",
                        connect_timeout=2,
                    ):
                        superuser_name = current_user
                        try:
                            msg = (
                                f"[POSTGRESQL] Using current Linux user '{current_user}' "
                                "as superuser (postgres role not found)"
                            )
                            print(msg)
                        except (ValueError, OSError):
                            pass
                    break
                except (*PG_CONNECT_ERRORS,) as exc:
                    logger.debug("PostgreSQL superuser connection attempt failed: %s", exc)
            last_error = e
            if i < 29:
                time.sleep(1)
            else:
                raise RuntimeError(f"PostgreSQL not ready after 30 seconds: {last_error}") from last_error

    return superuser_name


def _create_database_and_user(superuser_name: str, port: str, user: str, password: str, database: str) -> None:
    """Create database and user if they don't exist, granting CREATEDB."""
    try:
        with psycopg.connect(
            f"postgresql://{superuser_name}@127.0.0.1:{port}/postgres",
            connect_timeout=5,
        ) as conn:
            conn.autocommit = True
            cursor = conn.cursor()

            # Ensure "postgres" role exists
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'postgres'")
            if not cursor.fetchone():
                try:
                    cursor.execute("CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN")
                    logger.info("[PGManager] Created missing 'postgres' role")
                except BACKGROUND_INFRA_ERRORS as role_error:
                    logger.warning("[PGManager] Could not create 'postgres' role: %s", role_error)

            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL("CREATE USER {} WITH PASSWORD %s CREATEDB").format(sql.Identifier(user)),
                    (password,),
                )
                logger.info("[PGManager] Created user: %s", user)
            else:
                cursor.execute(sql.SQL("ALTER USER {} CREATEDB").format(sql.Identifier(user)))
                logger.info("[PGManager] Granted CREATEDB to existing user: %s", user)

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(user))
                )
                logger.info("[PGManager] Created database: %s", database)

            cursor.close()
    except (*PG_CONNECT_ERRORS,) as exc:
        logger.warning(
            "[PGManager] DB provisioning failed (superuser='%s'): %s",
            superuser_name,
            exc,
        )


def _app_user_has_createdb(port: str, user: str, password: str, database: str) -> bool:
    """Return True if the app user already has CREATEDB privilege."""
    try:
        with psycopg.connect(
            f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}",
            connect_timeout=5,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user")
            row = cursor.fetchone()
            cursor.close()
            return bool(row and row[0])
    except (*PG_CONNECT_ERRORS,):
        return False


def _ensure_createdb_privilege(port: str, user: str, password: str, database: str) -> None:
    """Ensure the app user has CREATEDB when PostgreSQL is already running.

    Skipped entirely once the privilege is granted (it is permanent).
    On first run: writes trust pg_hba.conf, reloads via SIGHUP, then
    grants CREATEDB through the postgres superuser (WSL / Ubuntu only).
    """
    if _app_user_has_createdb(port, user, password, database):
        return

    logger.info("[PGManager] %s lacks CREATEDB — granting now (first-time only)", user)
    data_path, _ = resolve_app_managed_data_path()
    create_pg_hba_conf(data_path)

    postmaster_pid_file = data_path / "postmaster.pid"
    if not postmaster_pid_file.exists():
        logger.warning(
            "[PGManager] postmaster.pid not found in %s — cannot auto-grant CREATEDB. "
            'Run manually in WSL/Ubuntu: sudo -u postgres psql -c "ALTER USER %s CREATEDB;"',
            data_path,
            user,
        )
        return

    try:
        with open(postmaster_pid_file, "r", encoding="utf-8") as pid_f:
            pid = int(pid_f.readline().strip())
        sighup = getattr(signal, "SIGHUP", None)
        if sighup is None:
            logger.warning("[PGManager] SIGHUP not available on this platform; skipping pg_hba.conf reload")
            return
        os.kill(pid, sighup)
        time.sleep(0.5)
        logger.debug("[PGManager] Reloaded pg_hba.conf (SIGHUP → PID %d)", pid)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[PGManager] pg_hba.conf reload failed: %s", exc)
        return

    _create_database_and_user("postgres", port, user, password, database)


def _log_runtime_mode(config: PostgresRuntimeConfig) -> None:
    try:
        print(f"[POSTGRESQL] Startup mode: {config.mode_label}")
        print(f"[POSTGRESQL] DATABASE_URL user: {config.runtime_user} @ {config.host}:{config.port}/{config.database}")
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
    config = load_postgres_runtime_config()
    _log_runtime_mode(config)

    port = config.port_str
    user = config.provision_user
    password = config.provision_password
    database = config.database

    existing = _check_existing_postgresql(config)
    if existing is True:
        if config.spawn_subprocess:
            _ensure_createdb_privilege(port, user, password, database)
        return None

    if not config.spawn_subprocess:
        if config.is_local:
            if not ensure_local_external_postgresql(config):
                sys.exit(1)
            return None
        if try_database_url_connect(config, timeout=5):
            return None
        try:
            print("[ERROR] Remote PostgreSQL from DATABASE_URL is not reachable.")
            print(f"        Host: {config.host}:{config.port}")
            print(f"        Runtime user: {config.runtime_user}")
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # App-managed subprocess mode (legacy ``mindgraph_user`` on localhost)
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
    data_path, _ = resolve_app_managed_data_path()

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

    test_file = socket_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except BACKGROUND_INFRA_ERRORS as e:
        try:
            print(f"[ERROR] Cannot write to socket directory {socket_dir_abs}: {e}")
            print(f"        Fix permissions: chmod 700 {socket_dir_abs}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    postgres_env = os.environ.copy()
    postgres_env["PGHOST"] = socket_dir_abs

    postgres_cmd = _build_postgres_command(postgres_binary, data_path, socket_dir)

    try:
        print(f"[POSTGRESQL] Socket directory: {socket_dir_abs}")
    except (ValueError, OSError):
        pass

    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        postgres_log = logs_dir / "postgresql.log"

        # If running as postgres user, ensure logs directory is writable
        # If not, use PostgreSQL data directory for logs
        is_root = False
        postgres_user_exists = False
        if sys.platform != "win32":
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                is_root = False

        if is_root:
            try:
                result = subprocess.run(
                    ["id", "-u", "postgres"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                postgres_user_exists = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        if is_root and postgres_user_exists:
            try:
                # Test if postgres user can write to logs directory
                test_result = subprocess.run(
                    ["sudo", "-u", "postgres", "test", "-w", str(logs_dir)],
                    check=False,
                    timeout=2,
                    capture_output=True,
                )
                if test_result.returncode != 0:
                    # Use PostgreSQL data directory for logs instead
                    postgres_log = data_path / "postgresql.log"
                    try:
                        print(f"[POSTGRESQL] Using PostgreSQL data directory for logs: {postgres_log}")
                    except (ValueError, OSError):
                        pass
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        if sys.platform != "win32":
            server_state.postgresql_stdout_file = open_append_text(postgres_log)
            server_state.postgresql_stderr_file = server_state.postgresql_stdout_file
            postgres_stdout = server_state.postgresql_stdout_file
            postgres_stderr = server_state.postgresql_stderr_file
        else:
            postgres_stdout = sys.stdout
            postgres_stderr = sys.stderr

        launch_background_process(
            server_state,
            "postgresql_resource_stack",
            "postgresql_process",
            postgres_cmd,
            stdout=postgres_stdout,
            stderr=postgres_stderr,
            cwd=str(data_path),
            env=postgres_env,
            start_new_session=True,
            bufsize=1,
        )

        def stop_wrapper():
            stop_postgresql_server(server_state)

        stop_on_exit = os.getenv("MINDGRAPH_STOP_POSTGRES_ON_EXIT", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if stop_on_exit:
            atexit.register(stop_wrapper)
        else:
            try:
                pid = server_state.postgresql_process.pid
                print(
                    f"[POSTGRESQL] Leaving server running (PID: {pid}). "
                    "Stop manually or set MINDGRAPH_STOP_POSTGRES_ON_EXIT=1 to stop on exit."
                )
            except (AttributeError, ValueError, OSError):
                pass

        # Wait for PostgreSQL to become ready
        superuser_name = "postgres"
        try:
            superuser_name = _wait_for_postgresql_ready(port)
        except RuntimeError as e:
            if server_state.postgresql_process.poll() is not None:
                try:
                    if postgres_log.exists():
                        with open(postgres_log, "r", encoding="utf-8") as f:
                            log_lines = f.readlines()
                            if log_lines:
                                last_log_lines = "\n".join(log_lines[-10:])
                                print("[ERROR] PostgreSQL server process terminated")
                                print(f"[ERROR] Last log entries:\n{last_log_lines}")
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.debug("PostgreSQL log file read failed: %s", exc)
            else:
                try:
                    print("[ERROR] PostgreSQL server process started but not responding after 30 seconds")
                    print(f"[ERROR] Last connection error: {e}")
                    print(f"[ERROR] Check PostgreSQL logs: tail -f {postgres_log}")
                    print(f"[ERROR] Data directory: {data_path}")
                    cmd = f"[ERROR] Try manually: psql -U {superuser_name} -h 127.0.0.1 -p {port} -d postgres"
                    print(cmd)
                except (ValueError, OSError):
                    pass
            sys.exit(1)

        # Create database and user
        _create_database_and_user(superuser_name, port, user, password, database)

        # Verify app-managed credentials; DATABASE_URL (e.g. mindgraph_app) is checked after RLS bootstrap.
        test_db_url = f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}"

        try:
            with psycopg.connect(test_db_url, connect_timeout=5):
                try:
                    pid = server_state.postgresql_process.pid
                    print(f"[POSTGRESQL] Server started successfully (PID: {pid})")
                    if sys.platform != "win32":
                        print(f"[POSTGRESQL] Logs: {postgres_log}")
                except (ValueError, OSError):
                    pass
            return server_state.postgresql_process
        except (*PG_CONNECT_ERRORS,) as e:
            try:
                print(f"[ERROR] PostgreSQL server started but connection test failed: {e}")
                url_part = test_db_url.split("@", maxsplit=1)[0] if "@" in test_db_url else test_db_url
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
            if sys.platform == "win32":
                server_state.postgresql_process.terminate()
            else:
                if hasattr(os, "getpgid") and hasattr(os, "killpg"):
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
        if server_state.postgresql_stdout_file is not None:
            try:
                server_state.postgresql_stdout_file.close()
            except (OSError, ValueError):
                pass
            server_state.postgresql_stdout_file = None
            server_state.postgresql_stderr_file = None
        close_resource_stack(server_state, "postgresql_resource_stack")
        server_state.postgresql_process = None
        try:
            print("[POSTGRESQL] Server stopped")
        except (ValueError, OSError):
            pass
