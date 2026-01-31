"""SQLite Type Migration Handler.

Handles column type mismatches for SQLite databases.
SQLite doesn't support ALTER COLUMN, so table recreation is required.

Safety features:
- Validates all identifiers to prevent SQL injection
- Disables foreign keys during migration
- Copies data with type casting
- Recreates indexes after migration

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Any, Optional, Dict
import logging
import re
import sqlite3
from sqlalchemy import inspect
from models.domain.auth import Base


logger = logging.getLogger(__name__)

# Valid identifier pattern for table/column names (prevent SQL injection)
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def validate_identifier(name: str) -> bool:
    """Validate table/column name to prevent SQL injection"""
    if not name or not VALID_IDENTIFIER_PATTERN.match(name):
        logger.error("[DBTypeMigration] Invalid identifier: '%s' - rejected for safety", name)
        return False
    return True


def normalize_sqlite_type(type_str: str) -> str:
    """
    Normalize SQLite type for comparison.

    SQLite has type affinity rules, so we normalize types to their affinity:
    - INTEGER: INT, INTEGER, TINYINT, SMALLINT, MEDIUMINT, BIGINT, etc.
    - TEXT: TEXT, VARCHAR, CHAR, CLOB, etc.
    - REAL: REAL, DOUBLE, FLOAT, etc.
    - NUMERIC: BOOLEAN, DATE, DATETIME, etc.

    Returns:
        Normalized type category for comparison
    """
    if not type_str:
        return 'TEXT'

    type_upper = type_str.upper().strip()

    # Extract base type (remove length specifiers)
    # VARCHAR(36) -> VARCHAR, INTEGER -> INTEGER
    base_type = type_upper.split('(')[0].strip()

    # Map to SQLite type affinities
    integer_types = {
        'INT', 'INTEGER', 'TINYINT', 'SMALLINT', 'MEDIUMINT',
        'BIGINT', 'UNSIGNED BIG INT', 'INT2', 'INT8'
    }
    text_types = {
        'TEXT', 'VARCHAR', 'CHAR', 'CHARACTER', 'VARYING CHARACTER',
        'NCHAR', 'NATIVE CHARACTER', 'NVARCHAR', 'CLOB', 'STRING'
    }
    real_types = {'REAL', 'DOUBLE', 'DOUBLE PRECISION', 'FLOAT'}
    blob_types = {'BLOB'}

    if base_type in integer_types:
        return 'INTEGER'
    elif base_type in text_types:
        return 'TEXT'
    elif base_type in real_types:
        return 'REAL'
    elif base_type in blob_types:
        return 'BLOB'
    elif base_type == 'BOOLEAN':
        # SQLite stores BOOLEAN as INTEGER, but we track it separately
        return 'BOOLEAN'
    elif base_type in ('DATE', 'DATETIME', 'TIMESTAMP'):
        # SQLite stores these as TEXT or INTEGER
        return 'DATETIME'
    else:
        # Default to NUMERIC affinity
        return 'NUMERIC'


def types_are_compatible(expected_type: str, actual_type: str) -> bool:
    """
    Check if expected and actual column types are compatible.

    Args:
        expected_type: Type from SQLAlchemy model
        actual_type: Type from database

    Returns:
        True if types are compatible, False if migration needed
    """
    expected_norm = normalize_sqlite_type(expected_type)
    actual_norm = normalize_sqlite_type(actual_type)

    # Direct match
    if expected_norm == actual_norm:
        return True

    # Special cases: BOOLEAN and DATETIME are stored as different types in SQLite
    # BOOLEAN can be stored as INTEGER (0/1)
    if expected_norm == 'BOOLEAN' and actual_norm == 'INTEGER':
        return True
    # DATETIME can be stored as TEXT or INTEGER (unix timestamp)
    if expected_norm == 'DATETIME' and actual_norm in ('TEXT', 'INTEGER'):
        return True

    return False


def get_sqlite_type(column_def: Any) -> str:
    """Convert SQLAlchemy column type to SQLite type string"""
    type_str = str(column_def.type)

    # SQLite type mapping
    if 'INTEGER' in type_str.upper():
        return 'INTEGER'
    elif 'VARCHAR' in type_str.upper() or 'STRING' in type_str.upper():
        # Extract length if available
        if hasattr(column_def.type, 'length') and column_def.type.length:
            return f"VARCHAR({column_def.type.length})"
        return 'TEXT'
    elif 'TEXT' in type_str.upper():
        return 'TEXT'
    elif 'FLOAT' in type_str.upper() or 'REAL' in type_str.upper():
        return 'REAL'
    elif 'BOOLEAN' in type_str.upper():
        return 'BOOLEAN'
    elif 'DATETIME' in type_str.upper() or 'TIMESTAMP' in type_str.upper():
        return 'DATETIME'
    else:
        return type_str


def get_sql_default_value(default: Any) -> Optional[str]:
    """Convert SQLAlchemy default to SQL value string"""
    if default is None:
        return None

    # Handle callable defaults (e.g., datetime.utcnow)
    if callable(default):
        return None

    # Handle ColumnDefault
    if hasattr(default, 'arg'):
        default = default.arg
        if callable(default):
            return None

    # Convert Python values to SQL
    if isinstance(default, bool):
        return '1' if default else '0'
    elif isinstance(default, (int, float)):
        return str(default)
    elif isinstance(default, str):
        return f"'{default}'"
    else:
        return str(default)


def detect_type_mismatches(
    engine: Any,
    table_name: str,
    table_class: Any
) -> List[Dict]:
    """
    Detect columns with type mismatches (column exists but wrong type).

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table
        table_class: SQLAlchemy model class

    Returns:
        List of type mismatch details
    """
    mismatches = []

    try:
        fresh_inspector = inspect(engine)

        if not fresh_inspector.has_table(table_name):
            return []

        # Get existing columns with their types
        existing_columns = {
            col['name'].lower(): col
            for col in fresh_inspector.get_columns(table_name)
        }

        # Get expected columns from model
        if table_class is None:
            table_metadata = Base.metadata.tables.get(table_name)
            if table_metadata is None:
                return []
            expected_columns = {col.name: col for col in table_metadata.columns}
        else:
            try:
                expected_columns = {
                    col.name: col
                    for col in table_class.__table__.columns
                }
            except AttributeError:
                table_metadata = Base.metadata.tables.get(table_name)
                if table_metadata is None:
                    return []
                expected_columns = {col.name: col for col in table_metadata.columns}

        # Check each column for type mismatch
        for col_name, col_def in expected_columns.items():
            col_name_lower = col_name.lower()
            if col_name_lower in existing_columns:
                existing_col = existing_columns[col_name_lower]
                expected_type = get_sqlite_type(col_def)
                actual_type = str(existing_col.get('type', ''))

                if not types_are_compatible(expected_type, actual_type):
                    mismatches.append({
                        'table': table_name,
                        'column': col_name,
                        'expected_type': expected_type,
                        'actual_type': actual_type,
                        'is_primary_key': col_def.primary_key
                    })

        return mismatches

    except Exception as e:
        logger.error("[DBTypeMigration] Detection failed for %s: %s", table_name, e)
        return []


def recreate_table_with_correct_schema(
    db_path: str,
    table_name: str,
    table_class: Any,
    mismatches: List[Dict]
) -> bool:
    """
    Recreate a table with the correct schema (SQLite table recreation pattern).

    SQLite doesn't support ALTER COLUMN, so we must:
    1. Create a new table with correct schema (_new suffix)
    2. Copy data from old table (with type casting where needed)
    3. Drop old table
    4. Rename new table to original name
    5. Recreate indexes

    Args:
        db_path: Path to SQLite database file
        table_name: Name of the table to recreate
        table_class: SQLAlchemy model class
        mismatches: List of type mismatches detected

    Returns:
        True if recreation successful, False otherwise
    """
    if not validate_identifier(table_name):
        logger.error("[DBTypeMigration] Invalid table name: '%s'", table_name)
        return False

    temp_table_name = f"{table_name}_migration_new"

    try:
        # Get table metadata
        if table_class is not None and hasattr(table_class, '__table__'):
            table_metadata = table_class.__table__
        else:
            table_metadata = Base.metadata.tables.get(table_name)

        if table_metadata is None:
            logger.error("[DBTypeMigration] No table metadata for '%s'", table_name)
            return False

        # Build column definitions for new table
        column_defs = []
        column_names = []
        for col in table_metadata.columns:
            col_name = col.name
            if not validate_identifier(col_name):
                logger.error("[DBTypeMigration] Invalid column name: '%s'", col_name)
                return False

            column_names.append(col_name)
            col_type = get_sqlite_type(col)

            # Build column definition
            parts = [f'"{col_name}"', col_type]

            if col.primary_key:
                parts.append('PRIMARY KEY')
            if not col.nullable and not col.primary_key:
                parts.append('NOT NULL')
            if col.default is not None:
                default_val = get_sql_default_value(col.default)
                if default_val:
                    parts.append(f'DEFAULT {default_val}')

            column_defs.append(' '.join(parts))

        # Foreign key constraints (if any)
        fk_constraints = []
        for fk in table_metadata.foreign_keys:
            parent_table = fk.column.table.name
            parent_col = fk.column.name
            child_col = fk.parent.name
            if all(validate_identifier(n) for n in [parent_table, parent_col, child_col]):
                fk_constraints.append(
                    f'FOREIGN KEY ("{child_col}") REFERENCES "{parent_table}" ("{parent_col}")'
                )

        # Combine all constraints
        all_defs = column_defs + fk_constraints

        conn = sqlite3.connect(db_path, timeout=60.0)
        cursor = conn.cursor()

        try:
            # Disable foreign key checks during migration
            cursor.execute("PRAGMA foreign_keys=OFF")

            # Step 1: Create new table with correct schema
            create_sql = f'CREATE TABLE "{temp_table_name}" ({", ".join(all_defs)})'
            logger.debug("[DBTypeMigration] Creating temp table: %s", temp_table_name)
            cursor.execute(create_sql)

            # Step 2: Copy data with type casting for mismatched columns
            select_cols = []
            for col_name in column_names:
                # Check if this column has a type mismatch
                mismatch = next(
                    (m for m in mismatches if m['column'].lower() == col_name.lower()),
                    None
                )
                if mismatch:
                    expected_norm = normalize_sqlite_type(mismatch['expected_type'])
                    actual_norm = normalize_sqlite_type(mismatch['actual_type'])

                    # Cast value if converting between types
                    if actual_norm == 'INTEGER' and expected_norm == 'TEXT':
                        select_cols.append(f'CAST("{col_name}" AS TEXT)')
                    elif actual_norm == 'TEXT' and expected_norm == 'INTEGER':
                        select_cols.append(f'CAST("{col_name}" AS INTEGER)')
                    else:
                        select_cols.append(f'"{col_name}"')
                else:
                    select_cols.append(f'"{col_name}"')

            # Check which columns exist in old table
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            old_columns = {row[1].lower() for row in cursor.fetchall()}

            # Only copy columns that exist in both old and new table
            copy_select = []
            copy_insert = []
            for i, col_name in enumerate(column_names):
                if col_name.lower() in old_columns:
                    copy_select.append(select_cols[i])
                    copy_insert.append(f'"{col_name}"')

            if copy_insert:
                copy_sql = (
                    f'INSERT INTO "{temp_table_name}" ({", ".join(copy_insert)}) '
                    f'SELECT {", ".join(copy_select)} FROM "{table_name}"'
                )
                logger.debug("[DBTypeMigration] Copying data: %d columns", len(copy_insert))
                cursor.execute(copy_sql)
                copied_rows = cursor.rowcount
                logger.info("[DBTypeMigration] Copied %d row(s) from '%s'", copied_rows, table_name)

            # Step 3: Drop old table
            cursor.execute(f'DROP TABLE "{table_name}"')
            logger.debug("[DBTypeMigration] Dropped old table: %s", table_name)

            # Step 4: Rename new table to original name
            cursor.execute(f'ALTER TABLE "{temp_table_name}" RENAME TO "{table_name}"')
            logger.debug("[DBTypeMigration] Renamed temp table to: %s", table_name)

            # Step 5: Recreate indexes
            for idx in table_metadata.indexes:
                idx_name = idx.name
                idx_cols = [f'"{col.name}"' for col in idx.columns]
                if validate_identifier(idx_name):
                    idx_sql = (
                        f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                        f'ON "{table_name}" ({", ".join(idx_cols)})'
                    )
                    try:
                        cursor.execute(idx_sql)
                        logger.debug("[DBTypeMigration] Recreated index: %s", idx_name)
                    except Exception as idx_err:
                        logger.warning("[DBTypeMigration] Index %s failed: %s", idx_name, idx_err)

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys=ON")

            conn.commit()
            logger.info(
                "[DBTypeMigration] Successfully recreated table '%s' with correct schema",
                table_name
            )
            return True

        except Exception as e:
            conn.rollback()
            # Cleanup temp table if it exists
            try:
                cursor.execute(f'DROP TABLE IF EXISTS "{temp_table_name}"')
                conn.commit()
            except Exception:
                pass
            logger.error("[DBTypeMigration] Table recreation failed: %s", e)
            return False
        finally:
            conn.close()

    except Exception as e:
        logger.error("[DBTypeMigration] Table recreation error: %s", e, exc_info=True)
        return False
