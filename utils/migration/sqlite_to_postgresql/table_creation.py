"""
PostgreSQL Table Creation Utilities

Helper functions for creating PostgreSQL tables, ENUM types, and indexes
during SQLite to PostgreSQL migration.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional, Set, Any, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError, ProgrammingError

# Import Base directly from models to avoid circular import with config.database
from models.domain.auth import Base

from utils.migration.sqlite.migration_table_order import get_table_migration_order

logger = logging.getLogger(__name__)


def create_enum_types(pg_engine: Any) -> None:
    """
    Create PostgreSQL ENUM types before creating tables.

    Args:
        pg_engine: PostgreSQL SQLAlchemy engine
    """
    try:
        # Collect all ENUM types from Base.metadata
        enum_types = {}

        for table in Base.metadata.tables.values():
            for column in table.columns:
                # Check if column type is an Enum
                col_type = column.type
                if hasattr(col_type, 'name') and hasattr(col_type, 'enums'):
                    enum_name = col_type.name
                    enum_values = col_type.enums
                    if enum_name and enum_values:
                        # Convert enum values to strings (they might be Enum objects)
                        enum_values_str = [
                            str(val) if not isinstance(val, str) else val
                            for val in enum_values
                        ]
                        enum_types[enum_name] = enum_values_str

        if not enum_types:
            logger.debug("[Migration] No ENUM types found in schema")
            return

        logger.info(
            "[Migration] Creating %d ENUM type(s): %s",
            len(enum_types), ', '.join(enum_types.keys())
        )

        with pg_engine.connect() as conn:
            for enum_name, enum_values in enum_types.items():
                try:
                    # Check if ENUM type already exists
                    check_sql = text("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_type WHERE typname = :enum_name
                        )
                    """)
                    result = conn.execute(check_sql, {"enum_name": enum_name})
                    exists = result.scalar()

                    if exists:
                        logger.debug("[Migration] ENUM type %s already exists", enum_name)
                        continue

                    # Create ENUM type
                    # Escape single quotes in enum values
                    escaped_values = []
                    for val in enum_values:
                        escaped_val = val.replace("'", "''")
                        escaped_values.append(f"'{escaped_val}'")
                    create_sql = (
                        f'CREATE TYPE "{enum_name}" AS ENUM '
                        f'({", ".join(escaped_values)})'
                    )
                    conn.execute(text(create_sql))
                    conn.commit()
                    logger.info("[Migration] Created ENUM type: %s", enum_name)
                except Exception as enum_error:
                    error_msg = str(enum_error).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.debug(
                            "[Migration] ENUM type %s already exists (race condition)",
                            enum_name
                        )
                    else:
                        logger.warning(
                            "[Migration] Failed to create ENUM type %s: %s",
                            enum_name, enum_error
                        )
    except Exception as e:
        logger.warning("[Migration] Error creating ENUM types: %s", e)


