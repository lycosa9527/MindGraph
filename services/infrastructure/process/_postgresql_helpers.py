"""
PostgreSQL helper functions for server management.

Provides utility functions for verification, cleanup, and directory ownership.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import psycopg

from services.utils.error_types import PG_CONNECT_ERRORS

if TYPE_CHECKING:
    from services.infrastructure.process._postgresql_runtime import PostgresRuntimeConfig


def postgresql_accepts_connections(host: str, port: int) -> bool:
    """
    True when something on ``host:port`` accepts PostgreSQL connections.

    Uses ``pg_isready`` when available (no app credentials required).
    """
    try:
        result = subprocess.run(
            ["pg_isready", "-h", host, "-p", str(port), "-t", "2"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        pass

    try:
        test_url = f"postgresql://postgres@{host}:{port}/postgres"
        with psycopg.connect(test_url, connect_timeout=2):
            return True
    except (*PG_CONNECT_ERRORS,):
        return False


def try_database_url_connect(config: "PostgresRuntimeConfig", timeout: int = 5) -> bool:
    """Return True when ``config.database_url`` accepts a connection."""
    try:
        with psycopg.connect(config.database_url, connect_timeout=timeout):
            return True
    except (*PG_CONNECT_ERRORS,):
        return False


def verify_postgresql_on_port(host: str, port: int, db_url: Optional[str] = None) -> bool:
    """
    Verify that PostgreSQL is actually running on the specified port.

    Prefers a successful ``DATABASE_URL`` connection; otherwise checks whether
    the server accepts connections (``pg_isready`` / generic probe).

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        db_url: Optional database URL for connection test

    Returns:
        bool: True if PostgreSQL is responding, False otherwise
    """
    if db_url and "postgresql" in db_url:
        try:
            with psycopg.connect(db_url, connect_timeout=2):
                return True
        except (*PG_CONNECT_ERRORS,):
            pass
    return postgresql_accepts_connections(host, port)


def cleanup_stale_pid_file(data_path: Path) -> None:
    """
    Check for and remove stale PostgreSQL PID file if the process is not running.

    Args:
        data_path: Path to PostgreSQL data directory
    """
    pid_file = data_path / "postmaster.pid"
    if not pid_file.exists():
        return

    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            pid_line = f.readline().strip()
            if pid_line and pid_line.isdigit():
                pid = int(pid_line)
                # Check if process is still running
                if sys.platform != "win32":
                    try:
                        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                        # Process exists - PID file is valid
                        return
                    except ProcessLookupError:
                        # Process doesn't exist - stale PID file
                        try:
                            print(f"[POSTGRESQL] Removing stale PID file (process {pid} not running)")
                        except (ValueError, OSError):
                            pass
                        pid_file.unlink()
                    except PermissionError:
                        # Permission denied - might be different user, leave it
                        pass
    except (OSError, ValueError, IOError):
        # If we can't read/parse the PID file, try to remove it
        try:
            pid_file.unlink()
        except OSError:
            pass


def postgres_system_user_exists() -> bool:
    """Return True when the ``postgres`` OS user exists (Linux only)."""
    if sys.platform == "win32":
        return False
    try:
        result = subprocess.run(
            ["id", "-u", "postgres"],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def launch_command_as_postgres(cmd: list[str]) -> list[str]:
    """Prefix ``cmd`` with ``sudo -u postgres`` when running as root on Linux."""
    is_root = False
    try:
        is_root = os.geteuid() == 0
    except AttributeError:
        is_root = False
    if is_root and postgres_system_user_exists():
        return ["sudo", "-u", "postgres", *cmd]
    return cmd


def cluster_postmaster_pid(data_path: Path) -> Optional[int]:
    """Return the live postmaster PID for ``data_path``, or None if not running."""
    pid_file = data_path / "postmaster.pid"
    if not pid_file.exists():
        return None
    try:
        with open(pid_file, "r", encoding="utf-8") as pid_handle:
            pid_text = pid_handle.readline().strip()
        if not pid_text.isdigit():
            return None
        pid = int(pid_text)
    except (OSError, ValueError):
        return None

    if sys.platform == "win32":
        return pid

    try:
        os.kill(pid, 0)
        return pid
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid


def ensure_postgres_directory_ownership(data_path: Path) -> bool:
    """
    Ensure postgres user exists and owns the PostgreSQL data directory.

    This function:
    1. Checks if postgres user exists, creates it if not
    2. Creates the directory if it doesn't exist
    3. Sets ownership to postgres:postgres
    4. Sets permissions to 700
    5. Verifies postgres user can access the directory

    Args:
        data_path: Path to PostgreSQL data directory

    Returns:
        bool: True if setup successful, False otherwise
    """
    if sys.platform == "win32":
        return True

    # Check if postgres user exists
    postgres_user_exists = False
    try:
        result = subprocess.run(["id", "-u", "postgres"], capture_output=True, timeout=2, check=False)
        postgres_user_exists = result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Create postgres user if it doesn't exist
    if not postgres_user_exists:
        try:
            create_result = subprocess.run(
                [
                    "useradd",
                    "-r",
                    "-s",
                    "/bin/bash",
                    "-d",
                    "/var/lib/postgresql",
                    "-m",
                    "postgres",
                ],
                capture_output=True,
                timeout=5,
                check=False,
                text=True,
            )
            if create_result.returncode == 0:
                postgres_user_exists = True
            else:
                try:
                    print(f"[WARNING] Could not create postgres user: {create_result.stderr}")
                    print("[POSTGRESQL] Please create postgres user manually:")
                    print("  sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                except (ValueError, OSError):
                    pass
                return False
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            try:
                print(f"[ERROR] Failed to create postgres user: {e}")
            except (ValueError, OSError):
                pass
            return False

    if not postgres_user_exists:
        return False

    # Create directory if it doesn't exist
    try:
        data_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        try:
            print(f"[ERROR] Could not create directory {data_path}: {e}")
        except (ValueError, OSError):
            pass
        return False

    # Check current ownership
    try:
        stat_info = data_path.stat()
        current_uid = stat_info.st_uid
        current_gid = stat_info.st_gid

        # Get postgres user UID/GID
        id_result = subprocess.run(
            ["id", "-u", "postgres"],
            capture_output=True,
            timeout=2,
            check=True,
            text=True,
        )
        postgres_uid = int(id_result.stdout.strip())

        gid_result = subprocess.run(
            ["id", "-g", "postgres"],
            capture_output=True,
            timeout=2,
            check=True,
            text=True,
        )
        postgres_gid = int(gid_result.stdout.strip())

        # Only change ownership if needed
        if current_uid != postgres_uid or current_gid != postgres_gid:
            chown_result = subprocess.run(
                ["chown", "-R", "postgres:postgres", str(data_path)],
                check=False,
                timeout=10,
                capture_output=True,
                text=True,
            )
            if chown_result.returncode != 0:
                try:
                    print(f"[ERROR] Could not change ownership: {chown_result.stderr}")
                    print(f"[POSTGRESQL] Please run: sudo chown -R postgres:postgres {data_path}")
                except (ValueError, OSError):
                    pass
                return False

        # Set permissions to 700
        chmod_result = subprocess.run(
            ["chmod", "700", str(data_path)],
            check=False,
            timeout=5,
            capture_output=True,
            text=True,
        )
        if chmod_result.returncode != 0:
            try:
                print(f"[WARNING] Could not set permissions: {chmod_result.stderr}")
            except (ValueError, OSError):
                pass

        # Verify postgres user can access (test as postgres user, not using sudo since we're root)
        # Use su instead of sudo for more reliable access
        test_result = subprocess.run(
            ["su", "-", "postgres", "-c", f'test -w "{data_path}" && echo OK'],
            check=False,
            timeout=5,
            capture_output=True,
            text=True,
        )
        if test_result.returncode != 0 or "OK" not in test_result.stdout:
            try:
                print("[WARNING] Verification failed - postgres user may not have access")
                print(f"[POSTGRESQL] Directory: {data_path}")
                print(f"[POSTGRESQL] Please verify: sudo -u postgres test -w {data_path}")
            except (ValueError, OSError):
                pass
            return False

        return True

    except (subprocess.SubprocessError, FileNotFoundError, OSError, ValueError) as e:
        try:
            print(f"[ERROR] Failed to set directory ownership: {e}")
            print("[POSTGRESQL] Please manually run:")
            print(f"  sudo chown -R postgres:postgres {data_path}")
            print(f"  sudo chmod 700 {data_path}")
        except (ValueError, OSError):
            pass
        return False
