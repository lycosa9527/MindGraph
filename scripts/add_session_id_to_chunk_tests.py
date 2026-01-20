"""
Add session_id column to chunk_test_results table.

This migration script adds the session_id column to existing chunk_test_results table
and generates UUIDs for existing records that don't have one.
"""
import importlib
import logging
import os
import sys
import uuid

# Add project root to path before importing project modules
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Dynamic imports after path modification
_config_database = importlib.import_module('config.database')

SessionLocal = _config_database.SessionLocal
engine = _config_database.engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists():
    """Check if session_id column already exists."""
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    
    if 'chunk_test_results' not in inspector.get_table_names():
        logger.warning("Table chunk_test_results does not exist")
        return False
    
    columns = [col['name'] for col in inspector.get_columns('chunk_test_results')]
    return 'session_id' in columns


def add_session_id_column():
    """Add session_id column to chunk_test_results table."""
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Check if column already exists
        if check_column_exists():
            logger.info("Column session_id already exists in chunk_test_results")
            return True
        
        # Add column
        logger.info("Adding session_id column to chunk_test_results...")
        alter_query = text("""
            ALTER TABLE chunk_test_results 
            ADD COLUMN session_id VARCHAR(36)
        """)
        db.execute(alter_query)
        
        # Create index
        logger.info("Creating index on session_id...")
        index_query = text("""
            CREATE INDEX IF NOT EXISTS ix_chunk_test_results_session_id 
            ON chunk_test_results(session_id)
        """)
        db.execute(index_query)
        
        db.commit()
        logger.info("Successfully added session_id column and index")
        
        # Generate UUIDs for existing records
        logger.info("Generating UUIDs for existing records...")
        update_query = text("""
            UPDATE chunk_test_results 
            SET session_id = :session_id 
            WHERE session_id IS NULL AND id = :test_id
        """)
        
        # Get all records without session_id
        select_query = text("SELECT id FROM chunk_test_results WHERE session_id IS NULL")
        result = db.execute(select_query)
        rows = result.fetchall()
        
        updated_count = 0
        for row in rows:
            test_id = row[0]
            new_uuid = str(uuid.uuid4())
            db.execute(update_query, {"session_id": new_uuid, "test_id": test_id})
            updated_count += 1
        
        db.commit()
        logger.info(f"Generated UUIDs for {updated_count} existing records")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding session_id column: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Main function."""
    print("=" * 80)
    print("Migration: Add session_id to chunk_test_results")
    print("=" * 80)
    print()
    
    if check_column_exists():
        print("✓ Column session_id already exists")
        print("Skipping migration.")
        return
    
    print("Adding session_id column...")
    if add_session_id_column():
        print("\n✓ Migration completed successfully!")
        print("\nAll chunk test results now have UUID session_id values.")
    else:
        print("\n✗ Migration failed. Check logs for details.")


if __name__ == "__main__":
    main()