def create_table_without_indexes(
    pg_engine: Any,
    table_name: str,
    table: Any,
    existing_tables: Optional[Set[str]] = None
) -> bool:
    """
    Create a PostgreSQL table without indexes to avoid index creation failures.

    Args:
        pg_engine: PostgreSQL SQLAlchemy engine
        table_name: Name of the table to create
        table: SQLAlchemy Table object
        existing_tables: Optional set of existing table names (for performance)

    Returns:
        True if table was created or already exists, False on error
    """
    try:
        # Check if table already exists
        if existing_tables is None:
            inspector = inspect(pg_engine)
            existing_tables = set(inspector.get_table_names())

        if table_name in existing_tables:
            return True

        # Check if parent tables exist for foreign keys
        for fk in table.foreign_keys:
            parent_table = fk.column.table.name
            if parent_table not in existing_tables and parent_table != table_name:
                logger.debug(
                    "[Migration] Cannot create table %s: parent table %s doesn't exist",
                    table_name, parent_table
                )
                return False

        # Build CREATE TABLE statement without indexes
        # Get column definitions
        column_defs = []
        constraints = []

        for column in table.columns:
            col_type = str(column.type.compile(dialect=postgresql.dialect()))
            col_def = f'"{column.name}" {col_type}'

            # Add NOT NULL if needed
            if not column.nullable and not column.primary_key:
                col_def += ' NOT NULL'

            # Add DEFAULT if needed
            if column.default is not None:
                if hasattr(column.default, 'arg'):
                    default_val = column.default.arg
                    if isinstance(default_val, (int, float)):
                        col_def += f' DEFAULT {default_val}'
                    elif isinstance(default_val, bool):
                        col_def += f' DEFAULT {str(default_val).upper()}'
                    elif isinstance(default_val, str):
                        # Escape single quotes in default string
                        escaped = default_val.replace("'", "''")
                        col_def += f" DEFAULT '{escaped}'"
                    elif callable(default_val):
                        # Skip callable defaults (e.g., datetime.utcnow)
                        pass

            column_defs.append(col_def)

            # Collect primary key columns
            if column.primary_key:
                constraints.append(f'PRIMARY KEY ("{column.name}")')

        # Add foreign key constraints
        for fk in table.foreign_keys:
            parent_table = fk.column.table.name
            parent_col = fk.column.name
            child_col = fk.parent.name

            # Get ON DELETE action
            on_delete = 'CASCADE'  # Default
            if fk.ondelete:
                on_delete = fk.ondelete.upper()

            constraints.append(
                f'FOREIGN KEY ("{child_col}") REFERENCES "{parent_table}" '
                f'("{parent_col}") ON DELETE {on_delete}'
            )

        # Add constraints from table.constraints
        # (UniqueConstraint, CheckConstraint from __table_args__)
        # SQLAlchemy stores constraints in table.constraints set
        # Skip PrimaryKeyConstraint (already handled above)
        # and ForeignKeyConstraint (handled above)
        for constraint in table.constraints:
            constraint_type = type(constraint).__name__

            # Skip constraints already handled
            if constraint_type in ('PrimaryKeyConstraint', 'ForeignKeyConstraint'):
                continue

            if constraint_type == 'UniqueConstraint':
                # Handle UniqueConstraint
                if hasattr(constraint, 'columns'):
                    unique_cols = [f'"{col.name}"' for col in constraint.columns]
                    if unique_cols:
                        constraint_name = getattr(constraint, 'name', None)
                        if constraint_name:
                            constraints.append(
                                f'CONSTRAINT "{constraint_name}" UNIQUE '
                                f'({", ".join(unique_cols)})'
                            )
                        else:
                            constraints.append(
                                f'UNIQUE ({", ".join(unique_cols)})'
                            )

            elif constraint_type == 'CheckConstraint':
                # Handle CheckConstraint
                if hasattr(constraint, 'sqltext'):
                    check_expr = str(constraint.sqltext)
                    constraint_name = getattr(constraint, 'name', None)
                    if constraint_name:
                        constraints.append(
                            f'CONSTRAINT "{constraint_name}" CHECK ({check_expr})'
                        )
                    else:
                        constraints.append(f'CHECK ({check_expr})')

        # Combine all parts
        all_parts = column_defs + constraints
        create_sql = (
            f'CREATE TABLE IF NOT EXISTS "{table_name}" '
            f'({", ".join(all_parts)})'
        )

        # Execute CREATE TABLE
        with pg_engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()

        # Verify table was created
        inspector = inspect(pg_engine)
        if table_name in inspector.get_table_names():
            logger.debug("[Migration] Created table %s without indexes", table_name)
            return True
        else:
            logger.error(
                "[Migration] Table %s creation reported success but table doesn't exist",
                table_name
            )
            return False

    except Exception as e:
        error_msg = str(e).lower()
        # Check if table already exists
        if "already exists" in error_msg or "duplicate" in error_msg:
            inspector = inspect(pg_engine)
            if table_name in inspector.get_table_names():
                return True
        logger.error("[Migration] Failed to create table %s: %s", table_name, e)
        return False


