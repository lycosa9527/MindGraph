"""
Start or reuse local system/external PostgreSQL (never ``initdb``).

Used when ``DATABASE_URL`` selects an RLS runtime role or ``POSTGRESQL_MANAGED_BY_APP=false``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from services.infrastructure.process._port_utils import check_port_in_use
from services.infrastructure.process._postgresql_discovery import (
    RankedCluster,
    clusters_on_port,
    discover_ranked_cluster_details,
)
from services.infrastructure.process._postgresql_helpers import (
    cleanup_stale_pid_file,
    launch_command_as_postgres,
    postgresql_accepts_connections,
)
from services.infrastructure.process._postgresql_paths import (
    find_postgres_binaries,
    find_system_postgresql_cluster,
    is_initialized_cluster,
    read_cluster_port,
)
from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig

logger = logging.getLogger(__name__)


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


def _find_pg_ctl_binary() -> Optional[str]:
    postgres_binary, _initdb = find_postgres_binaries()
    if not postgres_binary:
        return None
    pg_ctl = os.path.join(os.path.dirname(postgres_binary), "pg_ctl")
    if os.path.exists(pg_ctl) and os.access(pg_ctl, os.X_OK):
        return pg_ctl
    return None


def _persistent_cluster_log_path(data_path: Path) -> Path:
    preferred = Path("/var/log/postgresql") / f"postgresql-{data_path.name}.log"
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        return data_path / "postgresql.log"


def try_start_persistent_cluster(data_path: Path, port_int: int) -> bool:
    """Start an existing MindGraph data directory with ``pg_ctl`` (no ``initdb``)."""
    if sys.platform == "win32":
        return False
    if not is_initialized_cluster(data_path):
        return False
    if read_cluster_port(data_path) != port_int:
        return False

    host = "127.0.0.1"
    if postgresql_accepts_connections(host, port_int):
        return True

    port_in_use, _pid = check_port_in_use(host, port_int)
    if port_in_use:
        return False

    pg_ctl = _find_pg_ctl_binary()
    if pg_ctl is None:
        return False

    cleanup_stale_pid_file(data_path)
    log_path = _persistent_cluster_log_path(data_path)
    cmd = [pg_ctl, "-D", str(data_path), "-l", str(log_path), "start"]
    launch_cmd = launch_command_as_postgres(cmd)

    try:
        result = subprocess.run(
            launch_cmd,
            capture_output=True,
            timeout=60,
            check=False,
            text=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.debug("pg_ctl start failed for %s: %s", data_path, exc)
        return False

    if result.returncode != 0:
        logger.debug(
            "pg_ctl start failed for %s (rc=%s): %s",
            data_path,
            result.returncode,
            result.stderr.strip(),
        )
        return False

    for _ in range(15):
        if postgresql_accepts_connections(host, port_int):
            try:
                print("[POSTGRESQL] ✓ Started MindGraph PostgreSQL cluster")
                print(f"[POSTGRESQL] Data directory: {data_path}")
            except (ValueError, OSError):
                pass
            return True
        time.sleep(1)
    return False


def try_start_ranked_clusters(ranked: list[RankedCluster], port_int: int) -> bool:
    """Start ranked clusters on ``port_int`` in order until one succeeds."""
    for item in clusters_on_port(ranked, port_int):
        if try_start_persistent_cluster(item.path, port_int):
            return True
    return False


def _persistent_cluster_pid_on_port(
    port_int: int,
    ranked: list[RankedCluster],
) -> tuple[bool, Optional[int], Optional[Path]]:
    """True when ``port_int`` is held by a discovered MindGraph cluster."""
    host = "127.0.0.1"
    port_in_use, pid = check_port_in_use(host, port_int)
    if not port_in_use:
        return False, pid, None

    for item in clusters_on_port(ranked, port_int):
        data_path = item.path
        pid_file = data_path / "postmaster.pid"
        if not pid_file.exists():
            continue
        try:
            with open(pid_file, "r", encoding="utf-8") as pid_handle:
                file_pid = int(pid_handle.readline().strip())
        except (OSError, ValueError):
            continue
        if pid is not None and file_pid != pid:
            continue
        return True, file_pid if pid is None else pid, data_path

    return False, pid, None


def print_system_cluster_startup_help(
    config: PostgresRuntimeConfig,
    ranked: list[RankedCluster],
) -> None:
    """Tell the operator how to start PostgreSQL manually."""
    cluster_info = find_system_postgresql_cluster(config.port)
    main_path = cluster_info[0] if cluster_info else None
    persistent_dirs = [item.path for item in clusters_on_port(ranked, config.port)]
    try:
        print("[ERROR] PostgreSQL is configured for connect-only mode but the server is not reachable.")
        print(f"        Mode: {config.mode_label}")
        print(f"        DATABASE_URL host/port: {config.host}:{config.port}")
        if main_path is not None:
            print(f"        System data directory: {main_path}")
            print("        Try: sudo systemctl start postgresql")
        if persistent_dirs:
            sample = persistent_dirs[0]
            log_path = _persistent_cluster_log_path(sample)
            print(f"        MindGraph data directory: {sample}")
            print(f"        Try: sudo -u postgres pg_ctl -D {sample} -l {log_path} start")
        if main_path is None and not persistent_dirs:
            print("        Start your PostgreSQL service or fix DATABASE_URL, then retry.")
        print("        Application cannot start without PostgreSQL.")
    except (ValueError, OSError):
        pass


def print_app_managed_blocking_external_help(
    config: PostgresRuntimeConfig,
    pid: Optional[int],
    data_path: Path,
) -> None:
    """Explain that a MindGraph cluster is blocking connect-only startup."""
    cluster_info = find_system_postgresql_cluster(config.port)
    main_path = cluster_info[0] if cluster_info else None
    pid_hint = str(pid) if pid is not None else "<postgres PID>"
    log_path = _persistent_cluster_log_path(data_path)
    try:
        print(
            f"[ERROR] Port {config.port} is used by a MindGraph PostgreSQL cluster, "
            f"but it is not accepting connections for {config.mode_label}."
        )
        print(f"        Runtime user from DATABASE_URL: {config.runtime_user}")
        print(f"        Data directory: {data_path}")
        if main_path is not None:
            print(f"        Registered system cluster (expected): {main_path}")
        print(f"        Inspect: sudo -u postgres pg_ctl -D {data_path} status")
        print(f"        Restart: sudo -u postgres pg_ctl -D {data_path} -l {log_path} restart")
        print(f"        Or stop the process: kill {pid_hint}")
        print("        Application cannot start without PostgreSQL.")
    except (ValueError, OSError):
        pass


def ensure_local_external_postgresql(config: PostgresRuntimeConfig) -> bool:
    """
    Ensure a local connect-only PostgreSQL instance is up.

    Returns True when the port accepts connections or a local cluster was started.
    """
    host = "127.0.0.1" if config.host in ("localhost", "127.0.0.1", "::1") else config.host
    if postgresql_accepts_connections(host, config.port):
        return True

    ranked = discover_ranked_cluster_details(config)
    on_port = clusters_on_port(ranked, config.port)
    verified = [item for item in on_port if item.has_database]

    if verified and try_start_ranked_clusters(verified, config.port):
        return True

    if try_start_system_postgresql(config.port):
        return True

    if try_start_ranked_clusters(ranked, config.port):
        return True

    blocking, blocker_pid, data_path = _persistent_cluster_pid_on_port(config.port, ranked)
    if blocking and data_path is not None:
        print_app_managed_blocking_external_help(config, blocker_pid, data_path)
        return False

    print_system_cluster_startup_help(config, ranked)
    return False
