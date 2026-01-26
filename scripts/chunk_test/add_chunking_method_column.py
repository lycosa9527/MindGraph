"""
Migration script to add chunking_method column to chunk_test_document_chunks table.

This migration adds a dedicated column for chunking_method instead of storing it only in JSON metadata.
This allows efficient querying and filtering by chunking method.

Run with: python scripts/add_chunking_method_column.py
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from config.database import engine, get_db
from models.domain.knowledge_space import ChunkTestDocumentChunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add chunking_method column and migrate data from meta_data."""
    logger.info("Starting migration: add chunking_method column")

    with engine.connect() as conn:
        # Check if column already exists
        inspector = __import__('sqlalchemy').inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('chunk_test_document_chunks')]

        if 'chunking_method' in columns:
            logger.info("Column chunking_method already exists. Skipping migration.")
            return

        # Add column (nullable first, we'll populate it)
        logger.info("Adding chunking_method column...")
        conn.execute(text("""
            ALTER TABLE chunk_test_document_chunks
            ADD COLUMN chunking_method VARCHAR(50) NULL
        """))
        conn.commit()

        # Create index
        logger.info("Creating index on chunking_method...")
        try:
            conn.execute(text("""
                CREATE INDEX ix_chunk_test_document_chunks_chunking_method
                ON chunk_test_document_chunks(chunking_method)
            """))
            conn.commit()
        except Exception as e:
            logger.warning(f"Index creation failed (may already exist): {e}")

        # Create composite index
        logger.info("Creating composite index on (document_id, chunking_method)...")
        try:
            conn.execute(text("""
                CREATE INDEX ix_chunk_test_document_chunks_document_method
                ON chunk_test_document_chunks(document_id, chunking_method)
            """))
            conn.commit()
        except Exception as e:
            logger.warning(f"Composite index creation failed (may already exist): {e}")

        # Migrate data from meta_data JSON to column
        logger.info("Migrating data from meta_data to chunking_method column...")
        
        # Get database dialect
        dialect = engine.dialect.name
        
        if dialect == 'sqlite':
            # SQLite JSON extraction
            conn.execute(text("""
                UPDATE chunk_test_document_chunks
                SET chunking_method = json_extract(meta_data, '$.chunking_method')
                WHERE meta_data IS NOT NULL
                AND json_extract(meta_data, '$.chunking_method') IS NOT NULL
            """))
        elif dialect == 'postgresql':
            # PostgreSQL JSON extraction
            conn.execute(text("""
                UPDATE chunk_test_document_chunks
                SET chunking_method = meta_data->>'chunking_method'
                WHERE meta_data IS NOT NULL
                AND meta_data->>'chunking_method' IS NOT NULL
            """))
        elif dialect == 'mysql':
            # MySQL JSON extraction
            conn.execute(text("""
                UPDATE chunk_test_document_chunks
                SET chunking_method = JSON_UNQUOTE(JSON_EXTRACT(meta_data, '$.chunking_method'))
                WHERE meta_data IS NOT NULL
                AND JSON_EXTRACT(meta_data, '$.chunking_method') IS NOT NULL
            """))
        else:
            logger.warning(f"Unknown database dialect: {dialect}. Skipping data migration.")
            logger.info("Please manually migrate data from meta_data to chunking_method column.")
            conn.commit()
            return

        conn.commit()
        
        # Count migrated rows
        result = conn.execute(text("""
            SELECT COUNT(*) FROM chunk_test_document_chunks
            WHERE chunking_method IS NOT NULL
        """))
        migrated_count = result.scalar()
        logger.info(f"Migrated {migrated_count} rows from meta_data to chunking_method column")

        logger.info("Migration completed successfully!")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