def create_table_indexes(pg_engine: Any, table_name: str, table: Any) -> None:
    """
    Create indexes for a table separately (after table creation).

    Args:
        pg_engine: PostgreSQL SQLAlchemy engine
        table_name: Name of the table
        table: SQLAlchemy Table object
    """
    try:
        inspector = inspect(pg_engine)
        existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}

        with pg_engine.connect() as conn:
            # Create indexes from table.indexes
            for index in table.indexes:
                if index.name in existing_indexes:
                    logger.debug(
                        "[Migration] Index %s already exists on table %s",
                        index.name, table_name
                    )
                    continue

                # Build index columns
                index_cols = [f'"{col.name}"' for col in index.columns]
                index_sql = (
                    f'CREATE INDEX IF NOT EXISTS "{index.name}" '
                    f'ON "{table_name}" ({", ".join(index_cols)})'
                )

                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                    logger.debug(
                        "[Migration] Created index %s on table %s",
                        index.name, table_name
                    )
                except Exception as idx_error:
                    error_msg = str(idx_error).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.debug(
                            "[Migration] Index %s already exists (race condition)",
                            index.name
                        )
                    else:
                        logger.warning(
                            "[Migration] Failed to create index %s on table %s: %s",
                            index.name, table_name, idx_error
                        )

            # Create indexes from column.index=True
            for column in table.columns:
                if getattr(column, 'index', False) and not isinstance(column.index, bool):
                    # Index object already handled above
                    continue
                elif getattr(column, 'index', False):
                    # Implicit index from index=True
                    index_name = f"ix_{table_name}_{column.name}"
                    if index_name in existing_indexes:
                        continue

                    index_sql = (
                        f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                        f'ON "{table_name}" ("{column.name}")'
                    )
                    try:
                        conn.execute(text(index_sql))
                        conn.commit()
                        logger.debug(
                            "[Migration] Created implicit index %s on table %s",
                            index_name, table_name
                        )
                    except Exception as idx_error:
                        error_msg = str(idx_error).lower()
                        if "already exists" in error_msg or "duplicate" in error_msg:
                            logger.debug(
                                "[Migration] Index %s already exists (race condition)",
                                index_name
                            )
                        else:
                            logger.warning(
                                "[Migration] Failed to create implicit index %s: %s",
                                index_name, idx_error
                            )
    except Exception as e:
        logger.warning(
            "[Migration] Error creating indexes for table %s: %s",
            table_name, e
        )


