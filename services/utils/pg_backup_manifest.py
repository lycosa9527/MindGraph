"""
Shared pg_dump manifest builder — row counts via migrate role (BYPASSRLS).

Used by CLI dump/import, admin export, and scheduled backup so manifest
table counts match pg_dump content under PostgreSQL RLS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from scripts.db.migration_urls import (
    configure_rls_migration_environment,
    create_migration_engine,
)
from scripts.db.rls_roles_bootstrap import ensure_rls_roles_exist
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


class StatsEngineResolutionError(RuntimeError):
    """Migrate-capable stats engine could not be prepared (roles or DATABASE_MIGRATION_URL)."""


def prepare_pg_dump_rls() -> tuple[bool, str]:
    """
    Ensure RLS roles exist and resolve DATABASE_MIGRATION_URL for dump/import.

    Returns (success, message). Message is empty on success.
    """
    roles_ok, roles_msg = ensure_rls_roles_exist()
    if not roles_ok:
        return False, roles_msg
    try:
        configure_rls_migration_environment()
    except DATABASE_ERRORS as exc:
        return False, str(exc)
    return True, ""


def resolve_stats_engine(*, bootstrap_rls: bool = True) -> Engine:
    """
    Return a dedicated migrate-capable engine for manifest row counts.

    Uses ``NullPool`` and does not replace the application ``config.engine``.
    When ``bootstrap_rls`` is True (default), ensures RLS roles and migrate URL first.
    """
    if bootstrap_rls:
        rls_ok, rls_msg = prepare_pg_dump_rls()
        if not rls_ok:
            raise StatsEngineResolutionError(rls_msg)
    else:
        configure_rls_migration_environment()
    cfg = importlib.import_module("config.database")
    migration_url = cfg.DATABASE_MIGRATION_URL
    return create_migration_engine(migration_url)


def collect_table_row_counts(pg_engine: Engine) -> dict[str, int]:
    """Query row counts for each table. Omits tables that cannot be counted."""
    counts: dict[str, int] = {}
    inspector = inspect(pg_engine)
    table_names = inspector.get_table_names()
    with pg_engine.connect() as conn:
        for table_name in table_names:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                counts[table_name] = int(result.scalar() or 0)
            except DATABASE_ERRORS as exc:
                logger.debug("Could not count %s: %s", table_name, exc)
    return counts


def collect_db_stats(pg_engine: Engine) -> tuple[int, int, int, dict[str, int]]:
    """Return (table_count, column_count, total_records, per_table_counts)."""
    inspector = inspect(pg_engine)
    table_names = inspector.get_table_names()
    total_columns = 0
    for table_name in table_names:
        try:
            total_columns += len(inspector.get_columns(table_name))
        except DATABASE_ERRORS:
            pass

    counts = collect_table_row_counts(pg_engine)
    total_records = sum(counts.values())
    return len(table_names), total_columns, total_records, counts


def build_pg_dump_manifest(
    dump_path: Path,
    pg_engine: Engine,
    *,
    dump_file: str | None = None,
    timestamp: datetime | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Build manifest dict aligned across CLI, admin export, and scheduled backup."""
    when = timestamp or datetime.now(tz=UTC)
    manifest: dict[str, Any] = {
        "dump_file": dump_file or dump_path.name,
        "timestamp": when.isoformat(),
        "size_bytes": dump_path.stat().st_size,
    }
    if source is not None:
        manifest["source"] = source

    try:
        counts = collect_table_row_counts(pg_engine)
        manifest["tables"] = counts

        pg_inspector = inspect(pg_engine)
        all_tables = pg_inspector.get_table_names()
        total_cols = 0
        for tbl in all_tables:
            try:
                total_cols += len(pg_inspector.get_columns(tbl))
            except DATABASE_ERRORS:
                pass

        manifest["total_tables"] = len(all_tables)
        manifest["total_columns"] = total_cols
        manifest["total_records"] = sum(counts.values())
    except DATABASE_ERRORS as exc:
        logger.warning("Could not collect manifest table stats: %s", exc)

    return manifest
