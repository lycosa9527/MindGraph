"""
PostgreSQL path resolution and binary finding utilities.

Handles WSL detection, path resolution, and finding PostgreSQL binaries.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from services.infrastructure.process._postgresql_helpers import (
    ensure_postgres_directory_ownership,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


def is_initialized_cluster(path: Path) -> bool:
    """Return True when ``path`` contains a PostgreSQL data directory (PG_VERSION)."""
    version = path / "PG_VERSION"
    try:
        return version.is_file()
    except OSError:
        return False


def linux_native_cluster_dir() -> Path:
    """Default app-managed PostgreSQL data directory on WSL/Linux home."""
    return (Path.home() / ".mindgraph" / "postgresql").resolve()


def ubuntu_persistent_cluster_dir() -> Path:
    """Persistent MindGraph cluster on Ubuntu/Debian when the app runs as root."""
    return Path("/var/lib/postgresql/mindgraph")


def read_cluster_port(data_path: Path, default: int = 5432) -> int:
    """Read ``port`` from ``postgresql.conf`` when present."""
    conf_path = data_path / "postgresql.conf"
    if not conf_path.is_file():
        return default
    try:
        for line in conf_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("port"):
                _, _, value = stripped.partition("=")
                port_text = value.strip()
                if port_text.isdigit():
                    return int(port_text)
    except OSError:
        pass
    return default


def find_system_postgresql_cluster(port: Optional[int] = None) -> Optional[Tuple[Path, str]]:
    """
    Locate a distro-managed PostgreSQL cluster (e.g. ``/var/lib/postgresql/18/main``).

    Args:
        port: When set, prefer a cluster registered on this TCP port.

    Returns:
        Tuple of (main_data_directory, version_label) or None.
    """
    matches: list[tuple[Path, str, int]] = []

    try:
        result = subprocess.run(
            ["pg_lsclusters", "--no-header"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                fields = line.split()
                if len(fields) >= 6 and fields[1] == "main":
                    version = fields[0]
                    cluster_port = int(fields[2])
                    data_dir = Path(fields[5])
                    if is_initialized_cluster(data_dir):
                        matches.append((data_dir, version, cluster_port))
    except (FileNotFoundError, subprocess.SubprocessError, ValueError, OSError) as exc:
        logger.debug("pg_lsclusters cluster detection failed: %s", exc)

    if port is not None:
        for data_dir, version, cluster_port in matches:
            if cluster_port == port:
                return data_dir, version
    elif matches:
        data_dir, version, _cluster_port = matches[0]
        return data_dir, version

    if port is not None:
        return None

    base = Path("/var/lib/postgresql")
    if not base.is_dir():
        return None

    for version_dir in sorted(base.iterdir(), reverse=True):
        if not version_dir.is_dir() or not version_dir.name.isdigit():
            continue
        main = version_dir / "main"
        if is_initialized_cluster(main):
            return main, version_dir.name
    return None


def find_postgres_binaries() -> Tuple[Optional[str], Optional[str]]:
    """
    Find PostgreSQL postgres and initdb binaries.

    Returns:
        Tuple of (postgres_binary, initdb_binary) or (None, None) if not found
    """
    postgres_paths = [
        "/usr/lib/postgresql/18/bin/postgres",
        "/usr/lib/postgresql/16/bin/postgres",
        "/usr/lib/postgresql/15/bin/postgres",
        "/usr/lib/postgresql/14/bin/postgres",
        "/usr/local/pgsql/bin/postgres",
        "/usr/bin/postgres",
    ]

    postgres_binary = None
    initdb_binary = None
    for path in postgres_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            postgres_binary = path
            postgres_dir = os.path.dirname(path)
            initdb_path = os.path.join(postgres_dir, "initdb")
            if os.path.exists(initdb_path) and os.access(initdb_path, os.X_OK):
                initdb_binary = initdb_path
            break

    return postgres_binary, initdb_binary


def resolve_app_managed_data_path() -> Tuple[Path, bool]:
    """
    Resolve the data directory for app-managed (subprocess) PostgreSQL only.

    Returns:
        Tuple of (data_path, ubuntu_path_handled)
    """
    data_dir = os.getenv("POSTGRESQL_DATA_DIR", "./storage/postgresql")
    data_path = Path(data_dir).expanduser().resolve()

    resolved_str = str(data_path)
    is_wsl_windows_fs = resolved_str.startswith("/mnt/")

    is_wsl = False
    if sys.platform != "win32":
        try:
            with open("/proc/version", "r", encoding="utf-8") as proc_file:
                proc_version = proc_file.read().lower()
                if "microsoft" in proc_version or "wsl" in proc_version:
                    is_wsl = True
        except (FileNotFoundError, OSError, PermissionError):
            pass

    ubuntu_path_handled = False

    if not is_wsl_windows_fs:
        try:
            current = data_path
            while current != current.parent:
                if current.is_symlink():
                    link_target = current.readlink()
                    if str(link_target.resolve()).startswith("/mnt/"):
                        is_wsl_windows_fs = True
                        break
                current = current.parent
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("WSL symlink detection failed: %s", exc)

    if is_wsl or is_wsl_windows_fs:
        linux_native_dir = linux_native_cluster_dir()
        configured_path = Path(os.getenv("POSTGRESQL_DATA_DIR", "./storage/postgresql")).expanduser().resolve()
        explicit_linux_native = configured_path == linux_native_dir

        if explicit_linux_native or is_initialized_cluster(linux_native_dir):
            data_path = linux_native_dir
            try:
                if is_initialized_cluster(data_path):
                    print("[POSTGRESQL] Using existing app-managed cluster")
                else:
                    print("[POSTGRESQL] Using Linux-native path for new app-managed cluster")
                print(f"[POSTGRESQL] Data directory: {data_path}")
            except (ValueError, OSError):
                pass
        elif is_initialized_cluster(data_path):
            try:
                print("[POSTGRESQL] Using existing cluster on configured path (Windows mount — slower I/O)")
                print(f"[POSTGRESQL] Data directory: {data_path}")
            except (ValueError, OSError):
                pass
        else:
            linux_native_dir.mkdir(parents=True, exist_ok=True)
            try:
                print("[POSTGRESQL] WSL: using Linux-native app-managed data directory")
                print(f"[POSTGRESQL] Configured path: {configured_path}")
                print(f"[POSTGRESQL] Data directory: {linux_native_dir}")
            except (ValueError, OSError):
                pass
            data_path = linux_native_dir

    elif not is_wsl:
        is_root = False
        if sys.platform != "win32":
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                is_root = False

        if is_root:
            is_ubuntu_debian = False
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as os_file:
                    os_release = os_file.read().lower()
                    if "ubuntu" in os_release or "debian" in os_release:
                        is_ubuntu_debian = True
            except (FileNotFoundError, OSError, PermissionError):
                pass

            if is_ubuntu_debian:
                if str(data_path).startswith("/root/"):
                    alternative_dir = Path("/var/lib/postgresql/mindgraph")
                    try:
                        print("[POSTGRESQL] Root on Ubuntu/Debian — using alternative app-managed path")
                        print(f"[POSTGRESQL] Data directory: {alternative_dir}")
                    except (ValueError, OSError):
                        pass
                    data_path = alternative_dir.resolve()
                    ubuntu_path_handled = True

                if str(data_path) == "/var/lib/postgresql/mindgraph" and not ubuntu_path_handled:
                    ubuntu_path_handled = True

                if ubuntu_path_handled:
                    if not ensure_postgres_directory_ownership(data_path):
                        try:
                            print("[ERROR] Failed to set up PostgreSQL data directory ownership")
                        except (ValueError, OSError):
                            pass

    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
        if not ubuntu_path_handled:
            try:
                os.chmod(data_path, 0o700)
            except OSError:
                pass

    return data_path, ubuntu_path_handled


def resolve_data_path() -> Tuple[Path, bool]:
    """Backward-compatible alias for app-managed data path resolution."""
    return resolve_app_managed_data_path()
