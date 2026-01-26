"""
Database migration utilities.

This module provides functions for running database schema migrations.
"""

import logging
from typing import Any
from sqlalchemy import inspect, text, Column
from sqlalchemy.dialects import mysql, postgresql

logger = logging.getLogger(__name__)


def _get_sqlite_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to SQLite column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        SQLite column type string (e.g., "INTEGER", "TEXT", "BOOLEAN")
    """
    column_type = str(column.type)

    # Handle ENUM types - SQLite doesn't support ENUM, store as TEXT
    if hasattr(column.type, 'enums') or 'ENUM' in str(type(column.type)).upper():
        return "TEXT"

    # Map SQLAlchemy types to SQLite types
    type_mapping = {
        "INTEGER": "INTEGER",
        "BIGINT": "INTEGER",
        "SMALLINT": "INTEGER",
        "TEXT": "TEXT",
        "VARCHAR": "TEXT",
        "STRING": "TEXT",
        "CHAR": "TEXT",
        "BOOLEAN": "INTEGER",  # SQLite uses INTEGER for boolean (0/1)
        "DATETIME": "TEXT",    # SQLite uses TEXT for datetime
        "DATE": "TEXT",
        "TIMESTAMP": "TEXT",
        "FLOAT": "REAL",
        "REAL": "REAL",
        "DOUBLE": "REAL",
        "NUMERIC": "NUMERIC",
        "DECIMAL": "NUMERIC",
        "BLOB": "BLOB",
    }

    # Check for common patterns
    column_type_upper = column_type.upper()
    for sqlalchemy_type, sqlite_type in type_mapping.items():
        if sqlalchemy_type in column_type_upper:
            return sqlite_type

    # Handle VARCHAR(length) -> TEXT
    if "VARCHAR" in column_type_upper or "CHAR" in column_type_upper:
        return "TEXT"

    # Default to TEXT for unknown types
    return "TEXT"


def _get_postgresql_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to PostgreSQL column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        PostgreSQL column type string
    """
    # For PostgreSQL, use the column type's compile method
    return str(column.type.compile(dialect=postgresql.dialect()))


def _get_mysql_column_type(column: Column) -> str:
    """
    Convert SQLAlchemy column type to MySQL column type string.

    Args:
        column: SQLAlchemy Column object

    Returns:
        MySQL column type string
    """
    return str(column.type.compile(dialect=mysql.dialect()))


def _get_column_default(column: Column, dialect: str) -> str:
    """
    Get column default value as SQL string.

    Args:
        column: SQLAlchemy Column object
        dialect: Database dialect ('sqlite', 'postgresql', 'mysql')

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
            if dialect == "sqlite":
                return f"DEFAULT {1 if default_value else 0}"
            return f"DEFAULT {str(default_value).upper()}"
        elif isinstance(default_value, str):
            return f"DEFAULT '{default_value}'"
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
            logger.debug("[DBMigration] Index '%s' already exists on table '%s'", index_name, table_name)
            return True

        # Create index
        create_index_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column.name})"
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


def _add_column_sqlite(conn: Any, table_name: str, column: Column) -> bool:
    """
    Add a column to a SQLite table.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object to add

    Returns:
        True if column was added successfully, False otherwise
    """
    try:
        column_type = _get_sqlite_column_type(column)
        default_clause = _get_column_default(column, "sqlite")

        # SQLite limitation: Cannot add NOT NULL column without default
        # to table with existing rows
        # If column is NOT NULL and no default, make it nullable or provide a default
        if not column.nullable and not default_clause:
            # Check if table has any rows
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar()
            if row_count and row_count > 0:
                # Table has data, we need a default for NOT NULL column
                # Use a sensible default based on type
                if "INTEGER" in column_type:
                    default_clause = "DEFAULT 0"
                    nullable = "NOT NULL"
                elif "REAL" in column_type or "NUMERIC" in column_type:
                    default_clause = "DEFAULT 0"
                    nullable = "NOT NULL"
                elif "TEXT" in column_type:
                    # For TEXT columns, try to get the actual default value first
                    # If column has a default, use it; otherwise use empty string
                    actual_default = _get_column_default(column, "sqlite")
                    if actual_default:
                        default_clause = actual_default
                    else:
                        default_clause = "DEFAULT ''"
                    nullable = "NOT NULL"
                else:
                    # For unknown types, make it nullable to avoid errors
                    logger.warning(
                        "[DBMigration] Column '%s' is NOT NULL without default and "
                        "table has data. Making nullable.",
                        column.name
                    )
                    nullable = "NULL"
            else:
                # Table is empty, can add NOT NULL without default
                nullable = "NOT NULL"
        else:
            nullable = "NULL" if column.nullable else "NOT NULL"

        # Build ALTER TABLE statement
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type} {nullable}"
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
        default_clause = _get_column_default(column, "postgresql")

        # Build ALTER TABLE statement
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}"
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


def _add_column_mysql(conn: Any, table_name: str, column: Column) -> bool:
    """
    Add a column to a MySQL table.

    Args:
        conn: Database connection
        table_name: Name of the table
        column: SQLAlchemy Column object to add

    Returns:
        True if column was added successfully, False otherwise
    """
    try:
        column_type = _get_mysql_column_type(column)
        nullable = "" if column.nullable else "NOT NULL"
        default_clause = _get_column_default(column, "mysql")

        # Build ALTER TABLE statement
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}"
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


def run_migrations() -> bool:
    """
    Run database schema migrations.

    This function handles automatic database schema migrations,
    such as adding missing columns to existing tables.

    The migration process:
    1. Inspects the current database schema
    2. Compares with expected schema from SQLAlchemy models
    3. Adds missing columns to existing tables
    4. Handles different database dialects (SQLite, PostgreSQL, MySQL)

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
            logger.debug("[DBMigration] No tables to migrate (all tables are new or don't exist)")
            logger.debug("[DBMigration] Existing tables: %s", ', '.join(sorted(existing_tables)))
            logger.debug("[DBMigration] Expected tables: %s", ', '.join(sorted(expected_tables)))
            return True

        # Track migration results
        migration_success = True
        columns_added = 0

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

                    if not missing_columns:
                        logger.debug(
                            "[DBMigration] Table '%s' is up to date (no missing columns)",
                            table_name
                        )
                        continue

                    logger.info(
                        "[DBMigration] Table '%s' has %d missing column(s): %s",
                        table_name,
                        len(missing_columns),
                        ', '.join(missing_columns)
                    )

                    # Add each missing column
                    for column_name in missing_columns:
                        column = table.columns[column_name]

                        # Choose the appropriate add column function based on dialect
                        if dialect == "sqlite":
                            success = _add_column_sqlite(conn, table_name, column)
                        elif dialect == "postgresql":
                            success = _add_column_postgresql(conn, table_name, column)
                        elif dialect == "mysql":
                            success = _add_column_mysql(conn, table_name, column)
                        else:
                            logger.warning(
                                "[DBMigration] Unsupported database dialect '%s' for column migration",
                                dialect
                            )
                            success = False

                        if success:
                            columns_added += 1
                        else:
                            migration_success = False

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
        else:
            logger.debug("[DBMigration] Migration check completed: no columns needed to be added")

        return migration_success

    except Exception as e:
        logger.error("[DBMigration] Migration error: %s", e, exc_info=True)
        return False
