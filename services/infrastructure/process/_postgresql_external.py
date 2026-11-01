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
from services.infrastructure.process._postgresql_cluster_choice import (
    announce_cluster_choice,
    choose_cluster,
    publish_cluster_env,
)
from services.infrastructure.process._postgresql_discovery import (
    RankedCluster,
    clusters_on_port,
    discover_ranked_cluster_details,
)
from services.infrastructure.process._postgresql_helpers import (
    cleanup_stale_pid_file,
    cluster_postmaster_pid,
    launch_command_as_postgres,
    postmaster_data_directory,
    postgresql_accepts_connections,
    try_database_url_connect,
)
from services.infrastructure.process._postgresql_paths import (
    find_postgres_binaries,
    find_system_postgresql_cluster,
    is_initialized_cluster,
    postgres_binary_for_cluster,
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


def _find_pg_ctl_binary(data_path: Optional[Path] = None) -> Optional[str]:
    """``pg_ctl`` matching ``data_path``'s major version, else the newest install."""
    postgres_binary = postgres_binary_for_cluster(data_path) if data_path is not None else None
    if not postgres_binary:
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
    port_in_use, pid = check_port_in_use(host, port_int)
    if port_in_use:
        own_pid = cluster_postmaster_pid(data_path)
        listener = postmaster_data_directory(pid) if pid is not None else None
        listener_is_ours = listener is not None and _paths_match(listener, data_path)
        if (own_pid is not None and pid == own_pid) or listener_is_ours:
            return True
        return False

    pg_ctl = _find_pg_ctl_binary(data_path)
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
            print(f"        Registered distro cluster: {main_path}")
        print(f"        Inspect: sudo -u postgres pg_ctl -D {data_path} status")
        print(f"        Restart: sudo -u postgres pg_ctl -D {data_path} -l {log_path} restart")
        print(f"        Or stop the process: kill {pid_hint}")
        print("        Application cannot start without PostgreSQL.")
    except (ValueError, OSError):
        pass


def _paths_match(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.normpath(str(left)) == os.path.normpath(str(right))


def _distro_unit(data_path: Path) -> Optional[str]:
    """Return ``postgresql@<version>-<name>`` for a distro cluster path."""
    version = data_path.parent.name
    name = data_path.name
    if not version.isdigit() or not name:
        return None
    if data_path.parent.parent != Path("/var/lib/postgresql"):
        return None
    return f"postgresql@{version}-{name}"


def _run_command(cmd: list[str], timeout: int = 60) -> bool:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        logger.debug("Command failed %s: %s", cmd, exc)
        return False
    if result.returncode != 0:
        logger.debug("Command failed %s rc=%s: %s", cmd, result.returncode, result.stderr.strip())
        return False
    return True


def _run_root(cmd: list[str], timeout: int = 60) -> bool:
    try:
        is_root = os.geteuid() == 0
    except AttributeError:
        return False
    full = cmd if is_root else ["sudo", "-n", *cmd]
    return _run_command(full, timeout=timeout)


def _wait_until_port_free(host: str, port: int, attempts: int = 15) -> bool:
    for _ in range(attempts):
        in_use, _pid = check_port_in_use(host, port)
        if not in_use:
            return True
        time.sleep(1)
    return False


def _release_foreign_cluster(host: str, port: int, data_path: Path) -> bool:
    """Stop a postmaster that is not the MindGraph data directory."""
    unit = _distro_unit(data_path)
    if unit is not None:
        version = data_path.parent.name
        name = data_path.name
        _run_root(["systemctl", "disable", "--now", unit])
        _run_root(["pg_ctlcluster", version, name, "stop"])
    else:
        pg_ctl = _find_pg_ctl_binary(data_path)
        if pg_ctl is not None:
            stop_cmd = launch_command_as_postgres([pg_ctl, "-D", str(data_path), "stop", "-m", "fast"])
            _run_command(stop_cmd)
    if _wait_until_port_free(host, port):
        return True
    _run_root(["systemctl", "stop", "postgresql"])
    return _wait_until_port_free(host, port)


def _disable_competing_distro_cluster(port: int, mindgraph: Path) -> None:
    """Keep a registered distro ``main`` cluster from taking ``port`` on reboot."""
    cluster_info = find_system_postgresql_cluster(port)
    if cluster_info is None:
        return
    main_path = cluster_info[0]
    if _paths_match(main_path, mindgraph):
        return
    unit = _distro_unit(main_path)
    if unit is None:
        return
    if _run_root(["systemctl", "disable", unit]):
        try:
            print(f"[POSTGRESQL] Disabled {unit} so it does not reclaim port {port}")
        except (ValueError, OSError):
            pass


def _warn_if_database_url_rejected(config: PostgresRuntimeConfig) -> None:
    if try_database_url_connect(config, timeout=2):
        return
    try:
        print(
            "[POSTGRESQL] MindGraph cluster is up but DATABASE_URL credentials failed. "
            "Fix .env (roles/passwords) or run scripts/db/run_migrations.py option 4."
        )
    except (ValueError, OSError):
        pass


def _finish_mindgraph_cluster(config: PostgresRuntimeConfig, data_path: Path) -> bool:
    _disable_competing_distro_cluster(config.port, data_path)
    _warn_if_database_url_rejected(config)
    return True


def use_persistent_mindgraph_cluster(config: PostgresRuntimeConfig) -> Optional[bool]:
    """
    Start the cluster selected for this port and record it in ``.env``.

    Returns True when that cluster is listening, False when it should be
    listening but could not be started, and None when no MindGraph data
    directory should replace the distro cluster.
    """
    if sys.platform == "win32" or not config.is_local:
        return None

    choice = choose_cluster(config)
    if choice.path is None:
        if choice.on_port or choice.other_port is not None:
            announce_cluster_choice(config, choice, "missing")
        return None

    data_path = choice.path
    if read_cluster_port(data_path) != config.port:
        announce_cluster_choice(config, choice, "missing")
        return None

    env_status = publish_cluster_env(data_path)
    announce_cluster_choice(config, choice, env_status)

    host = config.connection_probe_host
    in_use, pid = check_port_in_use(host, config.port)
    if in_use:
        own_pid = cluster_postmaster_pid(data_path)
        listener = postmaster_data_directory(pid) if pid is not None else None
        listener_is_ours = listener is not None and _paths_match(listener, data_path)
        pid_file_is_ours = own_pid is not None and pid == own_pid and listener is None
        if listener_is_ours or pid_file_is_ours:
            return _finish_mindgraph_cluster(config, data_path)
        if listener is None:
            try:
                print(f"[ERROR] Port {config.port} is in use by pid {pid}, data directory unknown.")
                print(f"        MindGraph data directory: {data_path}")
                print("        Application cannot start without that cluster.")
            except (ValueError, OSError):
                pass
            return False
        try:
            print(f"[POSTGRESQL] Port {config.port} is served by {listener}")
            print(f"[POSTGRESQL] Stopping that cluster and starting {data_path}")
        except (ValueError, OSError):
            pass
        if not _release_foreign_cluster(host, config.port, listener):
            try:
                print(f"[ERROR] Could not free port {config.port} from {listener}")
                print(f"        MindGraph data directory: {data_path}")
            except (ValueError, OSError):
                pass
            return False

    if try_start_persistent_cluster(data_path, config.port):
        return _finish_mindgraph_cluster(config, data_path)
    try:
        print(f"[ERROR] Could not start MindGraph cluster: {data_path}")
        print("        Inspect /var/log/postgresql/postgresql-mindgraph.log")
    except (ValueError, OSError):
        pass
    return False


def ensure_local_external_postgresql(config: PostgresRuntimeConfig) -> bool:
    """
    Ensure a local connect-only PostgreSQL instance is up.

    Returns True when the port accepts connections or a local cluster was started.
    """
    preferred = use_persistent_mindgraph_cluster(config)
    if preferred is not None:
        return preferred

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
