"""
Migration script to add meta_data column to chunk_test_documents table.

This migration adds a JSON column for storing processing results and metadata.

Run with: python scripts/add_meta_data_to_chunk_test_documents.py

Or run the SQL directly:
SQLite: ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;
PostgreSQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;
MySQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;
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
    from sqlalchemy import text
    from config.database import engine
    from utils.migration.postgresql.schema_migration import run_migrations
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("\nPlease run this script from the project root with the correct Python environment.")
    print("\nOr run the SQL directly using your database client:")
    print("SQLite: ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;")
    print("PostgreSQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
    print("MySQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add meta_data column to chunk_test_documents table."""
    logger.info("Starting migration: add meta_data column to chunk_test_documents")

    try:
        # Use the existing run_migrations() function which will detect missing columns
        logger.info("Running automatic migrations...")
        success = run_migrations()

        if success:
            logger.info("Migration completed successfully!")
            logger.info("The meta_data column should now be added to chunk_test_documents table.")
        else:
            logger.warning("Automatic migration had issues. Trying direct SQL...")
            # Try direct SQL as fallback
            with engine.connect() as conn:
                # Check if column already exists
                inspector = __import__('sqlalchemy').inspect(engine)
                try:
                    columns = [col['name'] for col in inspector.get_columns('chunk_test_documents')]
                    if 'meta_data' in columns:
                        logger.info("Column meta_data already exists. Migration not needed.")
                        return
                except Exception:
                    pass

                dialect = engine.dialect.name
                logger.info(f"Adding meta_data column using {dialect} dialect...")
                if dialect == 'sqlite':
                    conn.execute(text("ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL"))
                elif dialect == 'postgresql':
                    conn.execute(text("ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL"))
                elif dialect == 'mysql':
                    conn.execute(text("ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL"))
                else:
                    conn.execute(text("ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL"))
                conn.commit()
                logger.info("Direct SQL migration completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        logger.info("\nYou can also run the SQL directly using your database client:")
        logger.info("SQLite: ALTER TABLE chunk_test_documents ADD COLUMN meta_data TEXT NULL;")
        logger.info("PostgreSQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
        logger.info("MySQL: ALTER TABLE chunk_test_documents ADD COLUMN meta_data JSON NULL;")
        raise


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
