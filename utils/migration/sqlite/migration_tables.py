"""
SQLite Migration Table Functions

Functions for migrating individual tables and verifying migration.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

try:
    from psycopg2.extras import execute_values
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

# Import Base directly from models to avoid circular import with config.database
from models.domain.auth import Base

# Import helper functions
from utils.migration.sqlite.migration_table_helpers import (
    build_insert_sql,
    convert_row_data,
    handle_foreign_key_violations
)

logger = logging.getLogger(__name__)

# Migration configuration constants
BATCH_SIZE = 10000  # Number of rows to fetch from SQLite at once
INSERT_PAGE_SIZE = 1000  # Number of rows to insert per batch in PostgreSQL
LARGE_TABLE_THRESHOLD = 10000  # Log progress for tables with more than this many rows
BATCH_FAILURE_THRESHOLD = 0.1  # Fail table migration if > 10% of batches fail

# Migration marker file
MIGRATION_MARKER_FILE = Path("backup/.migration_completed")
BACKUP_DIR = Path("backup")


def get_table_migration_order() -> List[str]:
    """
    Get list of tables in migration order (respecting foreign key dependencies).

    Returns:
        List of table names in correct migration order
    """
    # Order matters: parent tables before child tables
    # Tables are ordered by foreign key dependencies to ensure referential integrity
    return [
        # ========================================================================
        # TIER 1: Core tables with no foreign key dependencies
        # ========================================================================
        "organizations",
        "users",
        "api_keys",

        # ========================================================================
        # TIER 2: Tables that depend on Tier 1
        # ========================================================================
        # Knowledge space tables (depend on users/organizations)
        "knowledge_spaces",  # May reference users/organizations
        "knowledge_documents",  # References knowledge_spaces, users
        "document_chunks",  # References knowledge_documents
        "embeddings",  # References document_chunks
        "child_chunks",  # References document_chunks
        "chunk_attachments",  # References document_chunks
        "document_batches",  # References knowledge_documents
        "document_versions",  # References knowledge_documents
        "document_relationships",  # References knowledge_documents
        "knowledge_queries",  # References knowledge_spaces, users
        "query_feedback",  # References knowledge_queries
        "query_templates",  # References knowledge_spaces
        "evaluation_datasets",  # References knowledge_spaces
        "evaluation_results",  # References evaluation_datasets

        # Diagram tables (depend on users)
        "diagrams",  # References users

        # Token usage (depends on users)
        "token_usage",  # References users

        # Debate tables (depend on users)
        "debate_sessions",  # References users
        "debate_participants",  # References debate_sessions, users
        "debate_messages",  # References debate_sessions, debate_participants
        "debate_judgments",  # References debate_sessions

        # School zone tables (depend on diagrams, users)
        "shared_diagrams",  # References diagrams, users
        "shared_diagram_likes",  # References shared_diagrams, users
        "shared_diagram_comments",  # References shared_diagrams, users

        # Other tables (depend on users)
        "pinned_conversations",  # References users
        "dashboard_activities",  # References users
        "update_notifications",  # No foreign keys
        "update_notifications_dismissed",  # References update_notifications, users

        # ========================================================================
        # TIER 3: Chunk test tables (depend on knowledge space tables)
        # ========================================================================
        "chunk_test_documents",  # References knowledge_spaces
        "chunk_test_document_chunks",  # References chunk_test_documents
        "chunk_test_results",  # References chunk_test_documents, chunk_test_document_chunks
    ]


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    table_name: str,
    pg_engine: Any,
    inspector: Optional[Any] = None,
    progress_tracker: Optional[Any] = None
) -> Tuple[int, Optional[str]]:
    """
    Migrate a single table from SQLite to PostgreSQL.

    Args:
        sqlite_conn: SQLite connection
        table_name: Name of table to migrate
        pg_engine: PostgreSQL SQLAlchemy engine
        inspector: Optional pre-created inspector instance (for performance)
        progress_tracker: Optional progress tracker for displaying progress

    Returns:
        Tuple of (record_count, error_message)
    """
    # Ensure progress_tracker is recognized as used (even if None)
    _ = progress_tracker
    try:
        # Get table schema from SQLite (table_name is from trusted source, but quote for safety)
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
        columns = [desc[0] for desc in sqlite_cursor.description]

        # Check if table is empty first
        sqlite_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        total_count = sqlite_cursor.fetchone()[0]

        if total_count == 0:
            logger.info("[Migration] Table %s is empty, skipping", table_name)
            return 0, None

        # Execute query to get data (will fetch in batches)
        sqlite_cursor.execute(f'SELECT * FROM "{table_name}"')

        # Check if table exists in PostgreSQL, create if missing
        # Reuse inspector if provided, otherwise create new one
        if inspector is None:
            inspector = inspect(pg_engine)
        if inspector is None:
            return 0, "Failed to create database inspector"
        pg_table_names = inspector.get_table_names()
        if table_name not in pg_table_names:
            logger.warning(
                "[Migration] Table %s does not exist in PostgreSQL. "
                "Available tables: %s. Attempting to create...",
                table_name,
                ', '.join(sorted(pg_table_names)) if pg_table_names else "none"
            )

            # Try to create the missing table
            try:
                if table_name in Base.metadata.tables:
                    table = Base.metadata.tables[table_name]
                    table.create(bind=pg_engine, checkfirst=True)
                    logger.info("[Migration] Created missing table: %s", table_name)

                    # Re-check if table now exists
                    # Refresh inspector to get updated table list
                    inspector = inspect(pg_engine)
                    if inspector is None:
                        return 0, "Failed to refresh database inspector"
                    pg_table_names = inspector.get_table_names()
                    if table_name not in pg_table_names:
                        return 0, f"Table {table_name} could not be created in PostgreSQL"
                else:
                    return 0, f"Table {table_name} not found in Base.metadata - cannot create"
            except (OperationalError, ProgrammingError) as create_error:
                error_msg = str(create_error).lower()
                if ("already exists" in error_msg or
                    "duplicate" in error_msg or
                    ("relation" in error_msg and "exists" in error_msg)):
                    # Table was created by another process, verify it exists now
                    # Refresh inspector to get updated table list
                    inspector = inspect(pg_engine)
                    if inspector is None:
                        return 0, "Failed to refresh database inspector"
                    pg_table_names = inspector.get_table_names()
                    if table_name not in pg_table_names:
                        return 0, f"Table {table_name} creation reported success but table still missing"
                else:
                    return 0, f"Failed to create table {table_name}: {str(create_error)}"
            except Exception as create_error:
                return 0, f"Unexpected error creating table {table_name}: {str(create_error)}"

        # Get PostgreSQL table columns with their types
        pg_column_info = inspector.get_columns(table_name)
        pg_columns = [col['name'] for col in pg_column_info]

        # Build mapping of column names to their PostgreSQL types for type conversion
        pg_column_types = {}
        pg_column_nullable = {}  # Track which columns are nullable
        for col_info in pg_column_info:
            col_name = col_info['name']
            col_type = str(col_info['type']).upper()
            pg_column_types[col_name] = col_type
            pg_column_nullable[col_name] = col_info.get('nullable', True)

        # Get foreign key constraints to identify FK columns and their parent tables
        fk_constraints = inspector.get_foreign_keys(table_name)
        fk_columns = {}  # Map FK column name to its nullable status
        fk_parent_info = {}  # Map FK column name to (parent_table, parent_column) tuple
        for fk in fk_constraints:
            parent_table = fk.get('referred_table')
            referred_columns = fk.get('referred_columns', [])
            for col_name in fk.get('constrained_columns', []):
                fk_columns[col_name] = pg_column_nullable.get(col_name, True)
                if parent_table and referred_columns:
                    fk_parent_info[col_name] = (parent_table, referred_columns[0])

        # Get primary key constraint for conflict resolution
        pk_cols = inspector.get_pk_constraint(table_name)
        pk_column_names = pk_cols.get('constrained_columns', [])

        # Filter columns to only those that exist in both databases
        common_columns = [col for col in columns if col in pg_columns]

        # Track columns that exist in SQLite but not in PostgreSQL (data loss risk)
        missing_columns = [col for col in columns if col not in pg_columns]
        if missing_columns:
            logger.warning(
                "[Migration] Table %s: %d column(s) exist in SQLite but not in PostgreSQL "
                "(will be skipped - potential data loss): %s",
                table_name, len(missing_columns), ', '.join(missing_columns)
            )

        # Track columns that exist in PostgreSQL but not in SQLite (will be NULL/default)
        extra_columns = [col for col in pg_columns if col not in columns]
        if extra_columns:
            logger.info(
                "[Migration] Table %s: %d column(s) exist in PostgreSQL but not in SQLite "
                "(will use NULL/default values): %s",
                table_name, len(extra_columns), ', '.join(extra_columns)
            )

        if not common_columns:
            error_msg = (
                f"No common columns found for table {table_name}. "
                f"SQLite columns: {', '.join(columns)}, "
                f"PostgreSQL columns: {', '.join(pg_columns)}"
            )
            logger.error("[Migration] %s", error_msg)
            return 0, error_msg

        # Check if primary key columns are missing from common columns
        if pk_column_names:
            missing_pk_columns = [col for col in pk_column_names if col not in common_columns]
            if missing_pk_columns:
                logger.warning(
                    "[Migration] Primary key column(s) missing from common columns for table %s: %s",
                    table_name,
                    ', '.join(missing_pk_columns)
                )
                logger.warning(
                    "[Migration] Conflict resolution will fall back to DO NOTHING (updates may be skipped)"
                )

        # Build INSERT statement with ON CONFLICT handling for primary keys
        # Note: execute_values() expects "VALUES %s" (single placeholder), not "VALUES (%s, %s, ...)"
        # Use ON CONFLICT DO UPDATE for idempotent migrations
        # This allows re-running migration safely and updates existing records
        # Falls back to DO NOTHING if no primary key is found
        # CRITICAL: Use timestamp-aware updates to prevent overwriting newer PostgreSQL data
        conflict_columns = (
            [col for col in pk_column_names if col in common_columns]
            if pk_column_names else []
        )
        insert_sql = build_insert_sql(
            table_name,
            common_columns,
            pk_column_names or [],
            conflict_columns
        )

        # Migrate data using psycopg2 for better performance
        # Use batch processing to avoid loading entire table into memory
        pg_conn = pg_engine.raw_connection()
        try:
            pg_cursor = pg_conn.cursor()

            # Disable foreign key constraints during migration to handle orphaned records
            # This allows migration even if SQLite has data that violates foreign key constraints
            # Note: If this fails with permission denied, transaction may be aborted - need to handle that
            try:
                pg_cursor.execute("SET session_replication_role = 'replica'")
                pg_conn.commit()  # Commit the setting change
                logger.debug("[Migration] Disabled foreign key constraints for table %s", table_name)
            except Exception as fk_error:
                # Some PostgreSQL versions/configurations may not support this
                # If it fails with permission denied, transaction might be aborted - rollback and continue
                error_msg = str(fk_error).lower()
                if "permission denied" in error_msg:
                    logger.debug(
                        "[Migration] Cannot disable FK constraints (permission denied): %s. "
                        "Rolling back and continuing without FK disabling.",
                        fk_error
                    )
                    try:
                        pg_conn.rollback()
                    except Exception:
                        pass  # Ignore rollback errors
                elif "aborted" in error_msg:
                    logger.debug(
                        "[Migration] Transaction aborted while disabling FK constraints: %s. "
                        "Rolling back and continuing.",
                        fk_error
                    )
                    try:
                        pg_conn.rollback()
                    except Exception:
                        pass  # Ignore rollback errors
                else:
                    logger.debug(
                        "[Migration] Could not disable foreign key constraints (non-critical): %s",
                        fk_error
                    )

            # Progress reporting for large tables
            if total_count > LARGE_TABLE_THRESHOLD and not progress_tracker:
                logger.info(
                    "[Migration] Migrating %d records from %s (large table, using batch processing)",
                    total_count, table_name
                )

            # Process data in batches to avoid memory issues
            rows_inserted = 0
            batch_num = 0
            failed_batches = []
            batch_errors = []  # Track error messages for failed batches

            while True:
                # Fetch batch of rows from SQLite
                batch = sqlite_cursor.fetchmany(BATCH_SIZE)
                if not batch:
                    break

                batch_num += 1
                # Sanitize savepoint name (table_name is from trusted source, but sanitize for safety)
                # Replace any non-alphanumeric characters with underscore
                safe_table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
                savepoint_name = f"sp_{safe_table_name}_{batch_num}"

                try:
                    # Check if transaction is in a bad state and rollback if needed
                    # This handles cases where FK disabling failed and aborted the transaction
                    try:
                        # Try a simple query to check transaction state
                        pg_cursor.execute("SELECT 1")
                    except Exception as state_check:
                        if "aborted" in str(state_check).lower():
                            logger.debug(
                                "[Migration] Transaction is aborted, rolling back before batch %d",
                                batch_num
                            )
                            pg_conn.rollback()

                    # Create savepoint for this batch (allows rollback of just this batch)
                    pg_cursor.execute(f"SAVEPOINT {savepoint_name}")

                    # Prepare batch data: only include columns that exist in both databases
                    # Convert data types as needed (SQLite INTEGER booleans -> PostgreSQL BOOLEAN)
                    batch_data = [
                        convert_row_data(
                            row, columns, common_columns, pg_column_types, table_name
                        )
                        for row in batch
                    ]

                    # Insert batch into PostgreSQL
                    execute_values(
                        pg_cursor,
                        insert_sql,
                        batch_data,
                        page_size=INSERT_PAGE_SIZE
                    )

                    # Release savepoint on success
                    pg_cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")

                    # Track inserted rows (excluding conflicts)
                    batch_inserted = pg_cursor.rowcount
                    rows_inserted += batch_inserted

                    # Update progress tracker if available
                    if progress_tracker is not None:
                        progress_tracker.update_table_records(rows_inserted)

                    # Commit after each batch for better error recovery
                    pg_conn.commit()

                except Exception as batch_error:
                    # Check if transaction is aborted
                    error_msg = str(batch_error).lower()
                    is_aborted = (
                        "aborted" in error_msg or
                        "current transaction is aborted" in error_msg
                    )

                    if is_aborted:
                        # Transaction is aborted - rollback entire transaction and retry batch
                        logger.warning(
                            "[Migration] Transaction aborted for batch %d of table %s. "
                            "Rolling back and retrying batch.",
                            batch_num,
                            table_name
                        )
                        try:
                            pg_conn.rollback()
                            # Retry the batch after rollback
                            try:
                                pg_cursor.execute(f"SAVEPOINT {savepoint_name}")
                                execute_values(
                                    pg_cursor,
                                    insert_sql,
                                    batch_data,
                                    page_size=INSERT_PAGE_SIZE
                                )
                                pg_cursor.execute(
                                    f"RELEASE SAVEPOINT {savepoint_name}"
                                )
                                batch_inserted = pg_cursor.rowcount
                                rows_inserted += batch_inserted
                                if progress_tracker is not None:
                                    progress_tracker.update_table_records(
                                        rows_inserted
                                    )
                                pg_conn.commit()
                                continue  # Success, continue to next batch
                            except Exception as retry_error:
                                # Retry also failed
                                logger.warning(
                                    "[Migration] Batch %d retry failed for table %s: %s",
                                    batch_num, table_name, retry_error
                                )
                                failed_batches.append(batch_num)
                                batch_errors.append(
                                    f"Batch {batch_num}: {str(retry_error)}"
                                )
                                continue
                        except Exception as rollback_err:
                            logger.error(
                                "[Migration] Failed to rollback aborted transaction: %s",
                                rollback_err
                            )
                            failed_batches.append(batch_num)
                            batch_errors.append(f"Batch {batch_num}: Transaction aborted and rollback failed")
                            continue
                    else:
                        # Normal error - try to rollback to savepoint
                        try:
                            pg_cursor.execute(
                                f"ROLLBACK TO SAVEPOINT {savepoint_name}"
                            )
                            pg_cursor.execute(
                                f"RELEASE SAVEPOINT {savepoint_name}"
                            )

                            # Check if this is a foreign key violation for nullable columns
                            error_msg = str(batch_error)
                            is_fk_violation = (
                                "violates foreign key constraint" in error_msg.lower()
                            )

                            if is_fk_violation:
                                # Try to handle FK violations by inserting records individually
                                logger.info(
                                    "[Migration] Batch %d for table %s has FK violations. "
                                    "Attempting individual record insertion with NULL FK "
                                    "handling...",
                                    batch_num, table_name
                                )

                                (
                                    batch_success_count,
                                    batch_nullified_count,
                                    batch_skipped_count,
                                    fk_failed_batches,
                                    fk_batch_errors
                                ) = handle_foreign_key_violations(
                                    pg_cursor,
                                    pg_conn,
                                    batch_data,
                                    batch_num,
                                    table_name,
                                    common_columns,
                                    insert_sql,
                                    fk_columns,
                                    fk_parent_info,
                                    savepoint_name,
                                    progress_tracker
                                )

                                failed_batches.extend(fk_failed_batches)
                                batch_errors.extend(fk_batch_errors)
                                rows_inserted += batch_success_count

                                if batch_success_count > 0:
                                    continue  # Successfully handled FK violations (partial)
                                else:
                                    continue  # All records failed, already logged

                            # Non-FK error or FK handling failed
                            failed_batches.append(batch_num)
                            batch_errors.append(f"Batch {batch_num}: {error_msg}")
                            logger.warning(
                                "[Migration] Batch %d failed for table %s (rolled back): %s",
                                batch_num, table_name, batch_error
                            )
                            # Continue with next batch instead of failing entire table
                            continue
                        except Exception as rollback_error:
                            # If savepoint rollback fails, check if transaction is aborted
                            rollback_msg = str(rollback_error).lower()
                            if "aborted" in rollback_msg or "does not exist" in rollback_msg:
                                # Transaction aborted or savepoint doesn't exist
                                # Rollback entire transaction
                                logger.warning(
                                    "[Migration] Savepoint rollback failed (transaction aborted "
                                    "or savepoint missing). Rolling back entire transaction for "
                                    "batch %d.",
                                    batch_num
                                )
                                try:
                                    pg_conn.rollback()
                                    failed_batches.append(batch_num)
                                    batch_errors.append(f"Batch {batch_num}: {str(batch_error)}")
                                    continue
                                except Exception:
                                    pass
                            else:
                                # If savepoint rollback fails, rollback entire transaction
                                logger.error(
                                    "[Migration] Failed to rollback savepoint for batch %d: %s",
                                    batch_num, rollback_error
                                )
                                pg_conn.rollback()
                                raise batch_error from rollback_error

                # Log progress for large tables (only if no progress tracker)
                if total_count > LARGE_TABLE_THRESHOLD and not progress_tracker:
                    progress_pct = (rows_inserted / total_count) * 100
                    logger.debug(
                        "[Migration] %s: Batch %d - %d/%d records migrated (%.1f%%)",
                        table_name, batch_num, rows_inserted, total_count, progress_pct
                    )

            # Re-enable foreign key constraints and verify integrity
            # Try to re-enable (may fail if we never disabled them, which is fine)
            try:
                pg_cursor.execute("SET session_replication_role = 'origin'")
                pg_conn.commit()
                logger.debug(
                    "[Migration] Re-enabled foreign key constraints for table %s",
                    table_name
                )

                # Verify foreign key integrity for this table
                # Check if there are any foreign key violations
                try:
                    # Get foreign key constraints for this table
                    fk_check_sql = """
                        SELECT COUNT(*) FROM (
                            SELECT 1 FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
                            LIMIT 1
                        ) fk_check
                    """
                    pg_cursor.execute(fk_check_sql, (table_name,))
                    has_fk = pg_cursor.fetchone()[0] > 0

                    if has_fk:
                        # Try to verify foreign key integrity by checking for violations
                        # This is a best-effort check - PostgreSQL enforces FKs on next operation
                        logger.debug(
                            "[Migration] Foreign key constraints re-enabled for table %s",
                            table_name
                        )
                except Exception as fk_check_error:
                    logger.debug(
                        "[Migration] Could not verify foreign key constraints (non-critical): %s",
                        fk_check_error
                    )
            except Exception as fk_error:
                logger.warning(
                    "[Migration] Could not re-enable foreign key constraints (non-critical): %s",
                    fk_error
                )

            pg_cursor.close()

            # Calculate batch failure rate
            total_batches = batch_num
            failure_rate = (
                len(failed_batches) / total_batches if total_batches > 0 else 0.0
            )

            if failed_batches:
                logger.warning(
                    "[Migration] Table %s: %d/%d batch(es) failed (%.1f%% failure rate): %s",
                    table_name, len(failed_batches), total_batches,
                    failure_rate * 100, ', '.join(map(str, failed_batches))
                )

                # Fail table migration if failure rate exceeds threshold
                if failure_rate > BATCH_FAILURE_THRESHOLD:
                    error_msg = (
                        f"Table {table_name} migration failed: "
                        f"{len(failed_batches)}/{total_batches} batches failed "
                        f"({failure_rate*100:.1f}% failure rate, threshold: "
                        f"{BATCH_FAILURE_THRESHOLD*100:.1f}%). "
                        f"Errors: {'; '.join(batch_errors[:5])}"
                        f"{' (showing first 5)' if len(batch_errors) > 5 else ''}"
                    )
                    logger.error("[Migration] %s", error_msg)
                    return rows_inserted, error_msg

            if rows_inserted < total_count:
                skipped = total_count - rows_inserted
                failed_records = len(failed_batches) * BATCH_SIZE
                conflict_records = max(0, skipped - failed_records)

                if failed_batches:
                    logger.info(
                        "[Migration] Migrated %d/%d records from %s "
                        "(%d skipped due to conflicts, %d failed in %d batches)",
                        rows_inserted, total_count, table_name,
                        conflict_records, failed_records, len(failed_batches)
                    )
                else:
                    logger.info(
                        "[Migration] Migrated %d/%d records from %s "
                        "(%d skipped due to conflicts)",
                        rows_inserted, total_count, table_name, skipped
                    )
            else:
                logger.info("[Migration] Migrated %d records from %s", rows_inserted, table_name)

            # Return error if all batches failed
            if rows_inserted == 0 and total_count > 0 and len(failed_batches) > 0:
                error_msg = (
                    f"All {len(failed_batches)} batches failed for table {table_name}. "
                    f"Errors: {'; '.join(batch_errors[:5])}"
                    f"{' (showing first 5)' if len(batch_errors) > 5 else ''}"
                )
                return 0, error_msg

            # Return warning if some batches failed but below threshold
            if failed_batches:
                warning_msg = (
                    f"{len(failed_batches)} batch(es) failed but below failure threshold. "
                    f"Migrated {rows_inserted}/{total_count} records."
                )
                return rows_inserted, warning_msg

            return rows_inserted, None

        except Exception:
            pg_conn.rollback()
            raise
        finally:
            pg_conn.close()

    except Exception as e:
        error_msg = f"Failed to migrate table {table_name}: {str(e)}"
        logger.error("[Migration] %s", error_msg, exc_info=True)
        return 0, error_msg


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
        "incomplete_tables": []
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
                    (table_name,)
                )
                table_exists_in_sqlite = sqlite_cursor.fetchone() is not None

                if not table_exists_in_sqlite:
                    # Table doesn't exist in SQLite - skip verification
                    logger.debug("[Migration] Table %s does not exist in SQLite, skipping", table_name)
                    continue

                # Count SQLite records (table_name is from trusted source, but quote for safety)
                sqlite_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                sqlite_count = sqlite_cursor.fetchone()[0]

                # Check if table exists in PostgreSQL
                if table_name not in pg_tables:
                    # Table missing in PostgreSQL - CRITICAL ERROR
                    stats["missing_tables"].append(table_name)
                    stats["mismatches"].append({
                        "table": table_name,
                        "sqlite_count": sqlite_count,
                        "postgresql_count": 0,
                        "error": "Table missing in PostgreSQL"
                    })
                    logger.error(
                        "[Migration] CRITICAL: Table %s missing in PostgreSQL (SQLite has %d rows)",
                        table_name, sqlite_count
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
                    stats["mismatches"].append({
                        "table": table_name,
                        "sqlite_count": sqlite_count,
                        "postgresql_count": pg_count,
                        "error": (
                            f"PostgreSQL has {pg_count} rows, SQLite has {sqlite_count} rows "
                            f"(missing {sqlite_count - pg_count} rows)"
                        )
                    })
                    logger.error(
                        "[Migration] CRITICAL: Table %s incomplete in PostgreSQL: "
                        "SQLite=%d, PostgreSQL=%d (missing %d rows)",
                        table_name, sqlite_count, pg_count, sqlite_count - pg_count
                    )
                elif pg_count > sqlite_count:
                    # PostgreSQL has more rows - acceptable (may have new data)
                    stats["tables_migrated"] += 1
                    stats["total_records"] += sqlite_count
                    logger.info(
                        "[Migration] Table %s verified: SQLite=%d, PostgreSQL=%d "
                        "(PostgreSQL has more rows - acceptable)",
                        table_name, sqlite_count, pg_count
                    )
                else:
                    # Exact match - perfect
                    stats["tables_migrated"] += 1
                    stats["total_records"] += sqlite_count
                    logger.debug(
                        "[Migration] Table %s verified: SQLite=%d, PostgreSQL=%d (match)",
                        table_name, sqlite_count, pg_count
                    )

            except Exception as e:
                logger.error(
                    "[Migration] Failed to verify table %s: %s",
                    table_name, e, exc_info=True
                )
                stats["mismatches"].append({
                    "table": table_name,
                    "error": str(e)
                })

        sqlite_conn.close()
        pg_engine.dispose()

        # Determine if verification passed
        # Verification passes only if:
        # 1. No missing tables
        # 2. No incomplete tables (PostgreSQL >= SQLite for all tables)
        # 3. No errors
        is_valid = (
            len(stats["missing_tables"]) == 0 and
            len(stats["incomplete_tables"]) == 0 and
            len([m for m in stats["mismatches"] if "error" in m]) == 0
        )

        if not is_valid:
            logger.error(
                "[Migration] Verification FAILED: %d missing tables, %d incomplete tables, %d errors",
                len(stats["missing_tables"]),
                len(stats["incomplete_tables"]),
                len([m for m in stats["mismatches"] if "error" in m])
            )
        else:
            logger.info(
                "[Migration] Verification PASSED: %d tables verified, %d total records",
                stats["tables_migrated"],
                stats["total_records"]
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
            "statistics": stats
        }

        with open(MIGRATION_MARKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(marker_data, f, indent=2)

        logger.info("[Migration] Migration marker created: %s", MIGRATION_MARKER_FILE)
        return True
    except Exception as e:
        logger.error("[Migration] Failed to create migration marker: %s", e)
        return False


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
                    if not pk_cols.get('constrained_columns'):
                        continue

                    pk_col = pk_cols['constrained_columns'][0]

                    # Get the maximum ID value (use proper identifier quoting)
                    result = conn.execute(text(f'SELECT MAX("{pk_col}") FROM "{table_name}"'))
                    max_id = result.scalar()

                    if max_id is not None and max_id > 0:
                        # Use pg_get_serial_sequence() to find actual sequence name
                        # This is more reliable than assuming naming convention
                        # pg_get_serial_sequence expects string literals (single quotes), not identifiers
                        seq_result = conn.execute(text(
                            f"SELECT pg_get_serial_sequence('{table_name}', '{pk_col}')"
                        ))
                        sequence_name = seq_result.scalar()

                        if sequence_name:
                            # Remove schema prefix if present (e.g., "public.users_id_seq" -> "users_id_seq")
                            if '.' in sequence_name:
                                sequence_name = sequence_name.split('.')[-1]

                            try:
                                conn.execute(text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)"))
                                conn.commit()
                                sequences_reset += 1
                                logger.debug(
                                    "[Migration] Reset sequence %s to %d (table: %s)",
                                    sequence_name, max_id + 1, table_name
                                )
                            except Exception as seq_error:
                                logger.warning(
                                    "[Migration] Failed to reset sequence %s for table %s: %s",
                                    sequence_name, table_name, seq_error
                                )
                                sequences_failed.append(f"{table_name}.{pk_col}")
                        else:
                            # No sequence found - might be a non-serial primary key
                            logger.debug(
                                "[Migration] No sequence found for %s.%s (may not be serial)",
                                table_name, pk_col
                            )

                except Exception as e:
                    logger.warning("[Migration] Could not reset sequence for %s: %s", table_name, e)
                    sequences_failed.append(table_name)
                    continue

        if sequences_failed:
            logger.warning(
                "[Migration] PostgreSQL sequences reset: %d succeeded, %d failed: %s",
                sequences_reset, len(sequences_failed), ', '.join(sequences_failed)
            )
        else:
            logger.info("[Migration] PostgreSQL sequences reset (%d sequences)", sequences_reset)
    except Exception as e:
        logger.warning("[Migration] Failed to reset sequences: %s", e)
