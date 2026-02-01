"""
SQLite to PostgreSQL Data Migration Module

Migrates all data from SQLite database to PostgreSQL database.
This is a one-time migration that runs automatically on first launch.

Separate from utils/db_migration.py which handles schema migrations (adding columns).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import sqlite3
import logging
import importlib.util
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

# Import Base directly from models to avoid circular import with config.database
from models.domain.auth import Base

# Import all models to ensure they're registered with Base.metadata
# This is critical for table creation during migration
try:
    from models.domain.diagrams import Diagram
    _ = Diagram.__tablename__
except ImportError:
    pass

try:
    from models.domain.debateverse import (
        DebateSession, DebateParticipant, DebateMessage, DebateJudgment
    )
    _ = DebateSession.__tablename__
    _ = DebateParticipant.__tablename__
    _ = DebateMessage.__tablename__
    _ = DebateJudgment.__tablename__
except ImportError:
    pass

try:
    from models.domain.school_zone import (
        SharedDiagram, SharedDiagramLike, SharedDiagramComment
    )
    _ = SharedDiagram.__tablename__
    _ = SharedDiagramLike.__tablename__
    _ = SharedDiagramComment.__tablename__
except ImportError:
    pass

try:
    from models.domain.pinned_conversations import PinnedConversation
    _ = PinnedConversation.__tablename__
except ImportError:
    pass

try:
    from models.domain.dashboard_activity import DashboardActivity
    _ = DashboardActivity.__tablename__
except ImportError:
    pass

from utils.migration.sqlite.migration_utils import (
    get_sqlite_db_path,
    is_migration_completed,
    load_migration_progress,
    save_migration_progress,
    clear_migration_progress,
    acquire_migration_lock,
    release_migration_lock,
    is_postgresql_empty,
    check_table_completeness,
    BACKUP_DIR as MIGRATION_BACKUP_DIR
)
from utils.migration.sqlite.migration_backup import (
    backup_sqlite_database,
    move_sqlite_database_to_backup
)
from utils.migration.sqlite.migration_tables import (
    get_table_migration_order,
    migrate_table,
    verify_migration,
    create_migration_marker,
    reset_postgresql_sequences
)
from utils.migration.sqlite.migration_progress import (
    MigrationProgressTracker,
    STAGE_PREREQUISITES,
    STAGE_LOCK,
    STAGE_BACKUP,
    STAGE_CONNECT,
    STAGE_CREATE_TABLES,
    STAGE_MIGRATE_TABLES,
    STAGE_RESET_SEQUENCES,
    STAGE_VERIFY,
    STAGE_MOVE_SQLITE,
    STAGE_CREATE_MARKER,
    STAGE_COMPLETE
)
from utils.migration.sqlite_to_postgresql.table_creation import (
    create_enum_types,
    create_table_without_indexes,
    create_table_indexes
)

logger = logging.getLogger(__name__)

PSYCOPG2_AVAILABLE = importlib.util.find_spec('psycopg2') is not None

# Lazy import to avoid circular dependency with config.database
# Use importlib to import at module level while deferring execution
def _get_init_db_func():
    """Get init_db function, importing lazily to avoid circular dependency."""
    if not hasattr(_get_init_db_func, '_cached_module'):
        _get_init_db_func._cached_module = importlib.import_module('config.database')
    return _get_init_db_func._cached_module.init_db


def migrate_sqlite_to_postgresql(force: bool = False) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Migrate all data from SQLite to PostgreSQL.

    This function:
    1. Checks if SQLite database exists
    2. Checks if migration already completed
    3. Checks if PostgreSQL is empty (or allows resume if force=True)
    4. Backs up SQLite database (BEFORE migration)
    5. Ensures PostgreSQL tables exist
    6. Migrates all tables
    7. Resets PostgreSQL sequences
    8. Verifies migration
    9. Moves SQLite database to backup (AFTER successful migration)
    10. Creates migration marker

    Args:
        force: If True, allow migration even if PostgreSQL has some tables (for resume)

    Returns:
        Tuple of (success, error_message, statistics)
    """
    if not PSYCOPG2_AVAILABLE:
        return False, "psycopg2 not installed. Install with: pip install psycopg2-binary", None

    # Get SQLite database path first (before checking marker)
    sqlite_path = get_sqlite_db_path()

    # Check if migration already completed (marker file exists)
    # BUT: If SQLite still exists in original location, we should sync and move it
    if is_migration_completed():
        # Check if SQLite was actually moved to backup
        backup_dir = MIGRATION_BACKUP_DIR
        moved_files = []
        if backup_dir.exists():
            moved_files = list(backup_dir.glob("mindgraph.db.migrated.*.sqlite"))

        # If SQLite exists in original location but wasn't moved, allow migration
        # This handles cases where migration completed but move failed
        if sqlite_path and sqlite_path.exists():
            try:
                if not moved_files:
                    logger.warning(
                        "[Migration] Marker file exists but SQLite database still in original location: %s. "
                        "Migration will proceed to sync data and move SQLite to backup.",
                        sqlite_path
                    )
                    # Don't return - continue with migration
                else:
                    logger.info(
                        "[Migration] Migration already completed (marker file exists) "
                        "and SQLite moved to backup: %s. Skipping.",
                        moved_files[0].name
                    )
                    return True, None, None
            except Exception:
                # If we can't check, be safe and skip
                logger.info(
                    "[Migration] Migration already completed (marker file exists), skipping"
                )
                return True, None, None
        else:
            # No SQLite in original location - migration truly complete
            logger.info(
                "[Migration] Migration already completed (marker file exists, SQLite moved), skipping"
            )
            return True, None, None

    # Get SQLite database path (if not already retrieved above)
    if not sqlite_path:
        sqlite_path = get_sqlite_db_path()
        if not sqlite_path:
            logger.info("[Migration] No SQLite database found, skipping migration")
            return True, None, None

    # Check if path exists and is accessible
    try:
        if not sqlite_path.exists():
            logger.info("[Migration] SQLite database path does not exist: %s", sqlite_path)
            return True, None, None
    except PermissionError:
        logger.warning(
            "[Migration] Permission denied accessing SQLite database path: %s. Skipping migration.",
            sqlite_path
        )
        return True, None, None
    except Exception as e:
        logger.warning(
            "[Migration] Error checking SQLite database path %s: %s. Skipping migration.",
            sqlite_path, e
        )
        return True, None, None

    # Note: We allow migration to proceed even if backup has moved files
    # The migration will compare SQLite with PostgreSQL and only migrate missing data
    # This handles cases where SQLite was restored or has new data
    backup_dir = MIGRATION_BACKUP_DIR
    if backup_dir.exists():
        moved_files = list(backup_dir.glob("mindgraph.db.migrated.*.sqlite"))
        if moved_files:
            logger.info(
                "[Migration] Note: SQLite database exists at %s and backup file exists: %s. "
                "Migration will proceed with incremental update - comparing SQLite with PostgreSQL "
                "and migrating only missing data.",
                sqlite_path, moved_files[0].name
            )

    # Get PostgreSQL URL - use defaults from env.example if not set
    pg_url = os.getenv('DATABASE_URL', '')

    # If DATABASE_URL not set, construct from individual PostgreSQL settings
    # These defaults match env.example
    if not pg_url or 'postgresql' not in pg_url.lower():
        # Try to construct from individual PostgreSQL environment variables
        # Defaults match env.example values
        pg_user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
        pg_password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
        pg_host = os.getenv('POSTGRESQL_HOST', 'localhost')
        pg_port = os.getenv('POSTGRESQL_PORT', '5432')
        pg_database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

        # Construct PostgreSQL URL from components
        pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
        logger.info("[Migration] Using PostgreSQL configuration from environment variables")
        logger.debug(
            "[Migration] Constructed DATABASE_URL: postgresql://%s:***@%s:%s/%s",
            pg_user, pg_host, pg_port, pg_database
        )

    # Check if PostgreSQL is empty (or allow resume with force flag)
    is_empty, empty_error = is_postgresql_empty(pg_url, force=force, sqlite_path=sqlite_path)
    if not is_empty:
        if force:
            logger.error("[Migration] Cannot proceed even with force flag: %s", empty_error)
        else:
            logger.warning("[Migration] PostgreSQL database is not empty, skipping migration")
            logger.warning("[Migration] To force migration, use force=True or empty PostgreSQL database first")
        return False, empty_error or "PostgreSQL database is not empty", None

    # Get table list to initialize progress tracker
    tables = get_table_migration_order()
    total_tables = len(tables)

    logger.info("[Migration] Starting data migration from SQLite to PostgreSQL...")
    logger.info("[Migration] SQLite database: %s", sqlite_path)
    # Mask password in URL for logging
    masked_url = pg_url
    if '@' in pg_url:
        url_parts = pg_url.split('@')
        if len(url_parts) > 0:
            user_pass = url_parts[0].split('//')[1] if '//' in url_parts[0] else ''
            masked_url = pg_url.replace(user_pass, '***') if user_pass else pg_url
    logger.info("[Migration] PostgreSQL URL: %s", masked_url)

    # Initialize progress tracker
    progress_tracker = MigrationProgressTracker(total_tables=total_tables)

    sqlite_conn = None
    pg_engine = None
    migration_lock = None
    backup_path = None

    try:
        with progress_tracker:
            # Stage 0: Prerequisites check
            progress_tracker.update_stage(STAGE_PREREQUISITES)

            # STEP 1: Backup SQLite database BEFORE migration starts
            progress_tracker.update_stage(STAGE_BACKUP, "Backing up SQLite database...")
            backup_path = backup_sqlite_database(sqlite_path, progress_tracker)
            if not backup_path:
                error_msg = "Failed to backup SQLite database"
                logger.error("[Migration] %s - cannot proceed without backup", error_msg)
                progress_tracker.add_error(error_msg)
                return False, error_msg, None

            # Stage 1: Acquire migration lock
            progress_tracker.update_stage(STAGE_LOCK, "Acquiring migration lock...")
            migration_lock = acquire_migration_lock()
            if not migration_lock:
                error_msg = "Another migration is already in progress (lock file exists)"
                logger.error("[Migration] %s", error_msg)
                progress_tracker.add_error(error_msg)
                return False, error_msg, None

            # Stage 2: Connect to databases
            progress_tracker.update_stage(STAGE_CONNECT, "Connecting to databases...")
            sqlite_conn = sqlite3.connect(str(sqlite_path))
            pg_engine = create_engine(pg_url)

            # STEP 2: Ensure PostgreSQL tables exist to match SQLite schema
            progress_tracker.update_stage(STAGE_CREATE_TABLES, "Creating PostgreSQL tables...")

            # Create ENUM types first (required before table creation)
            create_enum_types(pg_engine)

            # First, try init_db() which creates tables using SQLAlchemy models
            # This ensures tables match the expected schema
            # Lazy import to avoid circular dependency with config.database
            try:
                init_db_func = _get_init_db_func()
                init_db_func()
                logger.debug("[Migration] init_db() completed")
            except Exception as init_error:
                # init_db() might fail due to duplicate indexes, but tables might still be created
                logger.debug(
                    "[Migration] init_db() encountered error (may be non-critical): %s",
                    init_error
                )

            # Verify and ensure ALL required tables exist
            inspector = inspect(pg_engine)
            existing_tables = set(inspector.get_table_names())
            expected_tables = set(Base.metadata.tables.keys())
            missing_tables = expected_tables - existing_tables

            if missing_tables:
                logger.info(
                    "[Migration] Creating %d missing table(s) in PostgreSQL: %s",
                    len(missing_tables),
                    ', '.join(sorted(missing_tables))
                )

                # Get tables in migration order (respects foreign key dependencies)
                migration_order = get_table_migration_order()
                # Filter to only include missing tables, preserving order
                tables_to_create = [t for t in migration_order if t in missing_tables]
                # Add any tables not in migration order (shouldn't happen, but be safe)
                tables_not_in_order = missing_tables - set(migration_order)
                if tables_not_in_order:
                    logger.warning(
                        "[Migration] Found %d table(s) not in migration order: %s",
                        len(tables_not_in_order),
                        ', '.join(sorted(tables_not_in_order))
                    )
                    tables_to_create.extend(sorted(tables_not_in_order))

                # Create missing tables one by one in dependency order
                # This ensures parent tables are created before child tables
                tables_created = 0
                tables_failed = []

                # Get existing tables once for performance
                inspector = inspect(pg_engine)
                existing_tables_set = set(inspector.get_table_names())

                for table_name in tables_to_create:
                    try:
                        table = Base.metadata.tables[table_name]

                        # Create table without indexes first to avoid index creation failures
                        # This ensures table is created even if indexes already exist
                        if create_table_without_indexes(
                            pg_engine, table_name, table, existing_tables_set
                        ):
                            # Table created successfully, now add indexes separately
                            create_table_indexes(pg_engine, table_name, table)

                            inspector = inspect(pg_engine)
                            if table_name in inspector.get_table_names():
                                tables_created += 1
                                logger.info("[Migration] ✓ Created table: %s", table_name)
                            else:
                                logger.error(
                                    "[Migration] ✗ Table creation reported success but table %s doesn't exist",
                                    table_name
                                )
                                tables_failed.append(table_name)
                        else:
                            # Table creation failed
                            tables_failed.append(table_name)
                    except (OperationalError, ProgrammingError) as table_error:
                        error_msg = str(table_error).lower()
                        # Check if error is about table/index already existing
                        if ("already exists" in error_msg or
                            "duplicate" in error_msg or
                            ("relation" in error_msg and "exists" in error_msg)):
                            # Verify table actually exists (index errors might be caught here)
                            inspector = inspect(pg_engine)
                            if table_name in inspector.get_table_names():
                                logger.debug("[Migration] Table %s already exists: %s", table_name, table_error)
                                tables_created += 1
                            else:
                                # Index/constraint error but table doesn't exist - need to retry
                                logger.warning(
                                    "[Migration] Table %s creation error (likely index): %s. "
                                    "Table doesn't exist, will retry.",
                                    table_name, table_error
                                )
                                tables_failed.append(table_name)
                        else:
                            # Check if it's a foreign key dependency error
                            if "undefinedtable" in error_msg or "does not exist" in error_msg:
                                # Parent table doesn't exist yet - will retry after other tables are created
                                logger.debug(
                                    "[Migration] Table %s depends on missing parent table: %s",
                                    table_name, table_error
                                )
                                tables_failed.append(table_name)
                            else:
                                logger.error("[Migration] ✗ Failed to create table %s: %s", table_name, table_error)
                                tables_failed.append(table_name)
                    except Exception as table_error:
                        logger.error("[Migration] ✗ Unexpected error creating table %s: %s", table_name, table_error)
                        tables_failed.append(table_name)

                # Retry failed tables (dependencies might have been created)
                # Use multiple retry passes to handle complex dependency chains
                max_retries = 5  # Increased from 3 to handle complex dependency chains
                for retry_pass in range(max_retries):
                    if not tables_failed:
                        break

                    logger.info(
                        "[Migration] Retry pass %d/%d: Retrying %d failed table(s): %s",
                        retry_pass + 1, max_retries, len(tables_failed),
                        ', '.join(tables_failed)
                    )

                    # Refresh inspector to get current table state
                    inspector = inspect(pg_engine)
                    existing_tables = set(inspector.get_table_names())

                    retry_failed = []
                    for table_name in tables_failed:
                        # Check if table was created by another process/retry
                        if table_name in existing_tables:
                            logger.debug("[Migration] Table %s now exists (created by another process)", table_name)
                            tables_created += 1
                            continue

                        try:
                            table = Base.metadata.tables[table_name]

                            # Check if parent tables exist (for foreign key dependencies)
                            parent_tables_missing = []
                            for fk in table.foreign_keys:
                                try:
                                    parent_table = fk.column.table.name
                                    if parent_table not in existing_tables and parent_table != table_name:
                                        parent_tables_missing.append(parent_table)
                                except AttributeError as e:
                                    logger.error(
                                        "[Migration] Error getting parent table for FK %s in table %s: %s",
                                        fk.parent.name if hasattr(fk, 'parent') else 'unknown',
                                        table_name, e
                                    )
                                    # If we can't determine parent table, skip this FK check
                                    continue

                            if parent_tables_missing:
                                logger.warning(
                                    "[Migration] Table %s still waiting for parent tables: %s (existing: %s)",
                                    table_name, ', '.join(parent_tables_missing),
                                    ', '.join(sorted(existing_tables))[:200]  # Limit length
                                )
                                retry_failed.append(table_name)
                                continue

                            # Try to create table without indexes first
                            if create_table_without_indexes(
                                pg_engine, table_name, table, existing_tables
                            ):
                                # Table created, add indexes separately
                                create_table_indexes(pg_engine, table_name, table)

                                # Verify table was actually created
                                inspector = inspect(pg_engine)
                                if table_name in inspector.get_table_names():
                                    tables_created += 1
                                    logger.info(
                                        "[Migration] ✓ Created table (retry %d): %s",
                                        retry_pass + 1, table_name
                                    )
                                    # Refresh existing_tables and inspector so subsequent
                                    # tables in this pass can see the new table
                                    inspector = inspect(pg_engine)  # Create fresh inspector
                                    existing_tables = set(inspector.get_table_names())
                                else:
                                    logger.error(
                                        "[Migration] ✗ Table creation reported success but table %s still missing",
                                        table_name
                                    )
                                    retry_failed.append(table_name)
                            else:
                                retry_failed.append(table_name)
                        except (OperationalError, ProgrammingError) as table_error:
                            error_msg = str(table_error).lower()
                            if ("already exists" in error_msg or
                                "duplicate" in error_msg or
                                ("relation" in error_msg and "exists" in error_msg)):
                                # Verify table actually exists
                                inspector = inspect(pg_engine)
                                if table_name in inspector.get_table_names():
                                    logger.debug(
                                        "[Migration] Table %s already exists (retry %d): %s",
                                        retry_pass + 1, table_name, table_error
                                    )
                                    tables_created += 1
                                else:
                                    # Index/constraint error but table doesn't exist
                                    logger.warning(
                                        "[Migration] Table %s creation error (likely index): %s. Will retry.",
                                        table_name, table_error
                                    )
                                    retry_failed.append(table_name)
                            elif "undefinedtable" in error_msg or "does not exist" in error_msg:
                                # Parent table still missing
                                logger.debug(
                                    "[Migration] Table %s still depends on missing parent (retry %d): %s",
                                    retry_pass + 1, table_name, table_error
                                )
                                retry_failed.append(table_name)
                            else:
                                logger.error(
                                    "[Migration] ✗ Failed to create table %s (retry %d): %s",
                                    retry_pass + 1, table_name, table_error
                                )
                                retry_failed.append(table_name)
                        except Exception as table_error:
                            logger.error(
                                "[Migration] ✗ Unexpected error creating table %s (retry %d): %s",
                                retry_pass + 1, table_name, table_error
                            )
                            retry_failed.append(table_name)

                    tables_failed = retry_failed

                # Verify all tables were created
                inspector = inspect(pg_engine)
                existing_tables = set(inspector.get_table_names())
                still_missing = expected_tables - existing_tables

                if still_missing:
                    logger.error(
                        "[Migration] CRITICAL: %d table(s) still missing after creation attempt: %s",
                        len(still_missing),
                        ', '.join(sorted(still_missing))
                    )
                    logger.error("[Migration] Cannot proceed with data migration without these tables")
                    return False, f"Failed to create required tables: {', '.join(sorted(still_missing))}", None

                logger.info(
                    "[Migration] ✓ All %d required tables exist in PostgreSQL",
                    len(expected_tables)
                )
            else:
                logger.info("[Migration] ✓ All %d expected tables already exist in PostgreSQL", len(expected_tables))

            logger.info("[Migration] PostgreSQL tables verified/created successfully")

            # STEP 3: Migrate each table (with resume capability)
            progress_tracker.update_stage(STAGE_MIGRATE_TABLES, "Migrating tables...")
            migration_stats = {
                "tables_migrated": 0,
                "total_records": 0,
                "errors": [],
                "warnings": [],  # Track non-fatal warnings (partial successes)
                "table_progress": {}  # Track progress per table for resume capability
            }

            # Load previous progress if resuming
            previous_progress = load_migration_progress()
            completed_tables = set(previous_progress.get("completed_tables", []))

            if completed_tables and force:
                logger.info(
                    "[Migration] Resuming migration: %d table(s) already completed: %s",
                    len(completed_tables),
                    ', '.join(sorted(completed_tables))
                )

            # Create inspector once and reuse for all tables (performance optimization)
            inspector = inspect(pg_engine)

            for table_idx, table_name in enumerate(tables, 1):
                try:
                    # Skip if table was already successfully migrated (resume capability)
                    if table_name in completed_tables:
                        logger.info(
                            "[Migration] Skipping table %d/%d: %s (already migrated)",
                            table_idx, total_tables, table_name
                        )
                        # Load previous stats for this table
                        if "table_progress" in previous_progress:
                            prev_table_progress = previous_progress["table_progress"].get(table_name, {})
                            if prev_table_progress.get("status") == "completed":
                                migration_stats["tables_migrated"] += 1
                                migration_stats["total_records"] += prev_table_progress.get("records_migrated", 0)
                                migration_stats["table_progress"][table_name] = prev_table_progress
                        continue

                    # Check if table exists in SQLite and get record count
                    sqlite_cursor = sqlite_conn.cursor()
                    sqlite_cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,)
                    )
                    if not sqlite_cursor.fetchone():
                        logger.debug("[Migration] Table %s does not exist in SQLite, skipping", table_name)
                        migration_stats["table_progress"][table_name] = {
                            "status": "skipped",
                            "records_migrated": 0,
                            "reason": "table does not exist in SQLite"
                        }
                        continue

                    # Get total record count for progress tracking
                    # (table_name is from trusted source, but quote for safety)
                    sqlite_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    total_records = sqlite_cursor.fetchone()[0]

                    # Check if table already has complete data in PostgreSQL
                    # Reuse inspector for performance
                    is_complete, _, pg_count = check_table_completeness(
                        sqlite_path, pg_url, table_name, pg_engine, inspector
                    )
                    if is_complete and pg_count is not None and pg_count > 0:
                        logger.info(
                            "[Migration] Skipping table %d/%d: %s (already has complete data: %d rows)",
                            table_idx, total_tables, table_name, pg_count
                        )
                        completed_tables.add(table_name)
                        migration_stats["tables_migrated"] += 1
                        migration_stats["total_records"] += pg_count
                        migration_stats["table_progress"][table_name] = {
                            "status": "completed",
                            "records_migrated": pg_count,
                            "reason": "already has complete data"
                        }
                        continue

                    # Start table migration in progress tracker
                    progress_tracker.start_table_migration(table_name, table_idx, total_records)

                    # Save progress before migrating this table
                    save_migration_progress({
                        "completed_tables": list(completed_tables),
                        "table_progress": migration_stats["table_progress"],
                        "current_table": table_name
                    })

                    # Pass inspector instance and progress tracker for performance
                    record_count, error = migrate_table(
                        sqlite_conn, table_name, pg_engine, inspector, progress_tracker
                    )

                    # Determine if error is a warning (partial success) or failure
                    is_warning = error is not None and (
                        "batch(es) failed but below failure threshold" in error or
                        "warning" in error.lower()
                    )
                    is_failure = error is not None and not is_warning

                    # Track progress per table
                    migration_stats["table_progress"][table_name] = {
                        "status": "completed" if not is_failure else "failed",
                        "records_migrated": record_count,
                        "error": error,
                        "warning": error if is_warning else None
                    }

                    if is_failure:
                        migration_stats["errors"].append(error)
                        progress_tracker.add_error(f"{table_name}: {error}")
                        # Don't fail immediately - continue with other tables
                        logger.error("[Migration] Error migrating %s: %s", table_name, error)
                        # Save progress even on error (for resume)
                        save_migration_progress({
                            "completed_tables": list(completed_tables),
                            "table_progress": migration_stats["table_progress"],
                            "errors": migration_stats["errors"]
                        })
                    elif is_warning:
                        # Warning: partial success (some batches failed but below threshold)
                        migration_stats.setdefault("warnings", []).append(f"{table_name}: {error}")
                        logger.warning("[Migration] Warning migrating %s: %s", table_name, error)
                        # Still mark as completed since records were migrated
                        completed_tables.add(table_name)
                        migration_stats["tables_migrated"] += 1
                        migration_stats["total_records"] += record_count
                        progress_tracker.complete_table(record_count)
                        # Save progress
                        save_migration_progress({
                            "completed_tables": list(completed_tables),
                            "table_progress": migration_stats["table_progress"],
                            "tables_migrated": migration_stats["tables_migrated"],
                            "total_records": migration_stats["total_records"],
                            "warnings": migration_stats.get("warnings", [])
                        })
                    else:
                        # Mark table as completed
                        completed_tables.add(table_name)
                        migration_stats["tables_migrated"] += 1
                        migration_stats["total_records"] += record_count
                        progress_tracker.complete_table(record_count)
                        # Save progress after successful migration
                        save_migration_progress({
                            "completed_tables": list(completed_tables),
                            "table_progress": migration_stats["table_progress"],
                            "tables_migrated": migration_stats["tables_migrated"],
                            "total_records": migration_stats["total_records"]
                        })

                except Exception as e:
                    error_msg = f"Failed to migrate table {table_name}: {str(e)}"
                    logger.error("[Migration] %s", error_msg, exc_info=True)
                    migration_stats["errors"].append(error_msg)
                    progress_tracker.add_error(error_msg)
                    migration_stats["table_progress"][table_name] = {
                        "status": "failed",
                        "records_migrated": 0,
                        "error": error_msg
                    }
                    # Save progress even on exception
                    save_migration_progress({
                        "completed_tables": list(completed_tables),
                        "table_progress": migration_stats["table_progress"],
                        "errors": migration_stats["errors"]
                    })

            # STEP 5: Reset PostgreSQL sequences
            progress_tracker.update_stage(STAGE_RESET_SEQUENCES, "Resetting PostgreSQL sequences...")
            reset_postgresql_sequences(pg_engine)

            # STEP 6: Verify migration
            progress_tracker.update_stage(STAGE_VERIFY, "Verifying migration...")
            is_valid, verify_stats = verify_migration(sqlite_path, pg_url)

            if not is_valid:
                error_msg = f"Migration verification failed: {verify_stats.get('mismatches', [])}"
                logger.error("[Migration] %s", error_msg)
                logger.error(
                    "[Migration] Migration failed verification - "
                    "PostgreSQL may be in inconsistent state"
                )
                logger.error("[Migration] Backup available at: %s", backup_path)
                progress_tracker.add_error(error_msg)
                # Clear progress file on verification failure to allow full retry
                logger.info("[Migration] Clearing progress file to allow full retry")
                clear_migration_progress()
                progress_tracker.print_summary(migration_stats)
                return False, error_msg, migration_stats

            # STEP 7: Move SQLite database to backup (only after successful migration)
            # This is critical to avoid confusion - SQLite should not remain in original location
            progress_tracker.update_stage(STAGE_MOVE_SQLITE, "Moving SQLite to backup...")
            move_success = move_sqlite_database_to_backup(sqlite_path, sqlite_conn)
            if not move_success:
                logger.error(
                    "[Migration] CRITICAL: Failed to move SQLite database after successful migration"
                )
                logger.error(
                    "[Migration] Original SQLite database still exists at: %s", sqlite_path
                )
                logger.error(
                    "[Migration] This may cause confusion - SQLite should be moved to backup folder"
                )
                logger.error(
                    "[Migration] Please manually move the database to backup folder "
                    "to prevent accidental reuse"
                )
                logger.error(
                    "[Migration] Suggested command: mv %s backup/mindgraph.db.migrated.manual.sqlite",
                    sqlite_path
                )
                # Don't fail migration - data is already migrated successfully
                # But log clearly that manual intervention is needed

            # STEP 8: Create migration marker
            progress_tracker.update_stage(
                STAGE_CREATE_MARKER, "Creating migration marker..."
            )
            final_stats = {
                **migration_stats,
                "verification": verify_stats,
                "backup_path": str(backup_path)
            }
            create_migration_marker(backup_path, final_stats)

            # Clear progress file after successful migration
            clear_migration_progress()

            # Final stage
            progress_tracker.update_stage(STAGE_COMPLETE, "Migration Complete!")

            # Print summary
            progress_tracker.print_summary(final_stats)

            logger.info("[Migration] Migration completed successfully!")
            logger.info("[Migration] Tables migrated: %d", migration_stats["tables_migrated"])
            logger.info("[Migration] Total records: %d", migration_stats["total_records"])
            logger.info("[Migration] Backup created: %s", backup_path)
            if move_success:
                logger.info("[Migration] SQLite database moved to backup")

            return True, None, final_stats

    except Exception as e:
        error_msg = f"Migration failed: {str(e)}"
        logger.error("[Migration] %s", error_msg, exc_info=True)
        logger.error("[Migration] Migration failed - PostgreSQL may be in inconsistent state")
        if backup_path:
            logger.error("[Migration] Backup available at: %s - you can restore from backup", backup_path)
        return False, error_msg, None

    finally:
        # Release migration lock
        release_migration_lock(migration_lock)

        # Clean up connections
        if sqlite_conn:
            try:
                sqlite_conn.close()
            except Exception:
                pass
        if pg_engine:
            pg_engine.dispose()
