"""Lightweight PostgreSQL reachability check and subprocess start (no app imports)."""

from __future__ import annotations

import logging
import re
import socket
import subprocess
import sys
import time
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_LIBPQ_SCHEME = re.compile(r"^postgresql\+[^/]+://", re.IGNORECASE)

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from services.infrastructure.process.process_manager import start_postgresql_server
except ImportError:
    start_postgresql_server = None


def libpq_database_url(db_url: str) -> str:
    """Strip SQLAlchemy driver suffix for psycopg2."""
    if not db_url:
        return db_url
    return _LIBPQ_SCHEME.sub("postgresql://", db_url, count=1)


def _parse_db_host(db_url: str) -> str:
    parsed = urlparse(db_url)
    return parsed.hostname or "localhost"


def _parse_db_port(db_url: str) -> int:
    parsed = urlparse(db_url)
    return parsed.port or 5432


def _find_process_on_port(port: int) -> Optional[int]:
    if sys.platform == "win32":
        return None
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        pass
    return None


def _can_connect_postgresql(db_url: str, timeout: int = 2) -> bool:
    if psycopg2 is None:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    try:
        conn = psycopg2.connect(libpq_database_url(db_url), connect_timeout=timeout)
        conn.close()
        return True
    except Exception:
        return False


def _get_connection_error(db_url: str, timeout: int = 2) -> Optional[str]:
    if psycopg2 is None:
        return None
    try:
        psycopg2.connect(libpq_database_url(db_url), connect_timeout=timeout)
        return None
    except Exception as exc:
        return str(exc)


def _connection_error_is_password_reject(conn_err: Optional[str]) -> bool:
    if not conn_err:
        return False
    return "password authentication failed" in conn_err.lower()


def _server_port_open(db_url: str, timeout: int = 2) -> bool:
    """True when something accepts TCP on the URL host/port (no credentials)."""
    host = _parse_db_host(db_url)
    port = _parse_db_port(db_url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_postgresql_server_reachable(db_url: str) -> bool:
    """
    Return True when PostgreSQL is listening on DATABASE_URL host/port.

    Used before MindGraph RLS roles exist (fresh install). Does not require
    mindgraph_* login credentials.
    """
    if not db_url or "postgresql" not in db_url.lower():
        logger.error("DATABASE_URL must be a PostgreSQL URL")
        return False

    host = _parse_db_host(db_url)
    port = _parse_db_port(db_url)
    if _server_port_open(db_url):
        logger.info("PostgreSQL server is reachable at %s:%s", host, port)
        return True

    logger.info("PostgreSQL not reachable at %s:%s. Attempting to start...", host, port)
    _try_start_postgresql()
    time.sleep(3)

    for attempt in range(3):
        if _server_port_open(db_url):
            logger.info("PostgreSQL server is now reachable at %s:%s", host, port)
            return True
        if attempt < 2:
            time.sleep(2)

    pid = _find_process_on_port(port)
    logger.error(
        "PostgreSQL not reachable at %s:%s (pid on port: %s). "
        "Start the service: sudo systemctl start postgresql",
        host,
        port,
        pid,
    )
    return False


def _try_start_postgresql() -> bool:
    if start_postgresql_server is not None:
        try:
            process = start_postgresql_server()
            if process:
                logger.info("Started PostgreSQL server (PID: %s)", process.pid)
            else:
                logger.info("PostgreSQL already running")
            return True
        except SystemExit:
            logger.warning("App PostgreSQL starter failed, trying system service...")

    if sys.platform == "win32":
        for name in (
            "postgresql-x64-18",
            "postgresql-x64-16",
            "postgresql-x64-15",
            "postgresql-x64-14",
            "postgresql",
        ):
            try:
                result = subprocess.run(
                    ["net", "start", name],
                    capture_output=True,
                    timeout=10,
                    check=False,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info("Started PostgreSQL service: %s", name)
                    return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        return False

    try:
        result = subprocess.run(
            ["systemctl", "start", "postgresql"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def ensure_postgresql_running(db_url: str) -> bool:
    """Return True when PostgreSQL accepts connections on ``db_url``."""
    if not db_url or "postgresql" not in db_url.lower():
        logger.error("DATABASE_URL must be a PostgreSQL URL")
        return False

    if _can_connect_postgresql(db_url):
        logger.info("PostgreSQL is running")
        return True

    conn_err = _get_connection_error(db_url)
    if _connection_error_is_password_reject(conn_err):
        logger.error(
            "PostgreSQL rejected the password (server is likely running). Detail: %s",
            conn_err,
        )
        return False

    logger.info("PostgreSQL not reachable. Attempting to start...")
    _try_start_postgresql()
    time.sleep(3)

    for attempt in range(3):
        if _can_connect_postgresql(db_url):
            logger.info("PostgreSQL is now running")
            return True
        if attempt < 2:
            time.sleep(2)

    port = _parse_db_port(db_url)
    pid = _find_process_on_port(port)
    host = _parse_db_host(db_url)
    logger.error(
        "PostgreSQL not reachable at %s:%s (pid on port: %s). Detail: %s",
        host,
        port,
        pid,
        conn_err,
    )
    return False
