"""
Shared preparation for full PostgreSQL pg_restore (replace-all-data flows).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import psycopg
from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import libpq_database_url
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def _pg_restore_line_should_skip_for_migrate_role(line: str) -> bool:
    """
    TOC entries ``mindgraph_migrate`` cannot apply during local pg_restore.

    Production dumps include superuser-only extension DDL and default ACLs
    owned by ``postgres``; skip them and re-apply grants after restore.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(";"):
        return False
    upper = stripped.upper()
    if " EXTENSION " in upper or upper.endswith(" EXTENSION"):
        return True
    if " COMMENT - EXTENSION " in upper:
        return True
    return " DEFAULT ACL " in upper


def build_pg_restore_toc_for_migrate_role(
    backup_path: Path,
    *,
    find_pg_restore: Any,
) -> Path | None:
    """
    Write a pg_restore TOC omitting superuser-only / postgres-owned ACL entries.

    Restore connects as ``mindgraph_migrate`` (``--no-owner``). Extensions must
    be pre-installed as superuser; default privileges are reapplied via RLS grant SQL.
    """
    pg_restore = find_pg_restore("pg_restore")
    if not pg_restore:
        return None

    result = subprocess.run(
        [pg_restore, "--list", str(backup_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        logger.warning("pg_restore --list failed; restoring without TOC filter")
        return None

    filtered: list[str] = []
    skipped = 0
    for line in result.stdout.splitlines():
        if _pg_restore_line_should_skip_for_migrate_role(line):
            filtered.append(f"; skipped migrate-incompatible: {line.lstrip(';')}")
            skipped += 1
        else:
            filtered.append(line)

    if skipped == 0:
        return None

    toc_path = Path(f"/tmp/mindgraph_pg_restore_{backup_path.stem}.toc")
    toc_path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    logger.info("pg_restore TOC: skipped %d migrate-incompatible entries", skipped)
    return toc_path


def build_pg_restore_toc_excluding_extensions(
    backup_path: Path,
    *,
    find_pg_restore: Any,
) -> Path | None:
    """Backward-compatible alias for :func:`build_pg_restore_toc_for_migrate_role`."""
    return build_pg_restore_toc_for_migrate_role(backup_path, find_pg_restore=find_pg_restore)


def _db_user_and_name_from_url(db_url: str) -> tuple[str, str]:
    """Parse PostgreSQL URL for username and database name (path after host)."""
    parsed = urlparse(db_url)
    user = unquote(parsed.username or "mindgraph_user")
    path = (parsed.path or "").lstrip("/")
    first = path.split("/")[0] if path else ""
    dbname = unquote(first) if first else "mindgraph"
    return user, dbname


def _log_database_privilege_hint(exc: Exception, db_url: str) -> None:
    """If exc is insufficient privilege on CREATE SCHEMA, log fix SQL."""
    msg = str(exc).lower()
    if "permission denied for database" not in msg and "insufficient privilege" not in msg:
        return
    user, dbname = _db_user_and_name_from_url(db_url)
    logger.error(
        "The app user cannot run CREATE SCHEMA (the database is often owned "
        "by postgres after createdb). As the postgres superuser, run one of:\n"
        '  sudo -u postgres psql -c "ALTER DATABASE %s OWNER TO %s;"\n'
        '  sudo -u postgres psql -c "GRANT CREATE ON DATABASE %s TO %s;"',
        dbname,
        user,
        dbname,
        user,
    )


def ensure_public_schema_exists(
    db_url: str,
    engine: Engine | None = None,
) -> bool:
    """
    Ensure ``public`` exists and is grantable.

    After ``DROP SCHEMA public CASCADE`` (e.g. failed restore), there is no
    schema for SQLAlchemy/ORM DDL; ``CREATE TYPE`` / ``CREATE TABLE`` then
    fails with "no schema has been selected to create in". Idempotent.
    """
    try:
        if engine is not None:
            with engine.begin() as conn:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        else:
            with psycopg.connect(libpq_database_url(db_url), autocommit=True) as conn, conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS public")
                cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
    except DATABASE_ERRORS as exc:
        logger.error("Failed to ensure public schema: %s", exc)
        _log_database_privilege_hint(exc, db_url)
        return False
    logger.debug("Ensured schema public exists")
    return True


def wipe_public_schema_before_restore(
    db_url: str,
    engine: Engine | None = None,
) -> bool:
    """
    Drop the public schema and recreate an empty ``public`` schema.

    Replaces ``--clean`` on pg_restore when FKs block drops. After
    ``DROP SCHEMA public CASCADE`` there is no ``public`` (unlike a new DB from
    ``createdb``), so ``CREATE TYPE public....`` in the archive would fail
    unless we create the schema first.
    """
    try:
        if engine is not None:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        else:
            with psycopg.connect(libpq_database_url(db_url), autocommit=True) as conn, conn.cursor() as cur:
                cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
                cur.execute("CREATE SCHEMA public")
                cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
    except DATABASE_ERRORS as exc:
        logger.error("Failed to reset public schema: %s", exc)
        _log_database_privilege_hint(exc, db_url)
        return False
    logger.info(
        "Reset public schema (DROP CASCADE, empty CREATE); pg_restore will load the dump",
    )
    return True
