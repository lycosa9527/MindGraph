"""
Script to remove chunk test results that don't have session_id.

This script identifies and removes chunk test results that were created
before session_id tracking was implemented.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from config.database import SessionLocal
from models.domain.knowledge_space import ChunkTestResult


def find_tests_without_session_id(db: Session) -> list:
    """
    Find chunk test results that don't have session_id.
    
    Since session_id field doesn't exist in the schema, we'll identify
    old records by checking if they have certain characteristics or
    by date range. For now, we'll list all records and let user decide.
    """
    results = db.query(ChunkTestResult).order_by(ChunkTestResult.created_at.desc()).all()
    
    # Since there's no session_id field, we'll show all results
    # User can identify which ones to delete
    return results


def delete_test_result(db: Session, test_id: int) -> bool:
    """Delete a specific test result by ID."""
    test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
    
    if not test_result:
        print(f"Test result {test_id} not found")
        return False
    
    try:
        db.delete(test_result)
        db.commit()
        print(f"Successfully deleted test result {test_id}")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error deleting test result {test_id}: {e}")
        return False


def main():
    """Main function to list and optionally delete test results."""
    db = SessionLocal()
    
    try:
        # Get all test results
        results = find_tests_without_session_id(db)
        
        if not results:
            print("No chunk test results found")
            return
        
        print(f"\nFound {len(results)} chunk test result(s):")
        print("-" * 80)
        
        for result in results:
            print(f"ID: {result.id}")
            print(f"  User ID: {result.user_id}")
            print(f"  Dataset: {result.dataset_name}")
            print(f"  Status: {result.status}")
            print(f"  Created: {result.created_at}")
            print(f"  Document IDs: {result.document_ids}")
            print()
        
        # Ask user which ones to delete
        print("\nEnter test IDs to delete (comma-separated), or 'all' to delete all, or 'cancel' to exit:")
        user_input = input().strip()
        
        if user_input.lower() == 'cancel':
            print("Cancelled")
            return
        
        if user_input.lower() == 'all':
            confirm = input("Are you sure you want to delete ALL test results? (yes/no): ")
            if confirm.lower() == 'yes':
                deleted_count = 0
                for result in results:
                    if delete_test_result(db, result.id):
                        deleted_count += 1
                print(f"\nDeleted {deleted_count} test result(s)")
            else:
                print("Cancelled")
        else:
            # Parse comma-separated IDs
            try:
                test_ids = [int(id.strip()) for id in user_input.split(',')]
                deleted_count = 0
                for test_id in test_ids:
                    if delete_test_result(db, test_id):
                        deleted_count += 1
                print(f"\nDeleted {deleted_count} test result(s)")
            except ValueError:
                print("Invalid input. Please enter comma-separated test IDs or 'all'")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
