"""
Script to manually add missing columns to chunk_test_results table.

This is a one-time fix for databases that were created before all columns
were added to the ChunkTestResult model.
"""

import importlib
import logging
import os
import sys

from sqlalchemy import inspect, text

# Add project root to path before importing project modules
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Dynamic imports after path modification
_config_database = importlib.import_module('config.database')
_models_knowledge_space = importlib.import_module('models.knowledge_space')

SessionLocal = _config_database.SessionLocal
engine = _config_database.engine
ChunkTestResult = _models_knowledge_space.ChunkTestResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sqlite_column_type(column):
    """Get SQLite column type string from SQLAlchemy column."""
    column_type = str(column.type)
    column_type_upper = column_type.upper()

    # Handle ENUM types - SQLite stores as TEXT
    if hasattr(column.type, 'enums') or 'ENUM' in str(type(column.type)).upper():
        return "TEXT"

    # Map common types
    if "INTEGER" in column_type_upper or "BIGINT" in column_type_upper:
        return "INTEGER"
    elif "REAL" in column_type_upper or "FLOAT" in column_type_upper or "DOUBLE" in column_type_upper:
        return "REAL"
    elif ("TEXT" in column_type_upper or "VARCHAR" in column_type_upper or
          "STRING" in column_type_upper or "CHAR" in column_type_upper):
        return "TEXT"
    elif "DATETIME" in column_type_upper or "DATE" in column_type_upper or "TIMESTAMP" in column_type_upper:
        return "TEXT"
    elif "JSON" in column_type_upper:
        return "TEXT"  # SQLite stores JSON as TEXT
    elif "BLOB" in column_type_upper:
        return "BLOB"
    else:
        return "TEXT"  # Default to TEXT


def get_column_default_sql(column, has_rows):
    """Get SQL default clause for a column."""
    if column.default is None:
        if column.nullable:
            return ""
        # NOT NULL without default - need to provide default if table has rows
        if has_rows:
            column_type = get_sqlite_column_type(column)
            if "INTEGER" in column_type:
                return "DEFAULT 0"
            elif "TEXT" in column_type:
                # Check if it's an ENUM with a default
                if hasattr(column.type, 'enums'):
                    # For ENUM, use first value as default if no explicit default
                    return "DEFAULT 'pending'"  # Common default for status columns
                return "DEFAULT ''"
        return ""

    # Handle explicit defaults
    if hasattr(column.default, 'arg'):
        default_value = column.default.arg
        if isinstance(default_value, (int, float)):
            return f"DEFAULT {default_value}"
        elif isinstance(default_value, bool):
            return f"DEFAULT {1 if default_value else 0}"
        elif isinstance(default_value, str):
            return f"DEFAULT '{default_value}'"
        elif callable(default_value):
            # Callable defaults (like datetime.utcnow) can't be set in ALTER TABLE
            # SQLAlchemy will handle them on insert
            return ""

    return ""


def fix_chunk_test_columns():
    """Add all missing columns to chunk_test_results table."""
    inspector = inspect(engine)

    # Check if table exists
    if 'chunk_test_results' not in inspector.get_table_names():
        logger.error("Table 'chunk_test_results' does not exist")
        return False

    # Get existing columns
    existing_columns = {col['name'] for col in inspector.get_columns('chunk_test_results')}
    logger.info("Existing columns: %s", sorted(existing_columns))

    # Get expected columns from model
    table = ChunkTestResult.__table__
    expected_columns = {col.name for col in table.columns}
    logger.info("Expected columns: %s", sorted(expected_columns))

    # Find missing columns
    missing_columns = expected_columns - existing_columns

    if not missing_columns:
        logger.info("All columns already exist in chunk_test_results table")
        return True

    logger.info("Missing columns: %s", sorted(missing_columns))

    # Check if table has any rows
    db = SessionLocal()
    try:
        count_query = db.execute(text("SELECT COUNT(*) FROM chunk_test_results"))
        row_count = count_query.scalar()
        has_rows = row_count and row_count > 0
        logger.info("Table has %d row(s)", row_count)

        # Add each missing column
        for column_name in sorted(missing_columns):
            column = table.columns[column_name]
            column_type = get_sqlite_column_type(column)
            nullable = "NULL" if column.nullable else "NOT NULL"
            default_clause = get_column_default_sql(column, has_rows)

            # Build ALTER TABLE statement
            sql = f"ALTER TABLE chunk_test_results ADD COLUMN {column_name} {column_type} {nullable}"
            if default_clause:
                sql += f" {default_clause}"

            logger.info("Adding column '%s': %s", column_name, sql)
            db.execute(text(sql))
            logger.info("Successfully added column '%s'", column_name)

        db.commit()
        logger.info("Successfully added %d column(s) to chunk_test_results table", len(missing_columns))
        return True

    except Exception as e:
        logger.error("Failed to add columns: %s", e, exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    SUCCESS = fix_chunk_test_columns()
    sys.exit(0 if SUCCESS else 1)
