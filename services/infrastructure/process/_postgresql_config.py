"""
PostgreSQL configuration file management.

Handles creation and updates of postgresql.conf and pg_hba.conf files.
"""

import os
import subprocess
from pathlib import Path


def _is_running_as_root() -> bool:
    """Check if running as root user."""
    if os.name == 'nt':
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
    socket_dir = data_path / 'sockets'
    socket_dir.mkdir(exist_ok=True)

    # If running as root and using Ubuntu path, ensure socket directory is owned by postgres
    is_root = _is_running_as_root()
    if is_root and str(data_path) == '/var/lib/postgresql/mindgraph':
        try:
            subprocess.run(
                ['chown', 'postgres:postgres', str(socket_dir)],
                check=False,
                timeout=5,
                capture_output=True
            )
            subprocess.run(
                ['chmod', '700', str(socket_dir)],
                check=False,
                timeout=5,
                capture_output=True
            )
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
    else:
        try:
            os.chmod(socket_dir, 0o700)
        except OSError:
            pass

    return socket_dir


def update_postgresql_conf(data_path: Path, port: str, socket_dir: Path) -> None:
    """
    Update or create postgresql.conf with appropriate settings.

    Args:
        data_path: PostgreSQL data directory
        port: PostgreSQL port
        socket_dir: Socket directory path
    """
    postgresql_conf = data_path / 'postgresql.conf'

    try:
        config_needs_update = True
        if postgresql_conf.exists():
            with open(postgresql_conf, 'r', encoding='utf-8') as f:
                content = f.read()
                has_correct_socket = f'unix_socket_directories = \'{socket_dir}\'' in content
                has_c_locale = 'lc_messages = \'C\'' in content
                if has_correct_socket and has_c_locale:
                    config_needs_update = False

        if config_needs_update:
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


def create_pg_hba_conf(data_path: Path) -> None:
    """
    Create pg_hba.conf if it doesn't exist.

    Args:
        data_path: PostgreSQL data directory
    """
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
