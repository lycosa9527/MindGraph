"""
PostgreSQL schema migration helper functions.

This module provides helper functions for PostgreSQL database operations
used during schema migrations.
"""

import logging
from typing import Any
from sqlalchemy import inspect, text, Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import quoted_name

logger = logging.getLogger(__name__)


def get_postgresql_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to PostgreSQL column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        PostgreSQL column type string
    """
    return str(column.type.compile(dialect=postgresql.dialect()))


def get_column_default(column: Column) -> str:
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
            # For callable defaults (e.g., datetime.utcnow), we can't set them
            # in ALTER TABLE. They'll be handled by SQLAlchemy on insert.
            # For nullable columns, use NULL as default to avoid NOT NULL violations
            if column.nullable:
                logger.debug(
                    "[DBMigration] Column '%s' has callable default, "
                    "using NULL for nullable column",
                    column.name
                )
                return "DEFAULT NULL"
            else:
                # Non-nullable columns with callable defaults will need
                # application-level handling
                logger.warning(
                    "[DBMigration] Column '%s' has callable default but is "
                    "NOT NULL. Default will be handled by application, "
                    "not database.",
                    column.name
                )
                return ""

    return ""


def create_index_if_needed(conn: Any, table_name: str, column: Column) -> bool:
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
            "[DBMigration] Failed to create index for column '%s' in "
            "table '%s': %s",
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


def create_table_indexes(conn: Any, table_name: str, table: Any) -> int:
    """
    Create indexes for a table from table.indexes (explicit Index objects).

    Args:
        conn: Database connection
        table_name: Name of the table
        table: SQLAlchemy Table object

    Returns:
        Number of indexes created
    """
    indexes_created = 0
    try:
        inspector = inspect(conn)
        existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}

        # Create indexes from table.indexes (explicit Index objects)
        for index in table.indexes:
            if index.name in existing_indexes:
                logger.debug(
                    "[DBMigration] Index '%s' already exists on table '%s'",
                    index.name,
                    table_name
                )
                continue

            # Build index columns with proper quoting
            index_cols = [
                str(quoted_name(col.name, quote=True))
                for col in index.columns
            ]
            quoted_table = quoted_name(table_name, quote=True)
            quoted_index = quoted_name(index.name, quote=True)

            index_sql = (
                f'CREATE INDEX IF NOT EXISTS {quoted_index} '
                f'ON {quoted_table} ({", ".join(index_cols)})'
            )

            try:
                conn.execute(text(index_sql))
                conn.commit()
                indexes_created += 1
                logger.info(
                    "[DBMigration] Created index '%s' on table '%s'",
                    index.name,
                    table_name
                )
            except Exception as idx_error:
                error_msg = str(idx_error).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug(
                        "[DBMigration] Index '%s' already exists "
                        "(race condition)",
                        index.name
                    )
                else:
                    logger.warning(
                        "[DBMigration] Failed to create index '%s' on "
                        "table '%s': %s",
                        index.name,
                        table_name,
                        idx_error
                    )
                    try:
                        conn.rollback()
                    except Exception:
                        pass

    except Exception as e:
        logger.warning(
            "[DBMigration] Error creating indexes for table '%s': %s",
            table_name,
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass

    return indexes_created


def add_column_postgresql(conn: Any, table_name: str, column: Column) -> bool:
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
        column_type = get_postgresql_column_type(column)
        nullable = "" if column.nullable else "NOT NULL"
        default_clause = get_column_default(column)

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
        create_index_if_needed(conn, table_name, column)

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


def fix_postgresql_sequence(conn: Any, table_name: str, column: Column) -> bool:
    """
    Fix PostgreSQL sequence for a primary key column with autoincrement.

    Creates sequence if missing and configures column to use it.
    Uses proper SQL identifier quoting to prevent SQL injection.

    Args:
        conn: Database connection
        table_name: Name of the table (from SQLAlchemy metadata, trusted)
        column: SQLAlchemy Column object (should be primary key with
                autoincrement)

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
        if ('INTEGER' not in column_type_str and
                'BIGINT' not in column_type_str and
                'SMALLINT' not in column_type_str):
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
                "[DBMigration] Sequence %s does not exist for %s.%s. "
                "Creating it...",
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
            # Note: setval() requires literal sequence name, but sequence_name
            # comes from SQLAlchemy metadata (trusted source), so it's safe
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
            # Sequence name in nextval() must be literal, but comes from
            # trusted source
            conn.execute(text(
                f'ALTER TABLE {quoted_table} '
                f'ALTER COLUMN {quoted_column} SET DEFAULT '
                f'nextval(\'{sequence_name}\')'
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
                    "[DBMigration] Sequence value (%d) is <= max ID (%d). "
                    "Updating...",
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
                    "[DBMigration] Sequence %s is already set correctly "
                    "(value: %d)",
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
