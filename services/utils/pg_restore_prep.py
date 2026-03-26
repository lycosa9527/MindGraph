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
    Drop the public schema so pg_restore can rebuild without --clean.

    pg_restore --clean can fail when dependent FKs block dropping primary keys
    (e.g. feature_access_user_grants -> users_pkey). A CASCADE drop matches
    full data replacement for scripted and admin imports.
    """
    try:
        if engine is not None:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
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
            finally:
                conn.close()
    except Exception as exc:
        logger.error("Failed to drop public schema: %s", exc)
        return False
    logger.info(
        "Dropped schema public (CASCADE); pg_restore will recreate from dump",
    )
    return True
