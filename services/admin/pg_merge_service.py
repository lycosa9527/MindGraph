"""
PG-to-PG Merge Service

Orchestrates non-destructive merge of a PostgreSQL dump into the live
database via a temporary staging database:

1. Create a staging database and pg_restore the dump into it.
2. Build user (by phone) and org (by code) ID mappings.
3. Merge every table in FK-safe order, remapping IDs.
4. Drop the staging database.

Public API:
    analyze_pg_dump()  – preview what the merge would do
    merge_pg_dump()    – execute the full merge

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import logging
import os
import subprocess
import uuid as uuid_mod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg import sql as psycopg_sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from config.database import libpq_database_url
from services.admin.database_export_service import _find_pg_binary
from services.admin.pg_merge_tables import (
    SKIP_TABLES,
    merge_table,
    ordered_table_names,
    reset_all_sequences,
)

logger = logging.getLogger(__name__)

_STAGING_PREFIX = "mindgraph_merge_staging_"

# App credentials in libpq format, derived once at import time.
_APP_DB_URL = libpq_database_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph",
    )
)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _replace_db_name(db_url: str, new_db: str) -> str:
    """Return *db_url* with the database name replaced by *new_db*."""
    parsed = urlparse(db_url)
    return urlunparse(parsed._replace(path=f"/{new_db}"))


def _sqla_url(libpq_url: str) -> str:
    """Convert a libpq URL to a psycopg-based SQLAlchemy URL."""
    if libpq_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + libpq_url[len("postgresql://") :]
    return libpq_url


def _admin_url() -> str:
    """App credentials pointed at the postgres system DB for CREATE/DROP DATABASE."""
    return _replace_db_name(_APP_DB_URL, "postgres")


# ---------------------------------------------------------------------------
# Staging database lifecycle
# ---------------------------------------------------------------------------


def _create_staging_db() -> str:
    """Create a temporary staging database, return its libpq URL."""
    staging_name = _STAGING_PREFIX + uuid_mod.uuid4().hex[:8]

    try:
        with psycopg.connect(_admin_url(), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(psycopg_sql.SQL("CREATE DATABASE {}").format(psycopg_sql.Identifier(staging_name)))
    except Exception as exc:
        if "permission denied" in str(exc).lower():
            raise PermissionError(
                "The database user lacks CREATEDB privilege. "
                'Grant it with: sudo -u postgres psql -c "ALTER USER mindgraph_user CREATEDB;"'
            ) from exc
        raise

    logger.info("[PGMerge] Created staging database: %s", staging_name)
    return _replace_db_name(_APP_DB_URL, staging_name)


def _restore_to_staging(staging_url: str, dump_path: Path) -> bool:
    """Run pg_restore to load a dump file into the staging database."""
    pg_restore = _find_pg_binary("pg_restore")
    if not pg_restore:
        logger.error("[PGMerge] pg_restore not found on system PATH")
        return False

    cmd = [
        pg_restore,
        "--no-owner",
        "--single-transaction",
        "-d",
        staging_url,
        str(dump_path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=3600,
        check=False,
        text=True,
    )
    if result.returncode > 1:
        logger.error(
            "[PGMerge] pg_restore failed (exit %d): %s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return False

    if result.returncode == 1:
        logger.warning(
            "[PGMerge] pg_restore completed with warnings: %s",
            (result.stderr or "")[:500],
        )

    logger.info("[PGMerge] Restored dump into staging database")
    return True


def _drop_staging_db(staging_url: str) -> None:
    """Drop the staging database, terminating any lingering connections first."""
    parsed = urlparse(staging_url)
    staging_name = parsed.path.lstrip("/").split("/")[0]

    try:
        with psycopg.connect(_admin_url(), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    psycopg_sql.SQL(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname = %s AND pid <> pg_backend_pid()"
                    ),
                    (staging_name,),
                )
                cur.execute(psycopg_sql.SQL("DROP DATABASE IF EXISTS {}").format(psycopg_sql.Identifier(staging_name)))
        logger.info("[PGMerge] Dropped staging database: %s", staging_name)
    except Exception as exc:
        logger.warning(
            "[PGMerge] Failed to drop staging database %s: %s",
            staging_name,
            exc,
        )


def _staging_engine(staging_url: str) -> Engine:
    """Create a disposable SQLAlchemy engine for the staging database."""
    return create_engine(_sqla_url(staging_url), poolclass=NullPool)


# ---------------------------------------------------------------------------
# Mapping builders
# ---------------------------------------------------------------------------


def _build_root_mappings(
    staging_eng: Engine,
    live_eng: Engine,
) -> Dict[str, Dict[int, int]]:
    """Build org (by code) and user (by phone) ID mappings.

    Returns ``{"organizations": {staging_id: live_id, ...},
               "users": {staging_id: live_id, ...}}``.
    """
    id_maps: Dict[str, Dict[int, int]] = {}

    with live_eng.connect() as conn:
        rows = conn.execute(text("SELECT code, id FROM organizations"))
        live_orgs = {r[0]: r[1] for r in rows}

    staging_inspector = inspect(staging_eng)
    staging_tables = set(staging_inspector.get_table_names())

    org_map: Dict[int, int] = {}
    if "organizations" in staging_tables:
        with staging_eng.connect() as conn:
            rows = conn.execute(text("SELECT id, code FROM organizations"))
            for staging_id, code in rows:
                if code in live_orgs:
                    org_map[staging_id] = live_orgs[code]
    id_maps["organizations"] = org_map

    with live_eng.connect() as conn:
        rows = conn.execute(text("SELECT phone, id FROM users"))
        live_users = {r[0]: r[1] for r in rows}

    user_map: Dict[int, int] = {}
    if "users" in staging_tables:
        with staging_eng.connect() as conn:
            rows = conn.execute(text("SELECT id, phone FROM users"))
            for staging_id, phone in rows:
                if phone in live_users:
                    user_map[staging_id] = live_users[phone]
    id_maps["users"] = user_map

    return id_maps


def _count_tables(engine: Engine) -> Dict[str, int]:
    """Return {table_name: row_count} for all tables in the database."""
    engine_inspector = inspect(engine)
    counts: Dict[str, int] = {}
    with engine.connect() as conn:
        for table in engine_inspector.get_table_names():
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                counts[table] = result.scalar() or 0
            except Exception:
                conn.rollback()
                counts[table] = -1
    return counts


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------


def analyze_pg_dump(
    dump_path: Path,
    live_engine: Engine,
) -> Dict[str, Any]:
    """Restore a dump to staging, analyse it, then drop staging.

    Returns a dict with user/org match stats, per-table row counts
    from the staging dump, and the list of tables that will be merged.
    """
    staging_url = _create_staging_db()
    staging_eng: Optional[Engine] = None
    try:
        if not _restore_to_staging(staging_url, dump_path):
            return {"success": False, "error": "pg_restore failed"}

        staging_eng = _staging_engine(staging_url)
        mappings = _build_root_mappings(staging_eng, live_engine)

        staging_counts = _count_tables(staging_eng)
        live_counts = _count_tables(live_engine)

        staging_inspector = inspect(staging_eng)
        staging_tables = set(staging_inspector.get_table_names())

        mergeable = [t for t in ordered_table_names() if t in staging_tables and t not in SKIP_TABLES]
        skipped = [t for t in staging_tables if t in SKIP_TABLES]

        org_map = mappings.get("organizations", {})
        user_map = mappings.get("users", {})

        staging_org_total = staging_counts.get("organizations", 0)
        staging_user_total = staging_counts.get("users", 0)

        per_table: Dict[str, Dict[str, int]] = {}
        for table in mergeable:
            per_table[table] = {
                "staging_rows": staging_counts.get(table, 0),
                "live_rows": live_counts.get(table, 0),
            }

        return {
            "success": True,
            "matched_users": len(user_map),
            "new_users": max(staging_user_total - len(user_map), 0),
            "matched_orgs": len(org_map),
            "new_orgs": max(staging_org_total - len(org_map), 0),
            "staging_tables": staging_counts,
            "merge_tables": mergeable,
            "skipped_tables": skipped,
            "per_table": per_table,
        }
    finally:
        if staging_eng is not None:
            staging_eng.dispose()
        _drop_staging_db(staging_url)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_pg_dump(
    dump_path: Path,
    live_engine: Engine,
) -> Dict[str, Any]:
    """Full PG-to-PG merge: staging → map → merge → cleanup.

    Returns ``{"success": True, "tables": {table: stats}, ...}``
    or ``{"success": False, "error": "..."}`` on failure.
    """
    started = datetime.now(tz=UTC)
    staging_url = _create_staging_db()
    staging_eng: Optional[Engine] = None

    try:
        if not _restore_to_staging(staging_url, dump_path):
            return {"success": False, "error": "pg_restore failed"}

        staging_eng = _staging_engine(staging_url)
        staging_inspector = inspect(staging_eng)
        staging_tables = set(staging_inspector.get_table_names())

        id_maps: Dict[str, Dict] = {}
        results: Dict[str, Dict[str, int]] = {}
        file_warning = False

        for table_name in ordered_table_names():
            if table_name not in staging_tables:
                id_maps[table_name] = {}
                continue

            table_result = merge_table(
                table_name,
                staging_eng,
                live_engine,
                id_maps,
            )
            results[table_name] = table_result

            if table_name in ("file_attachments", "library_documents"):
                if table_result.get("inserted", 0) > 0:
                    file_warning = True

        reset_all_sequences(live_engine)

        elapsed = (datetime.now(tz=UTC) - started).total_seconds()
        logger.info("[PGMerge] Full merge completed in %.1fs", elapsed)

        response: Dict[str, Any] = {
            "success": True,
            "tables": results,
            "elapsed_seconds": round(elapsed, 1),
        }
        if file_warning:
            response["file_warning"] = (
                "Some file_attachments or library_documents were merged. "
                "The referenced files on disk must be copied manually from "
                "the source server."
            )
        return response

    except Exception as exc:
        logger.error("[PGMerge] Merge failed: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)[:500]}
    finally:
        if staging_eng is not None:
            staging_eng.dispose()
        _drop_staging_db(staging_url)
