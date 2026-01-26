"""
Dependency checking utilities for MindGraph application.

Handles checking for required dependencies:
- Redis (Python package + server binary/service)
- Celery (Python package + Redis + Qdrant dependencies)
- Qdrant (Python package + server binary/service)
- PostgreSQL (Python package + server binaries)
"""

import os
import re
import sys
import subprocess
import importlib.util
import urllib.request
from types import ModuleType
from typing import Optional

# Try importing optional dependencies at module level
try:
    import redis
    REDIS_MODULE: Optional[ModuleType] = redis
except ImportError:
    REDIS_MODULE = None

try:
    import psycopg2
    PSYCOPG2_MODULE: Optional[ModuleType] = psycopg2
except ImportError:
    PSYCOPG2_MODULE = None


def check_package_installed(package_name: str) -> bool:
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def check_redis_installed() -> tuple[bool, str]:
    """
    Check if Redis is installed (Python package + server binary/service).

    Returns:
        tuple[bool, str]: (is_installed, message)
    """
    # Check Python package
    if REDIS_MODULE is None:
        return False, "Redis Python package not installed. Install with: pip install redis"

    # Check if Redis server binary exists in PATH
    redis_binary_found = False
    try:
        result = subprocess.run(
            ['which', 'redis-server'],
            capture_output=True,
            timeout=2,
            check=False
        )
        if result.returncode == 0:
            redis_binary_found = True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Check if Redis systemd service exists (Linux)
    redis_service_found = False
    if sys.platform != 'win32':
        try:
            result = subprocess.run(
                ['systemctl', 'list-unit-files', '--type=service', '--quiet', 'redis-server.service'],
                capture_output=True,
                timeout=2,
                check=False
            )
            if result.returncode == 0:
                redis_service_found = True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Check if Redis is already running (connection test)
    redis_running = False
    if REDIS_MODULE is not None:
        try:
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port_str = os.getenv('REDIS_PORT', '6379')
            redis_port = int(redis_port_str)
            redis_client_class = getattr(REDIS_MODULE, 'Redis')
            r = redis_client_class(host=redis_host, port=redis_port, socket_connect_timeout=1)
            r.ping()
            redis_running = True
        except Exception:
            pass

    if redis_running:
        return True, "Redis is installed and running"

    if redis_binary_found or redis_service_found:
        return True, "Redis is installed but not running"

    return False, (
        "Redis server binary or systemd service not found. "
        "Install Redis:\n"
        "  - Ubuntu/Debian: sudo apt-get install redis-server\n"
        "  - macOS: brew install redis\n"
        "  - Or download from: https://redis.io/download"
    )


def check_celery_installed() -> tuple[bool, str]:
    """
    Check if Celery is installed (Python package + dependencies).

    Returns:
        tuple[bool, str]: (is_installed, message)
    """
    # Check Celery Python package
    if not check_package_installed('celery'):
        return False, "Celery Python package not installed. Install with: pip install celery"

    # Check Redis dependency (required for Celery)
    if REDIS_MODULE is None:
        return False, (
            "Celery requires Redis but Redis Python package is not installed. "
            "Install with: pip install redis"
        )

    # Check if Redis is available
    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port_str = os.getenv('REDIS_PORT', '6379')
        redis_port = int(redis_port_str)
        redis_client_class = getattr(REDIS_MODULE, 'Redis')
        r = redis_client_class(host=redis_host, port=redis_port, socket_connect_timeout=1)
        r.ping()
    except Exception as e:
        return False, (
            f"Celery requires Redis but Redis server is not available: {e}\n"
            "Start Redis: sudo systemctl start redis-server"
        )

    # Check if Qdrant is configured (required for Celery in this app)
    qdrant_host = os.getenv('QDRANT_HOST', '')
    qdrant_url = os.getenv('QDRANT_URL', '')

    if not qdrant_host and not qdrant_url:
        return False, (
            "Celery requires Qdrant server but QDRANT_HOST is not configured.\n"
            "Install Qdrant: bash scripts/install_qdrant.sh\n"
            "Then add QDRANT_HOST=localhost:6333 to .env"
        )

    # Verify Qdrant is actually running
    try:
        urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
    except Exception:
        return False, (
            "Celery requires Qdrant server but Qdrant is not running on port 6333.\n"
            "Start Qdrant: bash scripts/install_qdrant.sh\n"
            "Or ensure Qdrant is running: sudo systemctl start qdrant"
        )

    return True, "Celery is installed and dependencies are available"


