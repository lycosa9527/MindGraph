"""
Start or reuse local system/external PostgreSQL (never ``initdb``).

Used when ``DATABASE_URL`` selects an RLS runtime role or ``POSTGRESQL_MANAGED_BY_APP=false``.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Optional

from services.infrastructure.process._port_utils import check_port_in_use
from services.infrastructure.process._postgresql_helpers import postgresql_accepts_connections
from services.infrastructure.process._postgresql_paths import (
    find_system_postgresql_cluster,
    is_initialized_cluster,
    linux_native_cluster_dir,
)
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def try_start_system_postgresql(port_int: int) -> bool:
    """Start or reuse the distro PostgreSQL cluster listening on ``port_int``."""
    if sys.platform == "win32":
        return False

    cluster_info = find_system_postgresql_cluster(port_int)
    if cluster_info is None:
        return False

    main_path, version = cluster_info
    host = "127.0.0.1"
    if postgresql_accepts_connections(host, port_int):
        try:
            print("[POSTGRESQL] ✓ System PostgreSQL is already running")
            print(f"[POSTGRESQL] Data directory: {main_path}")
        except (ValueError, OSError):
            pass
        return True

    port_in_use, _pid = check_port_in_use(host, port_int)
    if port_in_use:
        return False

    start_commands = (
        ["systemctl", "start", "postgresql"],
        ["pg_ctlcluster", version, "main", "start"],
    )
    started = False
    for cmd in start_commands:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60, check=False, text=True)
            if result.returncode == 0:
                started = True
                break
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    if not started:
        return False

    for _ in range(15):
        if postgresql_accepts_connections(host, port_int):
            try:
                print("[POSTGRESQL] ✓ Started system PostgreSQL")
                print(f"[POSTGRESQL] Data directory: {main_path}")
            except (ValueError, OSError):
                pass
            return True
        time.sleep(1)
    return False


def app_managed_cluster_blocking_port(port_int: int) -> tuple[bool, Optional[int]]:
    """True when port is held by postgres using ``~/.mindgraph/postgresql``."""
    host = "127.0.0.1"
    port_in_use, pid = check_port_in_use(host, port_int)
    if not port_in_use:
        return False, pid

    linux_native = linux_native_cluster_dir()
    if not is_initialized_cluster(linux_native):
        return False, pid

    pid_file = linux_native / "postmaster.pid"
    if not pid_file.exists():
        return False, pid

    try:
        with open(pid_file, "r", encoding="utf-8") as pid_handle:
            file_pid = int(pid_handle.readline().strip())
    except (OSError, ValueError):
        return False, pid

    if pid is not None and file_pid != pid:
        return False, pid

    return True, file_pid if pid is None else pid


def print_system_cluster_startup_help(config: PostgresRuntimeConfig) -> None:
    """Tell the operator how to start the distro PostgreSQL cluster manually."""
    cluster_info = find_system_postgresql_cluster(config.port)
    main_path = cluster_info[0] if cluster_info else None
    try:
        print("[ERROR] PostgreSQL is configured for connect-only mode but the server is not reachable.")
        print(f"        Mode: {config.mode_label}")
        print(f"        DATABASE_URL host/port: {config.host}:{config.port}")
        if main_path is not None:
            print(f"        System data directory: {main_path}")
            print("        Try: sudo systemctl start postgresql")
        else:
            print("        Start your PostgreSQL service or fix DATABASE_URL, then retry.")
        print("        Application cannot start without PostgreSQL.")
    except (ValueError, OSError):
        pass


def print_app_managed_blocking_external_help(config: PostgresRuntimeConfig, pid: Optional[int]) -> None:
    """Explain that a throwaway app-managed cluster is blocking the intended server."""
    cluster_info = find_system_postgresql_cluster(config.port)
    main_path = cluster_info[0] if cluster_info else None
    linux_native = linux_native_cluster_dir()
    pid_hint = str(pid) if pid is not None else "<postgres PID>"
    try:
        print(
            f"[ERROR] Port {config.port} is used by an app-managed PostgreSQL cluster, "
            f"but DATABASE_URL expects {config.mode_label}."
        )
        print(f"        Runtime user from DATABASE_URL: {config.runtime_user}")
        print(f"        App-managed data directory: {linux_native}")
        if main_path is not None:
            print(f"        System cluster (expected data): {main_path}")
        print(f"        Stop the app-managed server: kill {pid_hint}")
        print("        Or: pkill -f 'postgres.*-D.*\\.mindgraph/postgresql'")
        print("        Then: sudo systemctl start postgresql")
        print("        Application cannot start without PostgreSQL.")
    except (ValueError, OSError):
        pass


def ensure_local_external_postgresql(config: PostgresRuntimeConfig) -> bool:
    """
    Ensure a local connect-only PostgreSQL instance is up.

    Returns True when the port accepts connections or system service was started.
    """
    host = "127.0.0.1" if config.host in ("localhost", "127.0.0.1", "::1") else config.host
    if postgresql_accepts_connections(host, config.port):
        return True

    if try_start_system_postgresql(config.port):
        return True

    blocking, blocker_pid = app_managed_cluster_blocking_port(config.port)
    if blocking:
        print_app_managed_blocking_external_help(config, blocker_pid)
        return False

    print_system_cluster_startup_help(config)
    return False
