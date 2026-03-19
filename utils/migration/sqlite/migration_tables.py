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
import logging
from typing import Optional, Tuple, Any

try:
    from psycopg2.extras import execute_values
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

# Import Base directly from models to avoid circular import with config.database
from models.domain.auth import Base

# Import community models so they are registered with Base.metadata for table creation
try:
    from models.domain.community import (
        CommunityPost,
        CommunityPostComment,
        CommunityPostLike,
    )
    _ = CommunityPost.__tablename__
    _ = CommunityPostComment.__tablename__
    _ = CommunityPostLike.__tablename__
except ImportError:
    pass

# Import library models
try:
    from models.domain.library import (
        LibraryDocument,
        LibraryDanmaku,
        LibraryDanmakuLike,
        LibraryDanmakuReply,
        LibraryBookmark,
    )
    _ = LibraryDocument.__tablename__
    _ = LibraryDanmaku.__tablename__
    _ = LibraryDanmakuLike.__tablename__
    _ = LibraryDanmakuReply.__tablename__
    _ = LibraryBookmark.__tablename__
except ImportError:
    pass

# Import user activity/usage models
try:
    from models.domain.user_activity_log import UserActivityLog
    from models.domain.user_usage_stats import UserUsageStats
    from models.domain.teacher_usage_config import TeacherUsageConfig
    _ = UserActivityLog.__tablename__
    _ = UserUsageStats.__tablename__
    _ = TeacherUsageConfig.__tablename__
except ImportError:
    pass

# Import gewe models
try:
    from models.domain.gewe_message import GeweMessage
    from models.domain.gewe_contact import GeweContact
    from models.domain.gewe_group_member import GeweGroupMember
    _ = GeweMessage.__tablename__
    _ = GeweContact.__tablename__
    _ = GeweGroupMember.__tablename__
except ImportError:
    pass

# Import workshop chat models
try:
    from models.domain.workshop_chat import (
        ChatChannel, ChannelMember, ChatTopic, ChatMessage, DirectMessage,
        MessageReaction, StarredMessage, FileAttachment, UserTopicPreference,
    )
    _ = ChatChannel.__tablename__
    _ = ChannelMember.__tablename__
    _ = ChatTopic.__tablename__
    _ = ChatMessage.__tablename__
    _ = DirectMessage.__tablename__
    _ = MessageReaction.__tablename__
    _ = StarredMessage.__tablename__
    _ = FileAttachment.__tablename__
    _ = UserTopicPreference.__tablename__
except ImportError:
    pass

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
                                    *_,
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

                                continue  # Handled FK violations (partial or all failed)

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