def check_qdrant_installed() -> tuple[bool, str]:
    """
    Check if Qdrant is installed (Python package + server binary/service).

    Returns:
        tuple[bool, str]: (is_installed, message)
    """
    # Check Python package (qdrant-client package imports as qdrant_client)
    if not check_package_installed('qdrant_client'):
        return False, "Qdrant Python package not installed. Install with: pip install qdrant-client"

    # Check if Qdrant is already running
    try:
        urllib.request.urlopen('http://localhost:6333/collections', timeout=2)
        return True, "Qdrant is installed and running"
    except Exception:
        pass

    # Check if Qdrant binary exists in common locations
    qdrant_paths = [
        os.path.expanduser('~/qdrant/qdrant'),
        '/usr/local/bin/qdrant',
        '/usr/bin/qdrant',
    ]

    qdrant_binary_found = False
    for path in qdrant_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            qdrant_binary_found = True
            break

    # Check if Qdrant systemd service exists (Linux)
    qdrant_service_found = False
    if sys.platform != 'win32':
        try:
            result = subprocess.run(
                ['systemctl', 'list-unit-files', '--type=service', '--quiet', 'qdrant.service'],
                capture_output=True,
                timeout=2,
                check=False
            )
            if result.returncode == 0:
                qdrant_service_found = True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    if qdrant_binary_found or qdrant_service_found:
        return True, "Qdrant is installed but not running"

    return False, (
        "Qdrant server binary not found. Install Qdrant:\n"
        "  - Run: bash scripts/install_qdrant.sh\n"
        "  - Or download from: https://github.com/qdrant/qdrant/releases\n"
        "  - Or set QDRANT_HOST to point to an existing Qdrant server"
    )


def check_postgresql_installed() -> tuple[bool, str]:
    """
    Check if PostgreSQL is installed (Python package + server binaries).

    Checks for:
    - psycopg2 Python package
    - postgres binary (PostgreSQL server)
    - initdb binary (for initializing data directory)

    Returns:
        tuple[bool, str]: (is_installed, message)
    """
    # Check Python package (psycopg2-binary)
    if not check_package_installed('psycopg2'):
        return False, (
            "PostgreSQL Python package not installed. "
            "Install with: pip install psycopg2-binary"
        )

    # Check for postgres binary in common locations
    postgres_paths = [
        '/usr/lib/postgresql/18/bin/postgres',  # PostgreSQL 18 (WSL/Ubuntu)
        '/usr/lib/postgresql/16/bin/postgres',  # PostgreSQL 16
        '/usr/lib/postgresql/15/bin/postgres',  # PostgreSQL 15
        '/usr/lib/postgresql/14/bin/postgres',  # PostgreSQL 14
        '/usr/local/pgsql/bin/postgres',  # Custom installation
        '/usr/bin/postgres',  # System-wide
    ]

    postgres_binary_found = False
    postgres_version = None
    for path in postgres_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            postgres_binary_found = True
            # Try to extract version from path or binary
            if '18' in path:
                postgres_version = '18'
            elif '16' in path:
                postgres_version = '16'
            elif '15' in path:
                postgres_version = '15'
            elif '14' in path:
                postgres_version = '14'
            else:
                # Try to get version from binary
                try:
                    result = subprocess.run(
                        [path, '--version'],
                        capture_output=True,
                        timeout=2,
                        check=False,
                        text=True
                    )
                    if result.returncode == 0 and 'postgres' in result.stdout.lower():
                        # Extract version number
                        version_match = re.search(r'(\d+)', result.stdout)
                        if version_match:
                            postgres_version = version_match.group(1)
                except Exception:
                    pass
            break

    # Check for initdb binary (same directory as postgres)
    initdb_binary_found = False
    if postgres_binary_found:
        # Check initdb in same directory as postgres
        postgres_dir = os.path.dirname(path)
        initdb_path = os.path.join(postgres_dir, 'initdb')
        if os.path.exists(initdb_path) and os.access(initdb_path, os.X_OK):
            initdb_binary_found = True

    # Check if PostgreSQL is already running (connection test)
    postgres_running = False
    if PSYCOPG2_MODULE is not None:
        try:
            db_url = os.getenv('DATABASE_URL', '')
            if db_url and 'postgresql' in db_url:
                # Try to connect (quick timeout)
                conn = PSYCOPG2_MODULE.connect(
                    db_url,
                    connect_timeout=1
                )
                conn.close()
                postgres_running = True
        except Exception:
            pass

    if postgres_running:
        version_msg = f" (version {postgres_version})" if postgres_version else ""
        return True, f"PostgreSQL is installed and running{version_msg}"

    if postgres_binary_found and initdb_binary_found:
        version_msg = f" (version {postgres_version})" if postgres_version else ""
        return True, f"PostgreSQL is installed but not running{version_msg}"

    if postgres_binary_found and not initdb_binary_found:
        return False, (
            "PostgreSQL postgres binary found but initdb binary not found. "
            "Install PostgreSQL with: sudo apt-get install postgresql postgresql-contrib"
        )

    return False, (
        "PostgreSQL binaries not found. Install PostgreSQL:\n"
        "  - Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib\n"
        "  - macOS: brew install postgresql\n"
        "  - Or download from: https://www.postgresql.org/download/"
    )
