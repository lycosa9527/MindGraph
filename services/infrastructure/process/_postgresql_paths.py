"""
PostgreSQL path resolution and binary finding utilities.

Handles WSL detection, path resolution, and finding PostgreSQL binaries.
"""

import os
import sys
from pathlib import Path
from typing import Tuple, Optional

from services.infrastructure.process._postgresql_helpers import ensure_postgres_directory_ownership


def find_postgres_binaries() -> Tuple[Optional[str], Optional[str]]:
    """
    Find PostgreSQL postgres and initdb binaries.

    Returns:
        Tuple of (postgres_binary, initdb_binary) or (None, None) if not found
    """
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
            postgres_dir = os.path.dirname(path)
            initdb_path = os.path.join(postgres_dir, 'initdb')
            if os.path.exists(initdb_path) and os.access(initdb_path, os.X_OK):
                initdb_binary = initdb_path
            break

    return postgres_binary, initdb_binary


def resolve_data_path() -> Tuple[Path, bool]:
    """
    Resolve PostgreSQL data directory path with WSL and Ubuntu handling.

    Returns:
        Tuple of (data_path, ubuntu_path_handled)
    """
    data_dir = os.getenv('POSTGRESQL_DATA_DIR', './storage/postgresql')
    data_path = Path(data_dir).resolve()

    resolved_str = str(data_path)
    is_wsl_windows_fs = resolved_str.startswith('/mnt/')

    # Better WSL detection: check /proc/version for WSL indicators
    is_wsl = False
    if sys.platform != 'win32':
        try:
            with open('/proc/version', 'r', encoding='utf-8') as proc_file:
                proc_version = proc_file.read().lower()
                if 'microsoft' in proc_version or 'wsl' in proc_version:
                    is_wsl = True
        except (FileNotFoundError, OSError, PermissionError):
            pass

    # Track if we've handled Ubuntu case to avoid double-processing
    ubuntu_path_handled = False

    if not is_wsl_windows_fs:
        try:
            current = data_path
            while current != current.parent:
                if current.is_symlink():
                    link_target = current.readlink()
                    if str(link_target.resolve()).startswith('/mnt/'):
                        is_wsl_windows_fs = True
                        break
                current = current.parent
        except Exception:
            pass

    # WSL: Use Linux-native path in user's home directory
    if is_wsl or is_wsl_windows_fs:
        linux_native_dir = Path.home() / '.mindgraph' / 'postgresql'
        linux_native_dir.mkdir(parents=True, exist_ok=True)

        try:
            print("[POSTGRESQL] Detected WSL/Windows-mounted filesystem - using Linux-native path")
            print(f"[POSTGRESQL] Original path: {data_path}")
            print(f"[POSTGRESQL] Using Linux-native path: {linux_native_dir}")
            msg = ("[POSTGRESQL] (To use a custom path, set "
                   "POSTGRESQL_DATA_DIR to a Linux-native location)")
            print(msg)
        except (ValueError, OSError):
            pass

        data_path = linux_native_dir.resolve()

    # Ubuntu/Debian (not WSL): Handle root user cases
    elif not is_wsl:
        is_root = False
        if sys.platform != 'win32':
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                is_root = False

        if is_root:
            # Check if we're on Ubuntu/Debian
            is_ubuntu_debian = False
            try:
                with open('/etc/os-release', 'r', encoding='utf-8') as os_file:
                    os_release = os_file.read().lower()
                    if 'ubuntu' in os_release or 'debian' in os_release:
                        is_ubuntu_debian = True
            except (FileNotFoundError, OSError, PermissionError):
                pass

            if is_ubuntu_debian:
                # If path is under /root/, use alternative location
                if str(data_path).startswith('/root/'):
                    alternative_dir = Path('/var/lib/postgresql/mindgraph')

                    try:
                        msg = ("[POSTGRESQL] Detected root user on Ubuntu/Debian "
                               "with /root/ path - using alternative location")
                        print(msg)
                        print(f"[POSTGRESQL] Original path: {data_path}")
                        print(f"[POSTGRESQL] Using alternative path: {alternative_dir}")
                        msg2 = ("[POSTGRESQL] (To use a custom path, set "
                                "POSTGRESQL_DATA_DIR environment variable)")
                        print(msg2)
                    except (ValueError, OSError):
                        pass

                    data_path = alternative_dir.resolve()
                    ubuntu_path_handled = True

                # If path is /var/lib/postgresql/mindgraph (set via env var or redirected),
                # ensure ownership
                if str(data_path) == '/var/lib/postgresql/mindgraph' and not ubuntu_path_handled:
                    ubuntu_path_handled = True

                # Ensure postgres user exists and directory has correct ownership
                # for Ubuntu paths
                if ubuntu_path_handled:
                    if not ensure_postgres_directory_ownership(data_path):
                        try:
                            print("[ERROR] Failed to set up PostgreSQL data directory ownership")
                            print("[POSTGRESQL] PostgreSQL initialization may fail")
                        except (ValueError, OSError):
                            pass

    # Create directory if it doesn't exist (Ubuntu case already handled ownership)
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
        # Only set permissions if we didn't already handle Ubuntu case above
        if not ubuntu_path_handled:
            try:
                os.chmod(data_path, 0o700)
            except OSError:
                pass

    return data_path, ubuntu_path_handled
