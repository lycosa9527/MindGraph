"""
PG-to-PG Merge Service

Orchestrates non-destructive merge of a PostgreSQL dump into the live
database via a temporary staging schema on the same database.

Live reads/writes use the migrate role (BYPASSRLS) so org-scoped tables
such as token_usage can be merged without RLS blocking inserts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from services.admin.pg_merge_config import SKIP_TABLES, STATS_RECOMPUTE_TABLES, ordered_table_names
from services.admin.pg_merge_staging import (
    StagingArea,
    cleanup_orphan_staging_schemas,
    create_staging_area,
    drop_staging_area,
    merge_database_engine,
    restore_dump_to_staging,
    staging_engine,
    staging_table_names,
)
from services.admin.pg_merge_table_ops import merge_table, preview_table, reset_all_sequences
from services.teacher_usage_stats import compute_and_upsert_user_usage_stats_async
from services.utils.error_types import DATABASE_ERRORS, PG_CONNECT_ERRORS
from services.utils.pg_client_binaries import pg_tools_libpq_url
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_MIGRATE_DB_URL = pg_tools_libpq_url()


def _build_root_mappings(
    staging_eng: Engine,
    staging_schema: str,
    live_eng: Engine,
) -> Dict[str, Dict[int, int]]:
    """Build org (by code) and user (by phone) ID mappings."""
    id_maps: Dict[str, Dict[int, int]] = {}

    with live_eng.connect() as conn:
        rows = conn.execute(text("SELECT code, id FROM organizations"))
        live_orgs = {r[0]: r[1] for r in rows}

    staging_tables = staging_table_names(staging_eng, staging_schema)

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


def _count_tables(engine: Engine, schema: Optional[str] = None) -> Dict[str, int]:
    """Return {table_name: row_count} for tables in *schema* (default public)."""
    engine_inspector = inspect(engine)
    if schema is None:
        table_names = engine_inspector.get_table_names()
    else:
        table_names = engine_inspector.get_table_names(schema=schema)
    counts: Dict[str, int] = {}
    with engine.connect() as conn:
        for table in table_names:
            try:
                if schema is None:
                    query = text(f'SELECT COUNT(*) FROM "{table}"')
                else:
                    query = text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                result = conn.execute(query)
                counts[table] = result.scalar() or 0
            except DATABASE_ERRORS:
                conn.rollback()
                counts[table] = -1
    return counts


async def _recompute_usage_stats_async(user_ids: Set[int]) -> int:
    """Recompute user_usage_stats for affected users after merge."""
    recomputed = 0
    async with system_rls_session() as db:
        for user_id in sorted(user_ids):
            if await compute_and_upsert_user_usage_stats_async(user_id, db):
                recomputed += 1
    return recomputed


def _recompute_usage_stats(user_ids: Set[int]) -> int:
    """Sync wrapper for stats recompute after merge."""
    if not user_ids:
        return 0
    return asyncio.run(_recompute_usage_stats_async(user_ids))


def _run_staged(
    dump_path: Path,
    body: Callable[[StagingArea, Engine, Engine], Dict[str, Any]],
) -> Dict[str, Any]:
    """Create staging schema, run *body*, then drop the schema."""
    cleanup_orphan_staging_schemas(_MIGRATE_DB_URL)
    live_engine = merge_database_engine(_MIGRATE_DB_URL)
    area = create_staging_area(_MIGRATE_DB_URL)
    staging_eng: Optional[Engine] = None
    try:
        ok, restore_error = restore_dump_to_staging(area, str(dump_path))
        if not ok:
            return {"success": False, "error": restore_error or "Restore failed"}

        staging_eng = staging_engine(area)
        return body(area, staging_eng, live_engine)
    except PG_CONNECT_ERRORS as exc:
        logger.error("[PGMerge] Staging operation failed: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)[:500]}
    finally:
        if staging_eng is not None:
            staging_eng.dispose()
        live_engine.dispose()
        drop_staging_area(area)


def analyze_pg_dump(dump_path: Path) -> Dict[str, Any]:
    """Restore a dump to staging, analyse it, then drop staging."""

    def _analyze(area: StagingArea, staging_eng: Engine, live_engine: Engine) -> Dict[str, Any]:
        mappings = _build_root_mappings(staging_eng, area.schema_name, live_engine)

        staging_counts = _count_tables(staging_eng, schema=area.schema_name)
        live_counts = _count_tables(live_engine)

        staging_tables = staging_table_names(staging_eng, area.schema_name)

        mergeable = [t for t in ordered_table_names() if t in staging_tables and t not in SKIP_TABLES]
        skipped = [t for t in staging_tables if t in SKIP_TABLES]

        org_map = mappings.get("organizations", {})
        user_map = mappings.get("users", {})

        staging_org_total = staging_counts.get("organizations", 0)
        staging_user_total = staging_counts.get("users", 0)

        id_maps: Dict[str, Dict] = {}
        per_table: Dict[str, Dict[str, int]] = {}

        for table_name in ordered_table_names():
            if table_name not in mergeable:
                continue
            preview = preview_table(
                table_name,
                staging_eng,
                live_engine,
                id_maps,
                simulate_ids=True,
            )
            per_table[table_name] = {
                "staging_rows": staging_counts.get(table_name, 0),
                "live_rows": live_counts.get(table_name, 0),
                "new_rows": preview["new_rows"],
                "duplicate_rows": preview["duplicate_rows"],
                "orphaned_rows": preview["orphaned_rows"],
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

    return _run_staged(dump_path, _analyze)


def merge_pg_dump(dump_path: Path) -> Dict[str, Any]:
    """Full PG-to-PG merge: staging → map → merge → cleanup."""
    started = datetime.now(tz=UTC)

    def _merge(area: StagingArea, staging_eng: Engine, live_engine: Engine) -> Dict[str, Any]:
        staging_tables = staging_table_names(staging_eng, area.schema_name)

        id_maps: Dict[str, Dict] = {}
        results: Dict[str, Dict[str, int]] = {}
        file_warning = False
        stats_user_ids: Set[int] = set()

        try:
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
                clean_result = {k: v for k, v in table_result.items() if not k.startswith("_")}
                results[table_name] = clean_result

                if table_name in STATS_RECOMPUTE_TABLES and table_result.get("inserted", 0) > 0:
                    for uid in table_result.get("_inserted_user_ids", []):
                        if isinstance(uid, int):
                            stats_user_ids.add(uid)

                if table_name in ("file_attachments", "library_documents"):
                    if table_result.get("inserted", 0) > 0:
                        file_warning = True

            reset_all_sequences(live_engine)
            stats_recomputed = _recompute_usage_stats(stats_user_ids)

            elapsed = (datetime.now(tz=UTC) - started).total_seconds()
            logger.info("[PGMerge] Full merge completed in %.1fs", elapsed)

            response: Dict[str, Any] = {
                "success": True,
                "tables": results,
                "elapsed_seconds": round(elapsed, 1),
                "stats_recomputed_users": stats_recomputed,
            }
            if file_warning:
                response["file_warning"] = (
                    "Some file_attachments or library_documents were merged. "
                    "The referenced files on disk must be copied manually from "
                    "the source server."
                )
            return response

        except DATABASE_ERRORS as exc:
            logger.error("[PGMerge] Merge failed: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)[:500]}

    return _run_staged(dump_path, _merge)
