"""
Shared preparation for full PostgreSQL pg_restore (replace-all-data flows).

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional
from urllib.parse import unquote, urlparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import libpq_database_url

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


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
    if (
        "permission denied for database" not in msg
        and "insufficient privilege" not in msg
    ):
        return
    user, dbname = _db_user_and_name_from_url(db_url)
    logger.error(
        "The app user cannot run CREATE SCHEMA (the database is often owned "
        "by postgres after createdb). As the postgres superuser, run one of:\n"
        "  sudo -u postgres psql -c \"ALTER DATABASE %s OWNER TO %s;\"\n"
        "  sudo -u postgres psql -c \"GRANT CREATE ON DATABASE %s TO %s;\"",
        dbname,
        user,
        dbname,
        user,
    )


def ensure_public_schema_exists(
    db_url: str,
    engine: Optional[Engine] = None,
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
            if psycopg2 is None:
                logger.error(
                    "psycopg2 not installed. Install with: pip install psycopg2-binary",
                )
                return False
            conn = psycopg2.connect(libpq_database_url(db_url))
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute("CREATE SCHEMA IF NOT EXISTS public")
                    cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
            finally:
                conn.close()
    except Exception as exc:
        logger.error("Failed to ensure public schema: %s", exc)
        _log_database_privilege_hint(exc, db_url)
        return False
    logger.debug("Ensured schema public exists")
    return True


def wipe_public_schema_before_restore(
    db_url: str,
    engine: Optional[Engine] = None,
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
            if psycopg2 is None:
                logger.error(
                    "psycopg2 not installed. Install with: pip install psycopg2-binary",
                )
                return False
            conn = psycopg2.connect(libpq_database_url(db_url))
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
                    cur.execute("CREATE SCHEMA public")
                    cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
            finally:
                conn.close()
    except Exception as exc:
        logger.error("Failed to reset public schema: %s", exc)
        _log_database_privilege_hint(exc, db_url)
        return False
    logger.info(
        "Reset public schema (DROP CASCADE, empty CREATE); pg_restore will load the dump",
    )
    return True
