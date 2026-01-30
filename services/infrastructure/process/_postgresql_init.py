"""
PostgreSQL initialization utilities.

Handles initdb execution and user/ownership setup for PostgreSQL data directory.
"""

import os
import sys
import subprocess
import shlex
from pathlib import Path


def _is_running_as_root() -> bool:
    """Check if running as root user."""
    if sys.platform == 'win32':
        return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _check_postgres_user_exists() -> bool:
    """Check if postgres user exists."""
    try:
        result = subprocess.run(
            ['id', '-u', 'postgres'],
            capture_output=True,
            timeout=2,
            check=False
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _create_postgres_user() -> bool:
    """Try to create postgres user."""
    try:
        print("[POSTGRESQL] Creating 'postgres' user for PostgreSQL initialization...")
        create_result = subprocess.run(
            ['useradd', '-r', '-s', '/bin/bash', '-d', '/var/lib/postgresql', '-m', 'postgres'],
            capture_output=True,
            timeout=5,
            check=False
        )
        if create_result.returncode == 0:
            try:
                print("[POSTGRESQL] 'postgres' user created successfully")
            except (ValueError, OSError):
                pass
            return True
        return False
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _ensure_postgres_user() -> bool:
    """Ensure postgres user exists, creating if needed."""
    if _check_postgres_user_exists():
        return True

    if not _create_postgres_user():
        # Check if sudo is available
        sudo_available = False
        try:
            result = subprocess.run(
                ['which', 'sudo'],
                capture_output=True,
                timeout=2,
                check=False
            )
            sudo_available = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        if not sudo_available:
            try:
                print("[ERROR] Cannot create 'postgres' user and sudo is not available")
                print("        PostgreSQL's initdb cannot be run as root for security reasons.")
                print("        Solutions:")
                print("        1. Run the script as a non-root user")
                msg = ("        2. Create a 'postgres' user manually: "
                       "useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                print(msg)
            except (ValueError, OSError):
                pass
            return False

    return _check_postgres_user_exists()


def _change_ownership_for_root_path(data_path: Path) -> None:
    """Change ownership of data directory when running as root."""
    data_path_str = str(data_path)
    is_under_root = data_path_str.startswith('/root/')

    if not is_under_root:
        return

    if not _check_postgres_user_exists():
        return

    try:
        print("[POSTGRESQL] Changing ownership of data directory to 'postgres' user...")
        # Ensure parent storage directory exists and is accessible
        storage_dir = data_path.parent
        if not storage_dir.exists():
            storage_dir.mkdir(parents=True, exist_ok=True)

        # Change ownership of storage directory recursively
        subprocess.run(
            ['chown', '-R', 'postgres:postgres', str(storage_dir)],
            check=True,
            timeout=10,
            capture_output=True
        )

        # Ensure parent directories have execute permission for postgres to traverse
        current_path = storage_dir.parent
        while str(current_path) != '/' and str(current_path).startswith('/root/'):
            # Change ownership to postgres so it can traverse
            subprocess.run(
                ['chown', 'postgres:postgres', str(current_path)],
                check=False,
                timeout=5,
                capture_output=True
            )
            # Set execute permission for directory traversal
            subprocess.run(
                ['chmod', '755', str(current_path)],
                check=False,
                timeout=5,
                capture_output=True
            )
            # Stop at /root/MindGraph level (don't change /root itself)
            if str(current_path.parent) == '/root':
                break
            current_path = current_path.parent

        # Set proper permissions for PostgreSQL data directory
        subprocess.run(
            ['chmod', '-R', '700', str(data_path)],
            check=False,
            timeout=5,
            capture_output=True
        )
        try:
            print("[POSTGRESQL] Ownership changed successfully")
        except (ValueError, OSError):
            pass
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        try:
            print(f"[WARNING] Could not change ownership: {e}")
            print("[POSTGRESQL] Will attempt to continue, but initdb may fail")
        except (ValueError, OSError):
            pass


def _build_initdb_command(initdb_binary: str, data_path: Path) -> tuple[list[str], bool]:
    """
    Build initdb command with appropriate user wrapping if running as root.

    Returns:
        Tuple of (command_list, use_shell)
    """
    initdb_user = 'postgres'
    initdb_base_cmd = [
        initdb_binary, '-D', str(data_path), '-U', initdb_user,
        '--locale=C', '--encoding=UTF8'
    ]

    is_root = _is_running_as_root()
    if not is_root:
        return initdb_base_cmd, False

    # Ensure postgres user exists
    if not _ensure_postgres_user():
        try:
            print("[ERROR] Cannot run initdb as root")
            print("        PostgreSQL's initdb cannot be run as root for security reasons.")
            print("        Solutions:")
            print("        1. Run the script as a non-root user")
            msg = ("        2. Create a 'postgres' user: "
                   "useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
            print(msg)
            print("        3. Initialize PostgreSQL manually:")
            cmd = (f"           sudo -u postgres {initdb_binary} "
                   f"-D {data_path} -U postgres --locale=C --encoding=UTF8")
            print(cmd)
            print("        4. Or use an existing PostgreSQL installation")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # Change ownership if needed
    _change_ownership_for_root_path(data_path)

    # Build command to run as postgres user
    sudo_available = False
    try:
        result = subprocess.run(
            ['which', 'sudo'],
            capture_output=True,
            timeout=2,
            check=False
        )
        sudo_available = result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    if sudo_available:
        # Try sudo -u postgres
        try:
            result = subprocess.run(
                ['sudo', '-u', 'postgres', 'id'],
                capture_output=True,
                timeout=2,
                check=False
            )
            if result.returncode == 0:
                initdb_cmd = ['sudo', '-u', 'postgres'] + initdb_base_cmd
                try:
                    print("[POSTGRESQL] Running initdb via sudo as 'postgres' user (running as root)")
                except (ValueError, OSError):
                    pass
                return initdb_cmd, False
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Fallback to su
    cmd_str = ' '.join(shlex.quote(str(arg)) for arg in initdb_base_cmd)
    initdb_cmd = ['su', '-', 'postgres', '-c', cmd_str]
    try:
        print("[POSTGRESQL] Running initdb as 'postgres' user (running as root)")
    except (ValueError, OSError):
        pass
    return initdb_cmd, False


def initialize_postgresql_data_directory(
    initdb_binary: str,
    data_path: Path
) -> None:
    """
    Initialize PostgreSQL data directory using initdb.

    Args:
        initdb_binary: Path to initdb binary
        data_path: Path to PostgreSQL data directory

    Raises:
        SystemExit: If initialization fails
    """
    pg_version_file = data_path / 'PG_VERSION'
    if pg_version_file.exists():
        return

    try:
        print("[POSTGRESQL] Initializing PostgreSQL data directory...")
    except (ValueError, OSError):
        pass

    initdb_cmd, use_shell = _build_initdb_command(initdb_binary, data_path)

    try:
        initdb_result = subprocess.run(
            initdb_cmd,
            capture_output=True,
            timeout=30,
            check=False,
            text=True,
            shell=use_shell
        )
        if initdb_result.returncode != 0:
            error_msg = initdb_result.stderr
            # Check for root error specifically
            if 'cannot be run as root' in error_msg.lower():
                try:
                    print("[ERROR] Failed to initialize PostgreSQL data directory: cannot run as root")
                    print("        PostgreSQL's initdb cannot be run as root for security reasons.")
                    print("        Solutions:")
                    print("        1. Run the script as a non-root user")
                    msg = ("        2. Create a 'postgres' user: "
                           "sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                    print(msg)
                    print("        3. Initialize PostgreSQL manually:")
                    cmd = (f"           sudo -u postgres {initdb_binary} "
                           f"-D {data_path} -U postgres --locale=C --encoding=UTF8")
                    print(cmd)
                    print("        4. Or use an existing PostgreSQL installation")
                except (ValueError, OSError):
                    pass
            else:
                try:
                    print(f"[ERROR] Failed to initialize PostgreSQL data directory: {error_msg}")
                    print("        Application cannot start without PostgreSQL.")
                except (ValueError, OSError):
                    pass
            sys.exit(1)
        try:
            print("[POSTGRESQL] Data directory initialized")
        except (ValueError, OSError):
            pass
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        try:
            print(f"[ERROR] Failed to initialize PostgreSQL data directory: {e}")
            is_root = _is_running_as_root()
            if is_root:
                print("        Running as root - PostgreSQL initdb requires a non-root user.")
                print("        Solutions:")
                print("        1. Run the script as a non-root user")
                msg = ("        2. Create a 'postgres' user: "
                       "sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres")
                print(msg)
                print("        3. Initialize PostgreSQL manually:")
                cmd = (f"           sudo -u postgres {initdb_binary} "
                       f"-D {data_path} -U postgres --locale=C --encoding=UTF8")
                print(cmd)
            print("        Application cannot start without PostgreSQL.")
        except (ValueError, OSError):
            pass
        sys.exit(1)
