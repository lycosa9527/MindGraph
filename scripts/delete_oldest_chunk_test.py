"""
Delete the oldest completed chunk test result that doesn't have session_id.

This script automatically finds and deletes the oldest completed test result.
"""
import importlib
import logging
import os
import sys

# Add project root to path before importing project modules
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Dynamic imports after path modification
# Import all models first to ensure relationships are resolved
try:
    importlib.import_module('models.auth')
    importlib.import_module('models.knowledge_space')
except Exception:
    pass  # Models may have circular dependencies, continue anyway

_config_database = importlib.import_module('config.database')
_models_knowledge_space = importlib.import_module('models.knowledge_space')

SessionLocal = _config_database.SessionLocal
engine = _config_database.engine
ChunkTestResult = _models_knowledge_space.ChunkTestResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_for_session_id_column():
    """Check if session_id column exists in the table."""
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    
    if 'chunk_test_results' not in inspector.get_table_names():
        return False
    
    columns = [col['name'] for col in inspector.get_columns('chunk_test_results')]
    return 'session_id' in columns


def find_oldest_test_without_session_id(db):
    """Find the oldest test result without session_id."""
    from sqlalchemy import text
    
    has_session_id_column = check_for_session_id_column()
    
    if has_session_id_column:
        # Query for oldest record where session_id is NULL
        query = text("""
            SELECT id FROM chunk_test_results 
            WHERE session_id IS NULL 
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        result = db.execute(query)
        row = result.first()
        return row[0] if row else None
    else:
        # If column doesn't exist, get oldest test using raw SQL
        query = text("""
            SELECT id FROM chunk_test_results 
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        result = db.execute(query)
        row = result.first()
        return row[0] if row else None


def get_test_info(db, test_id: int):
    """Get test information using raw SQL."""
    from sqlalchemy import text
    
    query = text("""
        SELECT id, user_id, dataset_name, status, created_at, document_ids,
               semchunk_chunk_count, mindchunk_chunk_count
        FROM chunk_test_results 
        WHERE id = :test_id
    """)
    result = db.execute(query, {"test_id": test_id})
    row = result.first()
    return row if row else None


def delete_test_by_id(db, test_id: int) -> bool:
    """Delete a test result by ID using raw SQL."""
    from sqlalchemy import text
    
    # Get test info first
    test_info = get_test_info(db, test_id)
    if not test_info:
        print(f"Test {test_id} not found")
        return False
    
    try:
        print("\nTest to delete:")
        print(f"  ID: {test_info[0]}")
        print(f"  User ID: {test_info[1]}")
        print(f"  Dataset: {test_info[2]}")
        print(f"  Status: {test_info[3]}")
        print(f"  Created: {test_info[4]}")
        if test_info[5]:
            print(f"  Document IDs: {test_info[5]}")
        
        # Delete using raw SQL
        delete_query = text("DELETE FROM chunk_test_results WHERE id = :test_id")
        db.execute(delete_query, {"test_id": test_id})
        db.commit()
        print(f"\n[SUCCESS] Successfully deleted test {test_id}")
        return True
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error deleting test {test_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    db = SessionLocal()
    
    try:
        print("Checking for chunk test results without session_id...")
        
        test_id = find_oldest_test_without_session_id(db)
        
        if not test_id:
            print("No test results found without session_id.")
            return
        
        # Delete the test
        if delete_test_by_id(db, test_id):
            print("Done!")
        else:
            print("Failed to delete test.")
    
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