def ensure_missing_tables_created(
    pg_engine: Any,
    missing_tables: Set[str],
    expected_tables: Set[str]
) -> Tuple[bool, Optional[str]]:
    """
    Create missing PostgreSQL tables with retries for dependency resolution.

    Args:
        pg_engine: PostgreSQL SQLAlchemy engine
        missing_tables: Set of table names that need to be created
        expected_tables: Set of all expected table names (for verification)

    Returns:
        Tuple of (success, error_message). On success, error_message is None.
    """
    migration_order = get_table_migration_order()
    tables_to_create = [t for t in migration_order if t in missing_tables]
    tables_not_in_order = missing_tables - set(migration_order)
    if tables_not_in_order:
        logger.warning(
            "[Migration] Found %d table(s) not in migration order: %s",
            len(tables_not_in_order),
            ', '.join(sorted(tables_not_in_order))
        )
        tables_to_create.extend(sorted(tables_not_in_order))

    tables_failed = []
    inspector = inspect(pg_engine)
    existing_tables_set = set(inspector.get_table_names())

    for table_name in tables_to_create:
        try:
            table = Base.metadata.tables[table_name]
            if create_table_without_indexes(
                pg_engine, table_name, table, existing_tables_set
            ):
                create_table_indexes(pg_engine, table_name, table)
                inspector = inspect(pg_engine)
                if table_name in inspector.get_table_names():
                    logger.info("[Migration] ✓ Created table: %s", table_name)
                    existing_tables_set = set(inspector.get_table_names())
                else:
                    logger.error(
                        "[Migration] ✗ Table creation reported success but table %s doesn't exist",
                        table_name
                    )
                    tables_failed.append(table_name)
            else:
                tables_failed.append(table_name)
        except (OperationalError, ProgrammingError) as table_error:
            error_msg = str(table_error).lower()
            if ("already exists" in error_msg or
                    "duplicate" in error_msg or
                    ("relation" in error_msg and "exists" in error_msg)):
                inspector = inspect(pg_engine)
                if table_name in inspector.get_table_names():
                    existing_tables_set = set(inspector.get_table_names())
                else:
                    logger.warning(
                        "[Migration] Table %s creation error (likely index): %s. "
                        "Table doesn't exist, will retry.",
                        table_name, table_error
                    )
                    tables_failed.append(table_name)
            elif "undefinedtable" in error_msg or "does not exist" in error_msg:
                logger.debug(
                    "[Migration] Table %s depends on missing parent table: %s",
                    table_name, table_error
                )
                tables_failed.append(table_name)
            else:
                logger.error(
                    "[Migration] ✗ Failed to create table %s: %s",
                    table_name, table_error
                )
                tables_failed.append(table_name)
        except Exception as table_error:
            logger.error(
                "[Migration] ✗ Unexpected error creating table %s: %s",
                table_name, table_error
            )
            tables_failed.append(table_name)

    max_retries = 5
    for retry_pass in range(max_retries):
        if not tables_failed:
            break

        logger.info(
            "[Migration] Retry pass %d/%d: Retrying %d failed table(s): %s",
            retry_pass + 1, max_retries, len(tables_failed),
            ', '.join(tables_failed)
        )

        inspector = inspect(pg_engine)
        existing_tables = set(inspector.get_table_names())
        retry_failed = []

        for table_name in tables_failed:
            if table_name in existing_tables:
                logger.debug(
                    "[Migration] Table %s now exists (created by another process)",
                    table_name
                )
                continue

            try:
                table = Base.metadata.tables[table_name]
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
                        continue

                if parent_tables_missing:
                    logger.warning(
                        "[Migration] Table %s still waiting for parent tables: %s (existing: %s)",
                        table_name, ', '.join(parent_tables_missing),
                        ', '.join(sorted(existing_tables))[:200]
                    )
                    retry_failed.append(table_name)
                    continue

                if create_table_without_indexes(
                    pg_engine, table_name, table, existing_tables
                ):
                    create_table_indexes(pg_engine, table_name, table)
                    inspector = inspect(pg_engine)
                    if table_name in inspector.get_table_names():
                        logger.info(
                            "[Migration] ✓ Created table (retry %d): %s",
                            retry_pass + 1, table_name
                        )
                        inspector = inspect(pg_engine)
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
                    inspector = inspect(pg_engine)
                    if table_name in inspector.get_table_names():
                        existing_tables = set(inspector.get_table_names())
                    else:
                        logger.warning(
                            "[Migration] Table %s creation error (likely index): %s. Will retry.",
                            table_name, table_error
                        )
                        retry_failed.append(table_name)
                elif "undefinedtable" in error_msg or "does not exist" in error_msg:
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

    inspector = inspect(pg_engine)
    existing_tables = set(inspector.get_table_names())
    still_missing = expected_tables - existing_tables

    if still_missing:
        logger.error(
            "[Migration] CRITICAL: %d table(s) still missing after creation attempt: %s",
            len(still_missing),
            ', '.join(sorted(still_missing))
        )
        return False, f"Failed to create required tables: {', '.join(sorted(still_missing))}"

    logger.info(
        "[Migration] ✓ All %d required tables exist in PostgreSQL",
        len(expected_tables)
    )
    return True, None


__all__ = [
    "create_enum_types",
    "create_table_without_indexes",
    "create_table_indexes",
    "ensure_missing_tables_created",
]
