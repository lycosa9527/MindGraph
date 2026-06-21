"""
Locate PostgreSQL client programs (pg_dump, pg_restore) on the host.

Single implementation shared by admin export/import, CLI dump/import, scheduled
backups, and PG-merge staging restore. Honors PG_BIN_DIR; scans common Linux
layout (versions 18–12), then PATH (which / where).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from sqlalchemy.engine import make_url

from config.database import DATABASE_MIGRATION_URL, libpq_database_url
from scripts.db.migration_urls import ROLE_APP, resolve_migration_database_url

logger = logging.getLogger(__name__)


def find_pg_client_binary(name: str) -> Optional[str]:
    """
    Return an executable path for *name* (e.g. ``pg_dump``, ``pg_restore``).

    Returns None if no suitable binary is found.
    """
    pg_bin = os.environ.get("PG_BIN_DIR", "")
    paths = [
        os.path.join(pg_bin, name) if pg_bin else "",
        os.path.join(pg_bin, f"{name}.exe") if pg_bin else "",
    ]
    for version in range(18, 11, -1):
        paths.append(f"/usr/lib/postgresql/{version}/bin/{name}")
    paths += [
        f"/usr/local/pgsql/bin/{name}",
        f"/usr/bin/{name}",
        f"/usr/local/bin/{name}",
    ]
    for path in paths:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            return path

    try:
        cmd = ["where", name] if sys.platform == "win32" else ["which", name]
        result = subprocess.run(cmd, capture_output=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            first_line = result.stdout.decode("utf-8").strip().split("\n")[0]
            found = first_line.strip()
            return found if found else None
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def pg_tools_connection_username(db_url: str) -> str:
    """Return PostgreSQL username from a libpq/SQLAlchemy URL (for logging only)."""
    return make_url(db_url).username or "unknown"


def pg_tools_libpq_url() -> str:
    """
    Libpq URI for pg_dump and pg_restore.

    Uses a migrate-capable PostgreSQL role (``mindgraph_migrate``, BYPASSRLS).
    ``--no-policies`` only excludes policies from the archive; pg_dump still
    runs queries as the connection role and must bypass RLS to copy protected
    tables such as ``api_keys``.
    """
    dump_url = DATABASE_MIGRATION_URL
    if (make_url(dump_url).username or "") == ROLE_APP:
        dump_url, source = resolve_migration_database_url()
        logger.info("pg_dump/pg_restore using migrate-capable URL (%s)", source)
    return libpq_database_url(dump_url)


def build_pg_dump_cmd(pg_dump: str, output_path: Path, db_url: str) -> List[str]:
    """
    Build pg_dump argv aligned with admin export and Alembic RLS backup policy.

    Uses custom format, no owner/oids, and --no-policies. Callers must pass a
    migrate-capable URL (see ``pg_tools_libpq_url()``); the app runtime role
    cannot read RLS-protected tables during COPY.
    """
    return [
        pg_dump,
        "-Fc",
        "--no-owner",
        "--no-policies",
        "-f",
        str(output_path),
        libpq_database_url(db_url),
    ]


def log_pg_dump_failure(stderr: str) -> None:
    """Log pg_dump stderr and operator hints when RLS or privileges block the dump."""
    message = stderr or "pg_dump failed with no stderr output"
    logger.error("pg_dump failed: %s", message)
    lower = message.lower()
    if (
        "permission denied" in lower
        or "row-level security" in lower
        or "must be owner" in lower
        or "insufficient privilege" in lower
    ):
        logger.error(
            "Hint: set DATABASE_MIGRATION_URL to mindgraph_migrate (BYPASSRLS) in .env — "
            "see env.example. pg_dump cannot copy RLS-protected tables as mindgraph_app.",
        )
