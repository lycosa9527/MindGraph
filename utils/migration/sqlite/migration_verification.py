"""
SQLite Migration Verification Functions

Functions for verifying migration completeness and creating migration markers.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import create_engine, inspect, text

from .migration_table_order import get_table_migration_order
from .migration_utils import MIGRATION_MARKER_FILE, BACKUP_DIR

logger = logging.getLogger(__name__)


def verify_migration(sqlite_path: Path, pg_url: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify migration by comparing record counts between SQLite and PostgreSQL.

    Ensures PostgreSQL has complete data (>= SQLite counts) before allowing SQLite to be moved.
    This is a critical safety check to prevent data loss.

    Args:
        sqlite_path: Path to SQLite database
        pg_url: PostgreSQL connection URL

    Returns:
        Tuple of (is_valid, statistics_dict)
        - is_valid: True if PostgreSQL has all data (>= SQLite for all tables)
        - statistics_dict: Contains tables_migrated, total_records, and mismatches
    """
    stats = {
        "tables_migrated": 0,
        "total_records": 0,
        "mismatches": [],
        "missing_tables": [],
        "incomplete_tables": [],
    }

    try:
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        pg_engine = create_engine(pg_url)
        pg_inspector = inspect(pg_engine)
        pg_tables = set(pg_inspector.get_table_names())

        tables = get_table_migration_order()

        logger.info("[Migration] Verifying migration completeness for %d tables...", len(tables))

        for table_name in tables:
            try:
                # Check if table exists in SQLite
                sqlite_cursor = sqlite_conn.cursor()
                sqlite_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                table_exists_in_sqlite = sqlite_cursor.fetchone() is not None

                if not table_exists_in_sqlite:
                    # Table doesn't exist in SQLite - skip verification
                    logger.debug(
                        "[Migration] Table %s does not exist in SQLite, skipping",
                        table_name,
                    )
                    continue

                # Count SQLite records (table_name is from trusted source, but quote for safety)
                sqlite_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                sqlite_count = sqlite_cursor.fetchone()[0]

                # Check if table exists in PostgreSQL
                if table_name not in pg_tables:
                    # Table missing in PostgreSQL - CRITICAL ERROR
                    stats["missing_tables"].append(table_name)
                    stats["mismatches"].append(
                        {
                            "table": table_name,
                            "sqlite_count": sqlite_count,
                            "postgresql_count": 0,
                            "error": "Table missing in PostgreSQL",
                        }
                    )
                    logger.error(
                        "[Migration] CRITICAL: Table %s missing in PostgreSQL (SQLite has %d rows)",
                        table_name,
                        sqlite_count,
                    )
                    continue

                # Count PostgreSQL records using proper identifier quoting
                with pg_engine.connect() as conn:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    pg_count = result.scalar()

                # Verify PostgreSQL has complete data (>= SQLite)
                if pg_count < sqlite_count:
                    # PostgreSQL has fewer rows - CRITICAL ERROR
                    stats["incomplete_tables"].append(table_name)
                    stats["mismatches"].append(
                        {
                            "table": table_name,
                            "sqlite_count": sqlite_count,
                            "postgresql_count": pg_count,
                            "error": (
                                f"PostgreSQL has {pg_count} rows, SQLite has {sqlite_count} rows "
                                f"(missing {sqlite_count - pg_count} rows)"
                            ),
                        }
                    )
                    logger.error(
                        "[Migration] CRITICAL: Table %s incomplete in PostgreSQL: "
                        "SQLite=%d, PostgreSQL=%d (missing %d rows)",
                        table_name,
                        sqlite_count,
                        pg_count,
                        sqlite_count - pg_count,
                    )
                elif pg_count > sqlite_count:
                    # PostgreSQL has more rows - acceptable (may have new data)
                    stats["tables_migrated"] += 1
                    stats["total_records"] += sqlite_count
                    logger.info(
                        "[Migration] Table %s verified: SQLite=%d, PostgreSQL=%d "
                        "(PostgreSQL has more rows - acceptable)",
                        table_name,
                        sqlite_count,
                        pg_count,
                    )
                else:
                    # Exact match - perfect
                    stats["tables_migrated"] += 1
                    stats["total_records"] += sqlite_count
                    logger.debug(
                        "[Migration] Table %s verified: SQLite=%d, PostgreSQL=%d (match)",
                        table_name,
                        sqlite_count,
                        pg_count,
                    )

            except Exception as e:
                logger.error(
                    "[Migration] Failed to verify table %s: %s",
                    table_name,
                    e,
                    exc_info=True,
                )
                stats["mismatches"].append({"table": table_name, "error": str(e)})

        sqlite_conn.close()
        pg_engine.dispose()

        # Determine if verification passed
        # Verification passes only if:
        # 1. No missing tables
        # 2. No incomplete tables (PostgreSQL >= SQLite for all tables)
        # 3. No errors
        is_valid = (
            len(stats["missing_tables"]) == 0
            and len(stats["incomplete_tables"]) == 0
            and len([m for m in stats["mismatches"] if "error" in m]) == 0
        )

        if not is_valid:
            logger.error(
                "[Migration] Verification FAILED: %d missing tables, %d incomplete tables, %d errors",
                len(stats["missing_tables"]),
                len(stats["incomplete_tables"]),
                len([m for m in stats["mismatches"] if "error" in m]),
            )
        else:
            logger.info(
                "[Migration] Verification PASSED: %d tables verified, %d total records",
                stats["tables_migrated"],
                stats["total_records"],
            )

        return is_valid, stats

    except Exception as e:
        logger.error("[Migration] Verification failed with exception: %s", e, exc_info=True)
        return False, stats


