"""
Database migration utilities.

This module provides functions for running database schema migrations.
Currently supports PostgreSQL only (SQLite migration is handled separately).
"""

import logging
from typing import Any
from sqlalchemy import inspect, text, Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import quoted_name

logger = logging.getLogger(__name__)


def _get_postgresql_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to PostgreSQL column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        PostgreSQL column type string
    """
    return str(column.type.compile(dialect=postgresql.dialect()))


def _get_column_default(column: Column) -> str:
    """
    Get column default value as SQL string for PostgreSQL.

    Args:
        column: SQLAlchemy Column object

    Returns:
        Default value SQL string (e.g., "DEFAULT 0" or "DEFAULT NULL")
    """
    if column.default is None:
        if column.nullable:
            return "DEFAULT NULL"
        return ""

    # Handle server defaults
    if hasattr(column.default, 'arg'):
        default_value = column.default.arg
        if isinstance(default_value, (int, float)):
            return f"DEFAULT {default_value}"
        elif isinstance(default_value, bool):
            return f"DEFAULT {str(default_value).upper()}"
        elif isinstance(default_value, str):
            # Escape single quotes in string defaults
            escaped_value = default_value.replace("'", "''")
            return f"DEFAULT '{escaped_value}'"
        elif callable(default_value):
            # For callable defaults (e.g., datetime.utcnow), we can't set them in ALTER TABLE
            # They'll be handled by SQLAlchemy on insert
            return ""

    return ""


def _create_index_if_needed(conn: Any, table_name: str, column: Column) -> bool:
    """
    Create an index for a column if it has index=True.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object

    Returns:
        True if index was created or not needed, False on error
    """
    try:
        # Check if column has index=True
        # In SQLAlchemy, index=True creates an implicit index
        # column.index can be True (boolean), an Index object, or False/None
        column_index = getattr(column, 'index', False)
        if not column_index:
            return True  # No index needed

        # Generate index name (SQLAlchemy convention: ix_<table>_<column>)
        index_name = f"ix_{table_name}_{column.name}"

        # Check if index already exists
        inspector = inspect(conn)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        if index_name in existing_indexes:
            logger.debug(
                "[DBMigration] Index '%s' already exists on table '%s'",
                index_name,
                table_name
            )
            return True

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column.name, quote=True)

        # Create index
        create_index_sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {quoted_table}({quoted_column})"
        )
        conn.execute(text(create_index_sql))
        conn.commit()
        logger.info(
            "[DBMigration] Created index '%s' on column '%s' in table '%s'",
            index_name,
            column.name,
            table_name
        )
        return True
    except Exception as e:
        logger.warning(
            "[DBMigration] Failed to create index for column '%s' in table '%s': %s",
            column.name,
            table_name,
            e
        )
        # Don't fail the migration if index creation fails
        try:
            conn.rollback()
        except Exception:
            pass
        return True  # Return True to not block migration


def _add_column_postgresql(conn: Any, table_name: str, column: Column) -> bool:
    """
    Add a column to a PostgreSQL table.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object to add

    Returns:
        True if column was added successfully, False otherwise
    """
    try:
        column_type = _get_postgresql_column_type(column)
        nullable = "" if column.nullable else "NOT NULL"
        default_clause = _get_column_default(column)

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column.name, quote=True)

        # Build ALTER TABLE statement
        sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type}"
        if nullable:
            sql += f" {nullable}"
        if default_clause:
            sql += f" {default_clause}"

        conn.execute(text(sql))
        conn.commit()
        logger.info(
            "[DBMigration] Added column '%s' to table '%s'",
            column.name,
            table_name
        )

        # Create index if needed
        _create_index_if_needed(conn, table_name, column)

        return True
    except Exception as e:
        logger.error(
            "[DBMigration] Failed to add column '%s' to table '%s': %s",
            column.name,
            table_name,
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass  # Ignore rollback errors
        return False


def _fix_postgresql_sequence(conn: Any, table_name: str, column: Column) -> bool:
    """
    Fix PostgreSQL sequence for a primary key column with autoincrement.

    Creates sequence if missing and configures column to use it.
    Uses proper SQL identifier quoting to prevent SQL injection.

    Args:
        conn: Database connection
        table_name: Name of the table (from SQLAlchemy metadata, trusted)
        column: SQLAlchemy Column object (should be primary key with autoincrement)

    Returns:
        True if sequence was fixed successfully, False otherwise
    """
    try:
        # Only fix sequences for primary key columns with autoincrement
        if not column.primary_key:
            return True  # Not a primary key, skip

        # Check if column has autoincrement
        autoincrement = getattr(column, 'autoincrement', False)
        if not autoincrement:
            return True  # No autoincrement, skip

        # Only handle INTEGER types (BIGINT, SMALLINT also work)
        column_type_str = str(column.type).upper()
        if 'INTEGER' not in column_type_str and 'BIGINT' not in column_type_str and 'SMALLINT' not in column_type_str:
            return True  # Not an integer type, skip

        column_name = column.name
        sequence_name = f"{table_name}_{column_name}_seq"

        # Use proper identifier quoting for table and column names
        quoted_table = quoted_name(table_name, quote=True)
        quoted_column = quoted_name(column_name, quote=True)

        # Check if sequence exists (use parameterized query for sequence name)
        seq_check = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM pg_sequences "
            "WHERE schemaname = 'public' AND sequencename = :seq_name)"
        ), {"seq_name": sequence_name})
        sequence_exists = seq_check.scalar()

        # Get current max ID (use quoted identifiers)
        max_id_result = conn.execute(
            text(f'SELECT MAX({quoted_column}) FROM {quoted_table}')
        )
        max_id = max_id_result.scalar() or 0

        if not sequence_exists:
            logger.info(
                "[DBMigration] Sequence %s does not exist for %s.%s. Creating it...",
                sequence_name,
                table_name,
                column_name
            )

            # Check column type and default (use parameterized query)
            type_check = conn.execute(text(
                """
                SELECT data_type, column_default
                FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
                """
            ), {"table_name": table_name, "column_name": column_name})
            col_info = type_check.fetchone()

            if not col_info:
                logger.warning(
                    "[DBMigration] Could not find column %s.%s",
                    table_name,
                    column_name
                )
                return False

            # Create sequence (sequence name is safe - comes from trusted source)
            # But we still quote it properly
            quoted_sequence = quoted_name(sequence_name, quote=True)
            conn.execute(text(f"CREATE SEQUENCE {quoted_sequence}"))
            logger.info("[DBMigration] Created sequence %s", sequence_name)

            # Set sequence value
            # Note: setval() requires literal sequence name, but sequence_name comes from
            # SQLAlchemy metadata (trusted source), so it's safe to use here
            if max_id > 0:
                conn.execute(
                    text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)")
                )
                logger.info(
                    "[DBMigration] Set sequence %s to %d",
                    sequence_name,
                    max_id + 1
                )
            else:
                conn.execute(text(f"SELECT setval('{sequence_name}', 1, false)"))
                logger.info("[DBMigration] Set sequence %s to 1", sequence_name)

            # Set column default to use sequence (use quoted identifiers)
            # Sequence name in nextval() must be literal, but comes from trusted source
            conn.execute(text(
                f'ALTER TABLE {quoted_table} '
                f'ALTER COLUMN {quoted_column} SET DEFAULT nextval(\'{sequence_name}\')'
            ))
            logger.info(
                "[DBMigration] Set column default to use sequence for %s.%s",
                table_name,
                column_name
            )

            # Set sequence owner (use quoted identifiers)
            conn.execute(text(
                f"ALTER SEQUENCE {quoted_sequence} "
                f"OWNED BY {quoted_table}.{quoted_column}"
            ))
            logger.info("[DBMigration] Set sequence owner")

            conn.commit()
            logger.info(
                "[DBMigration] ✓ Successfully fixed sequence for %s.%s",
                table_name,
                column_name
            )
            return True
        else:
            # Sequence exists, verify it's set correctly
            quoted_sequence = quoted_name(sequence_name, quote=True)
            seq_value_result = conn.execute(
                text(f"SELECT last_value FROM {quoted_sequence}")
            )
            last_value = seq_value_result.scalar()

            if last_value <= max_id:
                logger.info(
                    "[DBMigration] Sequence value (%d) is <= max ID (%d). Updating...",
                    last_value,
                    max_id
                )
                # Sequence name comes from SQLAlchemy metadata (trusted source)
                conn.execute(
                    text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)")
                )
                conn.commit()
                logger.info(
                    "[DBMigration] ✓ Updated sequence %s to %d",
                    sequence_name,
                    max_id + 1
                )
                return True
            else:
                logger.debug(
                    "[DBMigration] Sequence %s is already set correctly (value: %d)",
                    sequence_name,
                    last_value
                )
                return True

    except Exception as e:
        logger.warning(
            "[DBMigration] Failed to fix sequence for %s.%s: %s",
            table_name,
            column.name,
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass  # Ignore rollback errors
        return False  # Don't fail migration if sequence fix fails


def run_migrations() -> bool:
    """
    Run database schema migrations.

    This function handles automatic database schema migrations,
    such as adding missing columns to existing tables and fixing PostgreSQL sequences.

    The migration process:
    1. Inspects the current database schema
    2. Compares with expected schema from SQLAlchemy models
    3. Adds missing columns to existing tables (PostgreSQL only)
    4. Fixes PostgreSQL sequences for primary key columns with autoincrement

    Note: This module currently supports PostgreSQL only.
    SQLite to PostgreSQL migration is handled by separate migration scripts.

    Returns:
        bool: True if migrations completed successfully, False otherwise
    """
    # Lazy import to avoid circular dependency with config.database
    # Import here ensures config.database is fully initialized when called
    base = None
    db_engine = None
    try:
        import config.database as database_module
        base = database_module.Base
        db_engine = database_module.engine
    except ImportError as import_error:
        logger.warning(
            "[DBMigration] Could not import database dependencies: %s. Skipping migrations.",
            import_error
        )
        return False

    if base is None or db_engine is None:
        logger.warning(
            "[DBMigration] Database dependencies not available. Skipping migrations."
        )
        return False

    try:
        # Get database dialect
        dialect = db_engine.dialect.name
        logger.debug("[DBMigration] Running migrations for database dialect: %s", dialect)

        # Only support PostgreSQL for schema migrations
        # SQLite migration is handled by separate migration scripts
        if dialect != "postgresql":
            logger.warning(
                "[DBMigration] Schema migrations only support PostgreSQL. "
                "Current dialect: %s. Skipping migrations.",
                dialect
            )
            return True  # Return True to not block startup

        # Create inspector to examine current database schema
        inspector = inspect(db_engine)
        existing_tables = set(inspector.get_table_names())

        # Get expected tables from base metadata
        expected_tables = set(base.metadata.tables.keys())

        # Log registered tables for debugging
        logger.debug(
            "[DBMigration] Registered tables in base.metadata: %s",
            ', '.join(sorted(expected_tables))
        )

        # Only migrate existing tables (table creation is handled by init_db)
        tables_to_migrate = existing_tables & expected_tables

        if not tables_to_migrate:
            logger.debug(
                "[DBMigration] No tables to migrate (all tables are new or don't exist)"
            )
            logger.debug(
                "[DBMigration] Existing tables: %s",
                ', '.join(sorted(existing_tables))
            )
            logger.debug(
                "[DBMigration] Expected tables: %s",
                ', '.join(sorted(expected_tables))
            )
            return True

        # Track migration results
        migration_success = True
        columns_added = 0
        sequences_fixed = 0

        with db_engine.connect() as conn:
            for table_name in tables_to_migrate:
                try:
                    # Get existing columns in the table
                    existing_columns = {
                        col['name'] for col in inspector.get_columns(table_name)
                    }

                    # Get expected columns from SQLAlchemy model
                    table = base.metadata.tables[table_name]
                    expected_columns = {col.name for col in table.columns}

                    # Find missing columns
                    missing_columns = expected_columns - existing_columns

                    # Add missing columns
                    if missing_columns:
                        logger.info(
                            "[DBMigration] Table '%s' has %d missing column(s): %s",
                            table_name,
                            len(missing_columns),
                            ', '.join(missing_columns)
                        )

                        for column_name in missing_columns:
                            column = table.columns[column_name]
                            success = _add_column_postgresql(conn, table_name, column)

                            if success:
                                columns_added += 1
                            else:
                                migration_success = False

                    # Fix PostgreSQL sequences for primary key columns with autoincrement
                    for column in table.columns:
                        if column.primary_key:
                            if _fix_postgresql_sequence(conn, table_name, column):
                                sequences_fixed += 1

                except Exception as e:
                    logger.error(
                        "[DBMigration] Error migrating table '%s': %s",
                        table_name,
                        e,
                        exc_info=True
                    )
                    migration_success = False

        if columns_added > 0:
            logger.info(
                "[DBMigration] Migration completed: added %d column(s) to existing tables",
                columns_added
            )
        if sequences_fixed > 0:
            logger.info(
                "[DBMigration] Fixed %d PostgreSQL sequence(s) for primary key columns",
                sequences_fixed
            )
        if columns_added == 0 and sequences_fixed == 0:
            logger.debug("[DBMigration] Migration check completed: no changes needed")

        return migration_success

    except Exception as e:
        logger.error("[DBMigration] Migration error: %s", e, exc_info=True)
        return False
