"""
PostgreSQL schema migration table operations.

This module handles complex table creation and cleanup operations
during PostgreSQL schema migrations.
"""

import logging
from typing import Any, Set, Tuple
from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.sql import quoted_name

from utils.migration.postgresql.schema_helpers import create_table_indexes

logger = logging.getLogger(__name__)


def create_missing_tables(
    db_engine: Any,
    base: Any,
    missing_tables: Set[str]
) -> Tuple[int, int, bool]:
    """
    Create missing tables and handle orphaned indexes/constraints.

    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata
        missing_tables: Set of table names to create

    Returns:
        tuple: (tables_created, indexes_created_total, success)
    """
    if not missing_tables:
        return 0, 0, True

    logger.info("[DBMigration] Step 2: Creating missing tables...")
    logger.info(
        "[DBMigration] Found %d missing table(s): %s",
        len(missing_tables),
        ', '.join(sorted(missing_tables))
    )

    tables_created = 0
    indexes_created_total = 0
    migration_success = True

    try:
        # Create missing tables using SQLAlchemy
        # Use checkfirst=True to avoid errors if table already exists
        tables_to_create = [
            base.metadata.tables[table_name]
            for table_name in missing_tables
        ]
        base.metadata.create_all(
            bind=db_engine,
            tables=tables_to_create,
            checkfirst=True
        )
        tables_created = len(missing_tables)
        logger.info(
            "[DBMigration] Created %d missing table(s)",
            tables_created
        )

        # Create indexes for newly created tables
        with db_engine.connect() as conn:
            for table_name in missing_tables:
                table = base.metadata.tables[table_name]
                indexes_created = create_table_indexes(conn, table_name, table)
                indexes_created_total += indexes_created
                if indexes_created > 0:
                    logger.info(
                        "[DBMigration] Created %d index(es) for table '%s'",
                        indexes_created,
                        table_name
                    )

    except ProgrammingError as e:
        # Handle partial table creation (e.g., indexes exist but table doesn't)
        error_msg = str(e).lower()
        if "duplicate" in error_msg and ("index" in error_msg or
                                          "relation" in error_msg):
            logger.warning(
                "[DBMigration] Partial table creation detected "
                "(orphaned indexes exist). Checking if tables are empty "
                "and recreating if needed..."
            )
            try:
                tables_created, indexes_created_total, migration_success = (
                    _handle_orphaned_objects(
                        db_engine, base, missing_tables
                    )
                )
            except Exception as retry_error:
                logger.error(
                    "[DBMigration] Error creating tables after handling "
                    "orphaned indexes: %s",
                    retry_error,
                    exc_info=True
                )
                migration_success = False
        else:
            # Non-index-related ProgrammingError
            logger.error(
                "[DBMigration] Error creating missing tables: %s",
                e,
                exc_info=True
            )
            migration_success = False

    except Exception as e:
        # General exception during table creation
        logger.error(
            "[DBMigration] Unexpected error creating missing tables: %s",
            e,
            exc_info=True
        )
        migration_success = False

    return tables_created, indexes_created_total, migration_success


