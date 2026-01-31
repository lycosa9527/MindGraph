"""
PostgreSQL schema migration utilities.

This module provides functions for running PostgreSQL database schema migrations.
Currently supports PostgreSQL only (SQLite migration is handled separately).
"""

import logging
from typing import Any, Tuple, Dict
from sqlalchemy import inspect, text

# Lazy import to avoid circular dependency with config.database
# Import here ensures config.database is fully initialized when called
try:
    import config.database as database_module
except ImportError:
    database_module = None

from utils.migration.postgresql.schema_helpers import (
    add_column_postgresql,
    create_table_indexes,
    fix_postgresql_sequence
)
from utils.migration.postgresql.schema_table_ops import create_missing_tables

logger = logging.getLogger(__name__)


def verify_migration_results(
    db_engine, base, expected_tables
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify migration results by checking tables, columns, sequences, and indexes.

    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata
        expected_tables: Set of expected table names

    Returns:
        tuple: (success: bool, details: dict with verification results)
    """
    inspector = inspect(db_engine)
    final_existing_tables = set(inspector.get_table_names())
    final_missing_tables = expected_tables - final_existing_tables

    verification_success = True
    details = {
        'tables_missing': list(final_missing_tables),
        'columns_missing': {},
        'sequences_missing': {},
        'indexes_missing': {}
    }

    # Verify tables
    if final_missing_tables:
        verification_success = False
    else:
        # Verify columns
        for table_name in sorted(final_existing_tables & expected_tables):
            table = base.metadata.tables[table_name]
            existing_columns = {
                col['name'] for col in inspector.get_columns(table_name)
            }
            expected_columns = {col.name for col in table.columns}
            missing_cols = expected_columns - existing_columns
            if missing_cols:
                details['columns_missing'][table_name] = list(missing_cols)
                verification_success = False

        # Verify sequences for primary key columns
        with db_engine.connect() as conn:
            for table_name in sorted(final_existing_tables & expected_tables):
                table = base.metadata.tables[table_name]
                for column in table.columns:
                    if column.primary_key and getattr(column, 'autoincrement',
                                                       False):
                        column_type_str = str(column.type).upper()
                        if ('INTEGER' in column_type_str or
                                'BIGINT' in column_type_str or
                                'SMALLINT' in column_type_str):
                            sequence_name = f"{table_name}_{column.name}_seq"
                            seq_check = conn.execute(text(
                                "SELECT EXISTS(SELECT 1 FROM pg_sequences "
                                "WHERE schemaname = 'public' AND "
                                "sequencename = :seq_name)"
                            ), {"seq_name": sequence_name})
                            sequence_exists = seq_check.scalar()
                            if not sequence_exists:
                                if table_name not in details['sequences_missing']:
                                    details['sequences_missing'][table_name] = []
                                details['sequences_missing'][table_name].append(
                                    sequence_name
                                )
                                verification_success = False

        # Verify indexes
        for table_name in sorted(final_existing_tables & expected_tables):
            table = base.metadata.tables[table_name]
            existing_indexes = {
                idx['name'] for idx in inspector.get_indexes(table_name)
            }
            expected_indexes = {idx.name for idx in table.indexes}
            missing_idxs = expected_indexes - existing_indexes
            if missing_idxs:
                details['indexes_missing'][table_name] = list(missing_idxs)
                verification_success = False

    return verification_success, details


def check_database_status(db_engine, base) -> Dict[str, Any]:
    """
    Check current database status (tables, columns).

    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata

    Returns:
        dict: Status information with expected_tables, existing_tables,
              missing_tables, missing_columns
    """
    inspector = inspect(db_engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(base.metadata.tables.keys())
    missing_tables = expected_tables - existing_tables

    missing_columns = {}
    for table_name in sorted(existing_tables & expected_tables):
        table = base.metadata.tables[table_name]
        existing_cols = {
            col['name'] for col in inspector.get_columns(table_name)
        }
        expected_cols = {col.name for col in table.columns}
        missing_cols = expected_cols - existing_cols
        if missing_cols:
            missing_columns[table_name] = list(missing_cols)

    return {
        'expected_tables': expected_tables,
        'existing_tables': existing_tables,
        'missing_tables': missing_tables,
        'missing_columns': missing_columns
    }


def run_migrations() -> bool:
    """
    Run database schema migrations.

    This function handles automatic database schema migrations following a
    check → act → verify pattern:
    1. CHECK: Inspect current database schema and compare with expected schema
    2. ACT: Create missing tables, add missing columns, fix sequences
    3. VERIFY: Confirm all changes were applied successfully

    The migration process:
    - Step 1: Check current status (tables, columns, sequences)
    - Step 2: Create missing tables (PostgreSQL only)
    - Step 3: Add missing columns to existing tables (PostgreSQL only)
    - Step 4: Fix PostgreSQL sequences for primary key columns with
              autoincrement
    - Step 5: Verify all changes were applied successfully

    Note: This module currently supports PostgreSQL only.
    SQLite to PostgreSQL migration is handled by separate migration scripts.

    Returns:
        bool: True if migrations completed successfully, False otherwise
    """
    if database_module is None:
        logger.warning(
            "[DBMigration] Could not import database dependencies. "
            "Skipping migrations."
        )
        return False

    base = database_module.Base
    db_engine = database_module.engine

    if base is None or db_engine is None:
        logger.warning(
            "[DBMigration] Database dependencies not available. "
            "Skipping migrations."
        )
        return False

    try:
        # Get database dialect
        dialect = db_engine.dialect.name
        logger.info(
            "[DBMigration] Starting database migrations for dialect: %s",
            dialect
        )
        logger.debug(
            "[DBMigration] Running migrations for database dialect: %s",
            dialect
        )

        # Only support PostgreSQL for schema migrations
        # SQLite migration is handled by separate migration scripts
        if dialect != "postgresql":
            logger.warning(
                "[DBMigration] Schema migrations only support PostgreSQL. "
                "Current dialect: %s. Skipping migrations.",
                dialect
            )
            return True  # Return True to not block startup

        # =====================================================================
        # STEP 1: CHECK - Inspect current database status
        # =====================================================================
        logger.info(
            "[DBMigration] Step 1: Checking current database status..."
        )

        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        expected_tables = set(base.metadata.tables.keys())

        # Find missing tables
        missing_tables = expected_tables - existing_tables

        # Log status
        logger.info(
            "[DBMigration] Status check: %d expected tables, "
            "%d existing tables, %d missing",
            len(expected_tables),
            len(existing_tables),
            len(missing_tables)
        )

        if missing_tables:
            logger.info(
                "[DBMigration] Missing tables: %s",
                ', '.join(sorted(missing_tables))
            )

        # Track migration results
        migration_success = True
        tables_created = 0
        columns_added = 0
        sequences_fixed = 0
        indexes_created_total = 0

        # =====================================================================
        # STEP 2: ACT - Create missing tables
        # =====================================================================
        if missing_tables:
            tables_created, indexes_from_tables, success = (
                create_missing_tables(db_engine, base, missing_tables)
            )
            indexes_created_total += indexes_from_tables
            if not success:
                migration_success = False

            # Refresh inspector to get updated table list
            inspector = inspect(db_engine)
            existing_tables = set(inspector.get_table_names())

        # =====================================================================
        # STEP 3: ACT - Add missing columns and fix sequences
        # =====================================================================
        # Refresh inspector after table creation
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        tables_to_migrate = existing_tables & expected_tables

        if tables_to_migrate:
            logger.info(
                "[DBMigration] Step 3: Migrating existing tables "
                "(%d tables to check)...",
                len(tables_to_migrate)
            )

            with db_engine.connect() as conn:
                for table_name in tables_to_migrate:
                    try:
                        # Get existing columns in the table
                        existing_columns = {
                            col['name']
                            for col in inspector.get_columns(table_name)
                        }

                        # Get expected columns from SQLAlchemy model
                        table = base.metadata.tables[table_name]
                        expected_columns = {col.name for col in table.columns}

                        # Find missing columns
                        missing_columns = expected_columns - existing_columns

                        # Add missing columns
                        if missing_columns:
                            logger.info(
                                "[DBMigration] Table '%s' has %d missing "
                                "column(s): %s",
                                table_name,
                                len(missing_columns),
                                ', '.join(missing_columns)
                            )

                            for column_name in missing_columns:
                                column = table.columns[column_name]
                                success = add_column_postgresql(
                                    conn, table_name, column
                                )

                                if success:
                                    columns_added += 1
                                else:
                                    migration_success = False
                                    logger.error(
                                        "[DBMigration] Failed to add column "
                                        "'%s' to table '%s'",
                                        column_name,
                                        table_name
                                    )

                        # Fix PostgreSQL sequences for primary key columns
                        # with autoincrement
                        for column in table.columns:
                            if column.primary_key:
                                sequence_fixed = fix_postgresql_sequence(
                                    conn, table_name, column
                                )
                                if sequence_fixed:
                                    sequences_fixed += 1

                        # Create missing indexes for this table
                        indexes_created = create_table_indexes(
                            conn, table_name, table
                        )
                        indexes_created_total += indexes_created
                        if indexes_created > 0:
                            logger.info(
                                "[DBMigration] Created %d missing index(es) "
                                "for table '%s'",
                                indexes_created,
                                table_name
                            )

                    except Exception as e:
                        logger.error(
                            "[DBMigration] Error migrating table '%s': %s",
                            table_name,
                            e,
                            exc_info=True
                        )
                        migration_success = False
                        # Continue with next table to allow partial migration
                        continue
        else:
            if tables_created > 0:
                logger.info(
                    "[DBMigration] Created %d table(s), no columns to "
                    "migrate",
                    tables_created
                )
            else:
                logger.info(
                    "[DBMigration] No tables to migrate (all tables exist "
                    "and are up to date)"
                )

        # Ensure all tables have their indexes created
        # This handles cases where tables existed but indexes were missing
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        tables_to_check_indexes = existing_tables & expected_tables

        if tables_to_check_indexes:
            logger.info(
                "[DBMigration] Ensuring all tables have required indexes "
                "(%d tables to check)...",
                len(tables_to_check_indexes)
            )
            with db_engine.connect() as conn:
                for table_name in tables_to_check_indexes:
                    table = base.metadata.tables[table_name]
                    indexes_created = create_table_indexes(
                        conn, table_name, table
                    )
                    indexes_created_total += indexes_created

            if indexes_created_total > 0:
                logger.info(
                    "[DBMigration] Created %d missing index(es) across all "
                    "tables",
                    indexes_created_total
                )

        # =====================================================================
        # STEP 4: VERIFY - Confirm all changes were applied
        # =====================================================================
        logger.info(
            "[DBMigration] Step 4: Verifying migration results..."
        )

        _, verification_details = verify_migration_results(
            db_engine, base, expected_tables
        )

        # Log verification results
        if verification_details['tables_missing']:
            logger.error(
                "[DBMigration] VERIFICATION FAILED: %d table(s) still "
                "missing: %s",
                len(verification_details['tables_missing']),
                ', '.join(sorted(verification_details['tables_missing']))
            )
            migration_success = False
        else:
            logger.info(
                "[DBMigration] ✓ Verification passed: All %d expected "
                "tables exist",
                len(expected_tables)
            )

        if verification_details['columns_missing']:
            logger.error(
                "[DBMigration] VERIFICATION FAILED: Missing columns found:"
            )
            for table_name, missing_cols in (
                verification_details['columns_missing'].items()
            ):
                logger.error(
                    "[DBMigration]   Table '%s' missing columns: %s",
                    table_name,
                    ', '.join(sorted(missing_cols))
                )
            migration_success = False
        else:
            logger.info(
                "[DBMigration] ✓ All tables have all expected columns"
            )

        if verification_details['sequences_missing']:
            logger.error(
                "[DBMigration] VERIFICATION FAILED: Missing sequences found:"
            )
            for table_name, missing_seqs in (
                verification_details['sequences_missing'].items()
            ):
                logger.error(
                    "[DBMigration]   Table '%s' missing sequences: %s",
                    table_name,
                    ', '.join(sorted(missing_seqs))
                )
            migration_success = False
        else:
            logger.info("[DBMigration] ✓ All required sequences exist")

        if verification_details['indexes_missing']:
            logger.error(
                "[DBMigration] VERIFICATION FAILED: Missing indexes found:"
            )
            for table_name, missing_idxs in (
                verification_details['indexes_missing'].items()
            ):
                logger.error(
                    "[DBMigration]   Table '%s' missing indexes: %s",
                    table_name,
                    ', '.join(sorted(missing_idxs))
                )
            migration_success = False
        else:
            logger.info(
                "[DBMigration] ✓ All tables have all expected indexes"
            )

        # Summary
        logger.info("[DBMigration] Migration summary:")
        if tables_created > 0:
            logger.info(
                "[DBMigration]   - Created %d missing table(s)",
                tables_created
            )
        if columns_added > 0:
            logger.info(
                "[DBMigration]   - Added %d missing column(s) to existing "
                "tables",
                columns_added
            )
        if sequences_fixed > 0:
            logger.info(
                "[DBMigration]   - Fixed %d PostgreSQL sequence(s) for "
                "primary key columns",
                sequences_fixed
            )
        if indexes_created_total > 0:
            logger.info(
                "[DBMigration]   - Created %d missing index(es)",
                indexes_created_total
            )
        if (tables_created == 0 and columns_added == 0 and
                sequences_fixed == 0 and indexes_created_total == 0):
            logger.info(
                "[DBMigration]   - No changes needed "
                "(database is up to date)"
            )

        if migration_success:
            logger.info("[DBMigration] ✓ Migration completed successfully")
        else:
            logger.error("[DBMigration] ✗ Migration completed with errors")

        return migration_success

    except Exception as e:
        logger.error(
            "[DBMigration] Migration error: %s", e, exc_info=True
        )
        return False
