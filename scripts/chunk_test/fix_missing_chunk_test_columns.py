"""
Migration script to add missing columns to chunk test tables.

This migration adds:
1. session_id column to chunk_test_results table
2. meta_data column to chunk_test_documents table (if missing)

Run with: python scripts/fix_missing_chunk_test_columns.py

Or run the SQL directly:
SQLite:
  ALTER TABLE chunk_test_results ADD COLUMN session_id TEXT NULL;
  ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;
  
PostgreSQL:
  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;
  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;
  
MySQL:
  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;
  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;
"""
import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ.setdefault('PYTHONPATH', str(project_root))

try:
    from sqlalchemy import text, inspect
    from config.database import engine
    from utils.migration.postgresql.schema_migration import run_migrations
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("\nPlease run this script from the project root with the correct Python environment.")
    print("\nOr run the SQL directly using your database client:")
    print("SQLite:")
    print("  ALTER TABLE chunk_test_results ADD COLUMN session_id TEXT NULL;")
    print("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;")
    print("\nPostgreSQL:")
    print("  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;")
    print("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
    print("\nMySQL:")
    print("  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;")
    print("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Error checking column existence: {e}")
        return False


def add_column_direct(table_name: str, column_name: str, column_type: str, nullable: bool = True):
    """Add a column directly using SQL."""
    try:
        dialect = engine.dialect.name
        nullable_clause = "NULL" if nullable else "NOT NULL"
        
        if dialect == 'sqlite':
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
        elif dialect == 'postgresql':
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
        elif dialect == 'mysql':
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
        else:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_clause}"
        
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        logger.info(f"Added column {column_name} to {table_name} using {dialect} dialect")
        return True
    except Exception as e:
        logger.error(f"Failed to add column {column_name} to {table_name}: {e}")
        return False


def migrate():
    """Add missing columns to chunk test tables."""
    logger.info("Starting migration: add missing columns to chunk test tables")
    
    try:
        # First, try automatic migrations
        logger.info("Running automatic migrations...")
        success = run_migrations()
        
        if success:
            logger.info("Automatic migration completed successfully!")
        else:
            logger.warning("Automatic migration had issues. Trying direct SQL...")
        
        # Check and add session_id to chunk_test_results
        if not check_column_exists('chunk_test_results', 'session_id'):
            logger.info("Adding session_id column to chunk_test_results...")
            dialect = engine.dialect.name
            if dialect == 'sqlite':
                add_column_direct('chunk_test_results', 'session_id', 'TEXT', nullable=True)
            elif dialect == 'postgresql':
                add_column_direct('chunk_test_results', 'session_id', 'VARCHAR(36)', nullable=True)
            elif dialect == 'mysql':
                add_column_direct('chunk_test_results', 'session_id', 'VARCHAR(36)', nullable=True)
            else:
                add_column_direct('chunk_test_results', 'session_id', 'TEXT', nullable=True)
            
            # Create index for session_id
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunk_test_results_session_id ON chunk_test_results(session_id)"))
                    conn.commit()
                logger.info("Created index on session_id column")
            except Exception as e:
                logger.warning(f"Failed to create index on session_id: {e}")
        else:
            logger.info("Column session_id already exists in chunk_test_results")
        
        # Check and add meta_data to chunk_test_documents
        if not check_column_exists('chunk_test_documents', 'meta_data'):
            logger.info("Adding meta_data column to chunk_test_documents...")
            dialect = engine.dialect.name
            if dialect == 'sqlite':
                add_column_direct('chunk_test_documents', 'meta_data', 'TEXT', nullable=True)
            elif dialect == 'postgresql':
                add_column_direct('chunk_test_documents', 'meta_data', 'JSON', nullable=True)
            elif dialect == 'mysql':
                add_column_direct('chunk_test_documents', 'meta_data', 'JSON', nullable=True)
            else:
                add_column_direct('chunk_test_documents', 'meta_data', 'TEXT', nullable=True)
        else:
            logger.info("Column meta_data already exists in chunk_test_documents")
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        logger.info("\nYou can also run the SQL directly using your database client:")
        logger.info("SQLite:")
        logger.info("  ALTER TABLE chunk_test_results ADD COLUMN session_id TEXT NULL;")
        logger.info("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;")
        logger.info("\nPostgreSQL:")
        logger.info("  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;")
        logger.info("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
        logger.info("\nMySQL:")
        logger.info("  ALTER TABLE chunk_test_results ADD COLUMN session_id VARCHAR(36) NULL;")
        logger.info("  ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
        raise


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