def _handle_orphaned_objects(
    db_engine: Any,
    base: Any,
    missing_tables: Set[str]
) -> Tuple[int, int, bool]:
    """
    Handle orphaned constraints and indexes, then recreate tables.

    Args:
        db_engine: SQLAlchemy engine
        base: SQLAlchemy Base metadata
        missing_tables: Set of table names to create

    Returns:
        tuple: (tables_created, indexes_created_total, success)
    """
    with db_engine.connect() as conn:
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())
        tables_to_recreate = []

        for table_name in missing_tables:
            table = base.metadata.tables[table_name]

            # If table exists, drop it (CASCADE removes all indexes/constraints)
            # This is safe for dev environments
            if table_name in existing_tables:
                logger.info(
                    "[DBMigration] Table '%s' exists. "
                    "Dropping and recreating...",
                    table_name
                )
                tables_to_recreate.append(table_name)

            # If table doesn't exist, drop any orphaned constraints/indexes
            if table_name not in existing_tables:
                logger.info(
                    "[DBMigration] Table '%s' doesn't exist. Cleaning up "
                    "orphaned constraints and indexes...",
                    table_name
                )
                _cleanup_orphaned_objects(conn, table_name, table)

        # Drop empty/corrupted tables (CASCADE will drop indexes/constraints)
        if tables_to_recreate:
            with conn.begin():
                for table_name in tables_to_recreate:
                    try:
                        quoted_table = quoted_name(table_name, quote=True)
                        conn.execute(
                            text(f'DROP TABLE IF EXISTS {quoted_table} CASCADE')
                        )
                        logger.info(
                            "[DBMigration] Dropped table: %s",
                            table_name
                        )
                    except Exception as drop_error:
                        logger.error(
                            "[DBMigration] Could not drop table '%s': %s",
                            table_name,
                            drop_error
                        )
                        # Remove from missing_tables if drop failed
                        if table_name in missing_tables:
                            missing_tables.remove(table_name)

        # Now create all tables that are still missing
        tables_created = 0
        indexes_created_total = 0

        if missing_tables:
            tables_to_create = [
                base.metadata.tables[table_name]
                for table_name in missing_tables
            ]

            # Use a fresh connection for table creation
            # This ensures we're not in any transaction state
            with db_engine.connect() as create_conn:
                with create_conn.begin():
                    base.metadata.create_all(
                        bind=create_conn,
                        tables=tables_to_create,
                        checkfirst=True
                    )
            tables_created = len(missing_tables)
            logger.info(
                "[DBMigration] Created %d missing table(s) (after cleanup)",
                tables_created
            )

            # Create indexes for newly created tables
            with db_engine.connect() as index_conn:
                for table_name in missing_tables:
                    table = base.metadata.tables[table_name]
                    indexes_created = create_table_indexes(
                        index_conn, table_name, table
                    )
                    indexes_created_total += indexes_created
                    if indexes_created > 0:
                        logger.info(
                            "[DBMigration] Created %d index(es) for "
                            "table '%s'",
                            indexes_created,
                            table_name
                        )
        else:
            logger.info(
                "[DBMigration] All tables already exist "
                "(some were empty and recreated)"
            )

        return tables_created, indexes_created_total, True