def create_migration_marker(backup_path: Optional[Path], stats: Dict[str, Any]) -> bool:
    """
    Create migration marker file to prevent re-migration.

    Args:
        backup_path: Path to SQLite backup file
        stats: Migration statistics

    Returns:
        True if marker created successfully
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        marker_data = {
            "migration_completed_at": datetime.now().isoformat(),
            "backup_path": str(backup_path) if backup_path else None,
            "statistics": stats,
        }

        with open(MIGRATION_MARKER_FILE, "w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)

        logger.info("[Migration] Migration marker created: %s", MIGRATION_MARKER_FILE)
        return True
    except Exception as e:
        logger.error("[Migration] Failed to create migration marker: %s", e)
        return False


def _integer_max_for_serial_setval(max_id: object) -> Optional[int]:
    """Return a positive int max for setval, or None if PK is not integer serial (e.g. UUID, str)."""
    if max_id is None or isinstance(max_id, str):
        return None
    if isinstance(max_id, bool):
        return None
    try:
        if isinstance(max_id, int):
            val = max_id
        elif isinstance(max_id, Decimal):
            val = int(max_id)
        else:
            val = int(max_id)
    except (TypeError, ValueError, OverflowError):
        return None
    return val if val > 0 else None


def reset_postgresql_sequences(pg_engine: Any) -> None:
    """
    Reset PostgreSQL sequences to match migrated data.

    After migrating data, sequences need to be updated so that
    new inserts don't conflict with existing IDs.

    Uses pg_get_serial_sequence() to find the actual sequence name
    instead of assuming naming convention.

    Args:
        pg_engine: PostgreSQL SQLAlchemy engine
    """
    try:
        inspector = inspect(pg_engine)
        tables = inspector.get_table_names()
        sequences_reset = 0
        sequences_failed = []

        with pg_engine.connect() as conn:
            for table_name in tables:
                try:
                    # Get primary key column
                    pk_cols = inspector.get_pk_constraint(table_name)
                    if not pk_cols.get("constrained_columns"):
                        continue

                    pk_col = pk_cols["constrained_columns"][0]

                    # Get the maximum ID value (use proper identifier quoting)
                    result = conn.execute(text(f'SELECT MAX("{pk_col}") FROM "{table_name}"'))
                    max_id = result.scalar()
                    int_max = _integer_max_for_serial_setval(max_id)
                    if int_max is not None:
                        # Use pg_get_serial_sequence() to find actual sequence name
                        # This is more reliable than assuming naming convention
                        # pg_get_serial_sequence expects string literals (single quotes), not identifiers
                        seq_result = conn.execute(text(f"SELECT pg_get_serial_sequence('{table_name}', '{pk_col}')"))
                        sequence_name = seq_result.scalar()

                        if sequence_name:
                            # Remove schema prefix if present (e.g., "public.users_id_seq" -> "users_id_seq")
                            if "." in sequence_name:
                                sequence_name = sequence_name.split(".")[-1]

                            try:
                                next_val = int_max + 1
                                conn.execute(
                                    text(f"SELECT setval('{sequence_name}', {next_val}, false)"),
                                )
                                conn.commit()
                                sequences_reset += 1
                                logger.debug(
                                    "[Migration] Reset sequence %s to %d (table: %s)",
                                    sequence_name,
                                    next_val,
                                    table_name,
                                )
                            except Exception as seq_error:
                                logger.warning(
                                    "[Migration] Failed to reset sequence %s for table %s: %s",
                                    sequence_name,
                                    table_name,
                                    seq_error,
                                )
                                sequences_failed.append(f"{table_name}.{pk_col}")
                        else:
                            # No sequence found - might be a non-serial primary key
                            logger.debug(
                                "[Migration] No sequence found for %s.%s (may not be serial)",
                                table_name,
                                pk_col,
                            )

                except Exception as e:
                    logger.warning("[Migration] Could not reset sequence for %s: %s", table_name, e)
                    sequences_failed.append(table_name)
                    continue

        if sequences_failed:
            logger.warning(
                "[Migration] PostgreSQL sequences reset: %d succeeded, %d failed: %s",
                sequences_reset,
                len(sequences_failed),
                ", ".join(sequences_failed),
            )
        else:
            logger.info("[Migration] PostgreSQL sequences reset (%d sequences)", sequences_reset)
    except Exception as e:
        logger.warning("[Migration] Failed to reset sequences: %s", e)
