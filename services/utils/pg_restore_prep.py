"""
Shared preparation for full PostgreSQL pg_restore (replace-all-data flows).

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import libpq_database_url

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


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
        return False
    logger.info(
        "Reset public schema (DROP CASCADE, empty CREATE); pg_restore will load the dump",
    )
    return True