def _cleanup_orphaned_objects(conn: Any, table_name: str, table: Any) -> None:
    """
    Clean up orphaned constraints and indexes for a table.

    Args:
        conn: Database connection
        table_name: Name of the table
        table: SQLAlchemy Table object
    """
    try:
        # Drop constraints and indexes in a transaction
        with conn.begin():
            # STEP 1: Drop constraints first (CASCADE automatically drops
            # associated indexes). This handles unique constraints created
            # by unique=True on columns
            try:
                constraint_query = text("""
                    SELECT c.conname, c.contype
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_namespace n ON t.relnamespace = n.oid
                    WHERE n.nspname = 'public'
                    AND t.relname = :table_name
                    AND c.contype IN ('u', 'p')
                """)
                result = conn.execute(
                    constraint_query, {"table_name": table_name}
                )
                constraints = result.fetchall()

                if constraints:
                    logger.info(
                        "[DBMigration] Found %d constraint(s) for "
                        "table '%s': %s",
                        len(constraints),
                        table_name,
                        ', '.join([c[0] for c in constraints])
                    )

                for constraint_name, constraint_type in constraints:
                    try:
                        quoted_table = quoted_name(table_name, quote=True)
                        quoted_constraint = quoted_name(
                            constraint_name, quote=True
                        )
                        conn.execute(text(
                            f'ALTER TABLE {quoted_table} '
                            f'DROP CONSTRAINT IF EXISTS {quoted_constraint} '
                            f'CASCADE'
                        ))
                        logger.info(
                            "[DBMigration] Dropped constraint: %s (type: %s)",
                            constraint_name,
                            ('UNIQUE' if constraint_type == 'u'
                             else 'PRIMARY KEY')
                        )
                    except Exception as drop_error:
                        error_msg = str(drop_error).lower()
                        if "does not exist" not in error_msg:
                            logger.warning(
                                "[DBMigration] Could not drop constraint "
                                "%s: %s",
                                constraint_name,
                                drop_error
                            )
            except Exception as constraint_error:
                # Query might fail if table never existed, that's OK
                logger.debug(
                    "[DBMigration] Could not query constraints for %s: %s",
                    table_name,
                    constraint_error
                )

            # STEP 2: Drop indexes by name from the model
            for index in table.indexes:
                try:
                    quoted_index = quoted_name(index.name, quote=True)
                    conn.execute(
                        text(f'DROP INDEX IF EXISTS {quoted_index} CASCADE')
                    )
                    logger.info(
                        "[DBMigration] Dropped orphaned index: %s",
                        index.name
                    )
                except Exception as drop_error:
                    error_msg = str(drop_error).lower()
                    if "does not exist" not in error_msg:
                        logger.debug(
                            "[DBMigration] Could not drop index %s: %s",
                            index.name,
                            drop_error
                        )

            # STEP 3: Query pg_class for any remaining orphaned indexes
            # This catches indexes that might not be in table.indexes
            try:
                model_index_names_list = [idx.name for idx in table.indexes]
                if model_index_names_list:
                    index_names_placeholders = ', '.join(
                        [f"'{name}'" for name in model_index_names_list]
                    )
                    pattern = f"ix_{table_name}_%"

                    orphaned_query = text(f"""
                        SELECT c.relname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                        AND c.relkind = 'i'
                        AND (
                            c.relname LIKE :pattern
                            OR c.relname IN ({index_names_placeholders})
                        )
                    """)
                    result = conn.execute(
                        orphaned_query,
                        {"pattern": pattern}
                    )
                    found_indexes = [row[0] for row in result.fetchall()]

                    if found_indexes:
                        logger.info(
                            "[DBMigration] Found %d additional orphaned "
                            "index(es): %s",
                            len(found_indexes),
                            ', '.join(found_indexes)
                        )

                    # Drop any found indexes
                    for index_name in found_indexes:
                        try:
                            quoted_index = quoted_name(index_name, quote=True)
                            conn.execute(
                                text(f'DROP INDEX IF EXISTS {quoted_index} '
                                     f'CASCADE')
                            )
                            logger.info(
                                "[DBMigration] Dropped orphaned index from "
                                "pg_class: %s",
                                index_name
                            )
                        except Exception as drop_error:
                            error_msg = str(drop_error).lower()
                            if "does not exist" not in error_msg:
                                logger.debug(
                                    "[DBMigration] Could not drop index %s: "
                                    "%s",
                                    index_name,
                                    drop_error
                                )
            except Exception as query_error:
                # Query might fail, that's OK
                logger.debug(
                    "[DBMigration] Could not query pg_class for orphaned "
                    "indexes: %s",
                    query_error
                )

        # Transaction committed, constraints and indexes should be dropped
        # Verify by querying again (outside transaction)
        try:
            # Verify constraints are gone
            verify_constraint_query = text("""
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                WHERE n.nspname = 'public'
                AND t.relname = :table_name
                AND c.contype IN ('u', 'p')
            """)
            result = conn.execute(
                verify_constraint_query, {"table_name": table_name}
            )
            remaining_constraints = [row[0] for row in result.fetchall()]
            if remaining_constraints:
                logger.warning(
                    "[DBMigration] Warning: Some constraints still exist "
                    "after drop: %s",
                    ', '.join(remaining_constraints)
                )

            # Verify indexes are gone
            verify_index_query = text("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname LIKE :pattern
            """)
            pattern = f"{table_name}%"
            result = conn.execute(verify_index_query, {"pattern": pattern})
            remaining_indexes = [row[0] for row in result.fetchall()]
            if remaining_indexes:
                logger.warning(
                    "[DBMigration] Warning: Some indexes still exist after "
                    "drop: %s",
                    ', '.join(remaining_indexes)
                )
        except Exception:
            pass  # Verification is optional

    except Exception as cleanup_error:
        logger.error(
            "[DBMigration] Error cleaning up orphaned indexes for %s: %s",
            table_name,
            cleanup_error,
            exc_info=True
        )
