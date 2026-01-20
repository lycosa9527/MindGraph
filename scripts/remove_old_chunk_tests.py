"""
Remove chunk test results that don't have session_id.

Since the ChunkTestResult model doesn't currently have a session_id field,
this script will list all test results and allow you to identify which ones
to delete (e.g., old test results from before session tracking was added).
"""
import importlib
import logging
import os
import sys

# Add project root to path
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


def list_all_test_results(db):
    """List all chunk test results."""
    results = db.query(ChunkTestResult).order_by(ChunkTestResult.created_at.desc()).all()
    return results


def check_for_session_id_column(_db):
    """Check if session_id column exists in the table."""
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    
    if 'chunk_test_results' not in inspector.get_table_names():
        return False
    
    columns = [col['name'] for col in inspector.get_columns('chunk_test_results')]
    return 'session_id' in columns


def find_tests_without_session_id(db):
    """Find tests that don't have session_id (if column exists)."""
    from sqlalchemy import text
    
    has_session_id_column = check_for_session_id_column(db)
    
    if has_session_id_column:
        # Query for records where session_id is NULL
        query = text("SELECT id FROM chunk_test_results WHERE session_id IS NULL")
        result = db.execute(query)
        return [row[0] for row in result]
    else:
        # If column doesn't exist, return all test IDs (they all lack session_id)
        results = db.query(ChunkTestResult).all()
        return [r.id for r in results]


def delete_test_by_id(db, test_id: int) -> bool:
    """Delete a test result by ID."""
    test = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
    if not test:
        print(f"Test {test_id} not found")
        return False
    
    try:
        db.delete(test)
        db.commit()
        print(f"✓ Deleted test {test_id}")
        return True
    except Exception as e:
        db.rollback()
        print(f"✗ Error deleting test {test_id}: {e}")
        return False


def main():
    """Main function."""
    db = SessionLocal()
    
    try:
        # Check if session_id column exists
        has_session_id_column = check_for_session_id_column(db)
        
        if has_session_id_column:
            print("✓ Found session_id column in chunk_test_results table")
            print("Finding tests without session_id...")
            test_ids_without_session = find_tests_without_session_id(db)
            
            if not test_ids_without_session:
                print("No test results found without session_id.")
                return
            
            print(f"\nFound {len(test_ids_without_session)} test result(s) without session_id:")
            print("=" * 100)
            
            # Show details of tests without session_id
            for test_id in test_ids_without_session:
                result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
                if result:
                    print(f"\nTest ID: {result.id}")
                    print(f"    User ID: {result.user_id}")
                    print(f"    Dataset: {result.dataset_name}")
                    print(f"    Status: {result.status}")
                    print(f"    Created: {result.created_at}")
                    if result.document_ids:
                        print(f"    Document IDs: {result.document_ids}")
            
            print("\n" + "=" * 100)
            confirm = input(f"\nDelete {len(test_ids_without_session)} test result(s) without session_id? (yes/no): ").strip()
            
            if confirm.lower() == 'yes':
                deleted = 0
                for test_id in test_ids_without_session:
                    if delete_test_by_id(db, test_id):
                        deleted += 1
                print(f"\n✓ Deleted {deleted} test result(s)")
            else:
                print("Cancelled. No changes made.")
        else:
            print("ℹ session_id column does not exist in chunk_test_results table")
            print("Listing all test results...")
            results = list_all_test_results(db)
            
            if not results:
                print("No chunk test results found in database.")
                return
            
            print(f"\nFound {len(results)} test result(s):\n")
            print("=" * 100)
            
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] Test ID: {result.id}")
                print(f"    User ID: {result.user_id}")
                print(f"    Dataset: {result.dataset_name}")
                print(f"    Status: {result.status}")
                print(f"    Created: {result.created_at}")
                if result.document_ids:
                    print(f"    Document IDs: {result.document_ids}")
                print(f"    Chunks (semchunk/mindchunk): {result.semchunk_chunk_count}/{result.mindchunk_chunk_count}")
            
            print("\n" + "=" * 100)
            print("\nTo delete test results, enter:")
            print("  - Test ID(s) separated by commas (e.g., 1,2,3)")
            print("  - 'cancel' or press Enter to exit")
            
            user_input = input("\nYour choice: ").strip()
            
            if not user_input or user_input.lower() == 'cancel':
                print("Cancelled. No changes made.")
                return
            
            # Parse comma-separated IDs
            try:
                test_ids = [int(id.strip()) for id in user_input.split(',')]
                deleted = 0
                for test_id in test_ids:
                    if delete_test_by_id(db, test_id):
                        deleted += 1
                print(f"\n✓ Deleted {deleted} test result(s)")
            except ValueError:
                print("✗ Invalid input. Please enter numeric test IDs separated by commas.")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
