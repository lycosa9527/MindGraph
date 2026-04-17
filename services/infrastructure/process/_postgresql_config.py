"""
PostgreSQL configuration file management.

Handles creation and updates of postgresql.conf and pg_hba.conf files.

The generated ``postgresql.conf`` is tuned for MindGraph workloads:
- RAM-aware sizing for shared_buffers / effective_cache_size / work_mem
- PG 18 async I/O via ``io_method`` on Linux, ``worker`` fallback elsewhere
- ``pg_stat_statements`` + ``auto_explain`` preloaded for observability
- Conservative idle/statement timeouts to prevent stuck FastAPI handlers
  from holding pool connections indefinitely
"""

import os
import platform
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Dict


_CONFIG_VERSION = "v2-perf-2026-04-conn250"

# Default max_connections for managed PostgreSQL. Must cover worst-case app demand:
# UVICORN_WORKERS × (async pool+overflow + sync pool+overflow) + reserve; see config/database.py.
_DEFAULT_MAX_CONNECTIONS = 250


def _is_running_as_root() -> bool:
    """Check if running as root user."""
    if os.name == "nt":
        return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def setup_socket_directory(data_path: Path) -> Path:
    """
    Set up socket directory with proper permissions.

    Args:
        data_path: PostgreSQL data directory

    Returns:
        Path to socket directory
    """
    socket_dir = data_path / "sockets"
    socket_dir.mkdir(exist_ok=True)

    is_root = _is_running_as_root()
    if is_root and str(data_path) == "/var/lib/postgresql/mindgraph":
        try:
            subprocess.run(
                ["chown", "postgres:postgres", str(socket_dir)],
                check=False,
                timeout=5,
                capture_output=True,
            )
            subprocess.run(
                ["chmod", "700", str(socket_dir)],
                check=False,
                timeout=5,
                capture_output=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
    else:
        try:
            os.chmod(socket_dir, 0o700)
        except OSError:
            pass

    return socket_dir


def _ram_mib_from_unix_sysconf(
    sysconf_impl: Callable[..., int],
    names: Dict[str, int],
) -> int | None:
    """Compute total RAM from POSIX sysconf when SC_* keys are defined."""
    if "SC_PAGE_SIZE" not in names or "SC_PHYS_PAGES" not in names:
        return None
    try:
        page_size = sysconf_impl("SC_PAGE_SIZE")
        phys_pages = sysconf_impl("SC_PHYS_PAGES")
    except (OSError, ValueError):
        return None
    if page_size <= 0 or phys_pages <= 0:
        return None
    return int(page_size * phys_pages / (1024 * 1024))


def _detect_total_ram_mb() -> int:
    """Return total host RAM in MiB; fall back to a conservative 2048 on error."""
    sysconf_obj = getattr(os, "sysconf", None)
    sysconf_names_obj = getattr(os, "sysconf_names", None)
    if isinstance(sysconf_obj, Callable) and isinstance(sysconf_names_obj, dict):
        ram_mb = _ram_mib_from_unix_sysconf(
            sysconf_obj,
            dict(sysconf_names_obj),
        )
        if ram_mb is not None:
            return ram_mb

    if platform.system() == "Windows":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dw_length", ctypes.c_ulong),
                    ("dw_memory_load", ctypes.c_ulong),
                    ("ull_total_phys", ctypes.c_ulonglong),
                    ("ull_avail_phys", ctypes.c_ulonglong),
                    ("ull_total_page_file", ctypes.c_ulonglong),
                    ("ull_avail_page_file", ctypes.c_ulonglong),
                    ("ull_total_virtual", ctypes.c_ulonglong),
                    ("ull_avail_virtual", ctypes.c_ulonglong),
                    ("sull_avail_extended_virtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dw_length = ctypes.sizeof(_MEMORYSTATUSEX)
            windll_obj = getattr(ctypes, "windll", None)
            if windll_obj is not None:
                kernel32 = windll_obj.kernel32
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    return int(stat.ull_total_phys / (1024 * 1024))
        except (OSError, AttributeError, ImportError):
            pass

    return 2048


def _ram_profile(total_mb: int) -> Dict[str, str]:
    """Pick PostgreSQL memory settings based on detected host RAM.

    Tier table chosen to be safe: shared_buffers stays at ~25% of RAM,
    effective_cache_size at ~75%. These are widely accepted defaults
    (see pgtune.leopard.in.ua).
    """
    if total_mb >= 16 * 1024:
        return {
            "shared_buffers": "4GB",
            "effective_cache_size": "12GB",
            "work_mem": "32MB",
            "maintenance_work_mem": "1GB",
            "wal_buffers": "32MB",
            "max_wal_size": "8GB",
            "min_wal_size": "2GB",
        }
    if total_mb >= 8 * 1024:
        return {
            "shared_buffers": "2GB",
            "effective_cache_size": "6GB",
            "work_mem": "16MB",
            "maintenance_work_mem": "512MB",
            "wal_buffers": "16MB",
            "max_wal_size": "4GB",
            "min_wal_size": "1GB",
        }
    if total_mb >= 4 * 1024:
        return {
            "shared_buffers": "1GB",
            "effective_cache_size": "3GB",
            "work_mem": "8MB",
            "maintenance_work_mem": "256MB",
            "wal_buffers": "16MB",
            "max_wal_size": "2GB",
            "min_wal_size": "512MB",
        }
    if total_mb >= 2 * 1024:
        return {
            "shared_buffers": "512MB",
            "effective_cache_size": "1500MB",
            "work_mem": "4MB",
            "maintenance_work_mem": "128MB",
            "wal_buffers": "8MB",
            "max_wal_size": "1GB",
            "min_wal_size": "256MB",
        }
    return {
        "shared_buffers": "256MB",
        "effective_cache_size": "768MB",
        "work_mem": "2MB",
        "maintenance_work_mem": "64MB",
        "wal_buffers": "4MB",
        "max_wal_size": "512MB",
        "min_wal_size": "128MB",
    }


def _io_method() -> str:
    """``io_uring`` on Linux (PG 18+), ``worker`` elsewhere.

    PG 18 introduced ``io_method`` for async I/O. On Linux io_uring delivers
    the largest gains; on macOS/Windows it is not available, so use ``worker``.
    """
    if platform.system() == "Linux":
        return "io_uring"
    return "worker"


def _build_postgresql_conf(port: str, socket_dir: Path, max_connections: int) -> str:
    """Render the full ``postgresql.conf`` body for the managed instance."""
    total_ram_mb = _detect_total_ram_mb()
    profile = _ram_profile(total_ram_mb)
    io_method = _io_method()

    return f"""# PostgreSQL configuration for MindGraph subprocess mode
# Generated config version: {_CONFIG_VERSION}
# Host RAM detected: {total_ram_mb} MiB
#
# Tunables follow the database & Redis performance plan (Phase 2).
# Override sizing via the host environment by editing this file after
# generation; MindGraph only rewrites it when the version marker changes.

# ---------------------------------------------------------------- network
port = {port}
listen_addresses = '127.0.0.1'
unix_socket_directories = '{socket_dir}'

# ---------------------------------------------------------------- connections
max_connections = {max_connections}
superuser_reserved_connections = 5

# ---------------------------------------------------------------- memory
shared_buffers              = {profile["shared_buffers"]}
effective_cache_size        = {profile["effective_cache_size"]}
work_mem                    = {profile["work_mem"]}
maintenance_work_mem        = {profile["maintenance_work_mem"]}
huge_pages                  = try
dynamic_shared_memory_type  = posix

# ---------------------------------------------------------------- WAL / checkpoints
wal_buffers                 = {profile["wal_buffers"]}
min_wal_size                = {profile["min_wal_size"]}
max_wal_size                = {profile["max_wal_size"]}
checkpoint_completion_target = 0.9
checkpoint_timeout          = 15min
wal_compression             = on
synchronous_commit          = local

# ---------------------------------------------------------------- planner (SSD)
random_page_cost            = 1.1
effective_io_concurrency    = 200
default_statistics_target   = 200

# ---------------------------------------------------------------- async I/O (PG 18)
io_method                   = {io_method}
io_workers                  = 3

# ---------------------------------------------------------------- vacuum
autovacuum_naptime          = 30s
autovacuum_vacuum_scale_factor  = 0.05
autovacuum_analyze_scale_factor = 0.02
vacuum_buffer_usage_limit   = 256MB

# ---------------------------------------------------------------- observability
shared_preload_libraries    = 'pg_stat_statements,auto_explain'
pg_stat_statements.track    = top
pg_stat_statements.max      = 10000
auto_explain.log_min_duration = 500ms
auto_explain.log_analyze    = on
auto_explain.log_buffers    = on
track_io_timing             = on
track_functions             = pl

# ---------------------------------------------------------------- safety nets
idle_in_transaction_session_timeout = 30s
statement_timeout                   = 60s
lock_timeout                        = 5s
log_min_duration_statement          = 1000

# ---------------------------------------------------------------- logging
log_destination = 'stderr'
logging_collector = off
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_timezone = 'UTC'

# ---------------------------------------------------------------- locale
datestyle = 'iso, mdy'
timezone = 'UTC'
lc_messages = 'C'
lc_monetary = 'C'
lc_numeric = 'C'
lc_time = 'C'
default_text_search_config = 'pg_catalog.english'
"""


def update_postgresql_conf(data_path: Path, port: str, socket_dir: Path) -> None:
    """
    Update or create postgresql.conf with appropriate settings.

    Rewrites the file whenever the embedded ``CONFIG_VERSION`` marker is
    missing or stale, so deploys can roll out tunable changes by bumping
    ``_CONFIG_VERSION``. Existing manual overrides will be lost on upgrade
    — operators who customise this file should pin ``_CONFIG_VERSION``
    in their fork.

    Args:
        data_path: PostgreSQL data directory
        port: PostgreSQL port
        socket_dir: Socket directory path
    """
    postgresql_conf = data_path / "postgresql.conf"
    max_connections = int(os.getenv("POSTGRESQL_MAX_CONNECTIONS", str(_DEFAULT_MAX_CONNECTIONS)))

    try:
        config_needs_update = True
        if postgresql_conf.exists():
            with open(postgresql_conf, "r", encoding="utf-8") as f:
                content = f.read()
                has_correct_socket = f"unix_socket_directories = '{socket_dir}'" in content
                has_current_version = f"Generated config version: {_CONFIG_VERSION}" in content
                if has_correct_socket and has_current_version:
                    config_needs_update = False

        if config_needs_update:
            body = _build_postgresql_conf(port, socket_dir, max_connections)
            with open(postgresql_conf, "w", encoding="utf-8") as f:
                f.write(body)
            try:
                print(
                    f"[POSTGRESQL] Updated postgresql.conf ({_CONFIG_VERSION}) "
                    f"with socket directory: {socket_dir}, max_connections={max_connections}"
                )
            except (ValueError, OSError):
                pass
    except Exception as e:
        try:
            print(f"[ERROR] Failed to update postgresql.conf: {e}")
        except (ValueError, OSError):
            pass


def create_pg_hba_conf(data_path: Path) -> None:
    """
    Write pg_hba.conf with trust authentication for all local connections.

    Always overwrites the file so that initdb's default scram-sha-256 config
    does not prevent the application from connecting as the postgres superuser
    (which has no password in the managed setup).

    Args:
        data_path: PostgreSQL data directory
    """
    pg_hba_conf = data_path / "pg_hba.conf"
    try:
        with open(pg_hba_conf, "w", encoding="utf-8") as f:
            f.write("""# PostgreSQL host-based authentication configuration
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
""")
    except Exception as e:
        try:
            print(f"[ERROR] Failed to write pg_hba.conf: {e}")
        except (ValueError, OSError):
            pass
