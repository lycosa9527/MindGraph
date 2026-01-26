"""
Cleanup script for stuck chunk test documents.

This script finds documents stuck in 'processing' status and resets them
to 'failed' or 'pending' so they can be cleaned up or reprocessed.

Run with: python scripts/cleanup_stuck_chunk_test_documents.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('PYTHONPATH', str(project_root))

try:
    from sqlalchemy import and_
    
    # Import Diagram model FIRST - User model has a relationship to Diagram
    # This must be imported before config.database triggers User model configuration
    try:
        from models.domain.diagrams import Diagram
    except ImportError:
        # Diagram model may not exist - that's okay, relationships will use string references
        pass
    
    # Now import database session - this triggers model imports in config.database
    # which handles the correct import order for other models
    from config.database import SessionLocal
    
    # Now import the specific model we need
    # config.database already imported all necessary models in correct order
    from models.domain.knowledge_space import ChunkTestDocument
    
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("\nPlease ensure you're in the correct Python environment.")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"Error setting up models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


def cleanup_stuck_documents(user_id: int = None, reset_to: str = "failed", older_than_minutes: int = 30):
    """
    Find and reset stuck documents.
    
    Args:
        user_id: Optional user ID to filter by (None = all users)
        reset_to: Status to set ('failed' or 'pending')
        older_than_minutes: Only reset documents stuck longer than this (default: 30 minutes)
    """
    db = SessionLocal()
    
    try:
        # Find documents stuck in 'processing' status
        query = db.query(ChunkTestDocument).filter(
            ChunkTestDocument.status == 'processing'
        )
        
        if user_id:
            query = query.filter(ChunkTestDocument.user_id == user_id)
        
        stuck_docs = query.all()
        
        if not stuck_docs:
            print("✓ No stuck documents found.")
            return []
        
        print(f"\nFound {len(stuck_docs)} document(s) stuck in 'processing' status:")
        print("=" * 80)
        
        reset_docs = []
        cutoff_time = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        
        for doc in stuck_docs:
            # Check if document is old enough to be considered stuck
            # Use updated_at if available, otherwise created_at
            check_time = doc.updated_at if doc.updated_at else doc.created_at
            
            age_minutes = (datetime.utcnow() - check_time).total_seconds() / 60
            
            if check_time < cutoff_time:
                reset_docs.append((doc, age_minutes))
                print(f"  ✗ Document ID {doc.id}: '{doc.file_name}'")
                print(f"      User: {doc.user_id}, Age: {age_minutes:.1f} minutes")
                print(f"      Progress: {doc.processing_progress} ({doc.processing_progress_percent}%)")
            else:
                print(f"  ⏳ Document ID {doc.id}: '{doc.file_name}' (still processing, {age_minutes:.1f} min old)")
        
        if not reset_docs:
            print("\n✓ No documents are old enough to be considered stuck.")
            return []
        
        print("\n" + "=" * 80)
        print(f"RESET OPTIONS:")
        print("=" * 80)
        print(f"  Reset {len(reset_docs)} document(s) to '{reset_to}' status?")
        print("\nOptions:")
        print("  'failed' - Mark as failed (recommended for stuck documents)")
        print("  'pending' - Reset to pending (will be reprocessed)")
        print("  'delete' - Delete the documents entirely")
        
        response = input(f"\nReset to '{reset_to}'? (y/n/delete): ").strip().lower()
        
        if response == 'delete':
            # Delete documents
            deleted_count = 0
            for doc, _ in reset_docs:
                try:
                    # Delete file if exists
                    if os.path.exists(doc.file_path):
                        os.remove(doc.file_path)
                    
                    # Delete document (cascades to chunks)
                    db.delete(doc)
                    deleted_count += 1
                    print(f"  ✓ Deleted document {doc.id}: '{doc.file_name}'")
                except Exception as e:
                    print(f"  ✗ Failed to delete document {doc.id}: {e}")
            
            db.commit()
            print(f"\n✓ Deleted {deleted_count} document(s).")
            return reset_docs
        
        elif response == 'y':
            # Clean up Qdrant data and reset status
            from services.knowledge.chunk_test_document_service import ChunkTestDocumentService
            
            cleaned_qdrant_count = 0
            for doc, age_minutes in reset_docs:
                try:
                    # Clean up incomplete Qdrant operations
                    service = ChunkTestDocumentService(db, doc.user_id)
                    service.cleanup_incomplete_processing(doc.id)
                    cleaned_qdrant_count += 1
                    
                    # Update status
                    doc.status = reset_to
                    doc.processing_progress = None
                    doc.processing_progress_percent = 0
                    if reset_to == 'failed':
                        doc.error_message = f"Reset from stuck 'processing' status (was stuck for {age_minutes:.1f} minutes)"
                    else:
                        doc.error_message = None
                    
                    print(f"  ✓ Cleaned up document {doc.id}: '{doc.file_name}' (Qdrant + DB)")
                except Exception as e:
                    print(f"  ✗ Failed to cleanup document {doc.id}: {e}")
                    # Still reset status even if Qdrant cleanup failed
                    doc.status = reset_to
                    doc.processing_progress = None
                    doc.processing_progress_percent = 0
                    if reset_to == 'failed':
                        doc.error_message = f"Reset from stuck 'processing' status (was stuck for {age_minutes:.1f} minutes)"
                    else:
                        doc.error_message = None
            
            db.commit()
            print(f"\n✓ Reset {len(reset_docs)} document(s) to '{reset_to}' status.")
            if cleaned_qdrant_count > 0:
                print(f"✓ Cleaned up Qdrant data for {cleaned_qdrant_count} document(s).")
            return reset_docs
        
        else:
            print("\nSkipped. Documents remain in 'processing' status.")
            return []
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return []
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup stuck chunk test documents")
    parser.add_argument("--user-id", type=int, help="Filter by user ID (optional)")
    parser.add_argument("--reset-to", choices=["failed", "pending"], default="failed",
                       help="Status to reset to (default: failed)")
    parser.add_argument("--older-than", type=int, default=30,
                       help="Only reset documents stuck longer than N minutes (default: 30)")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Chunk Test Document Cleanup")
    print("=" * 80)
    
    if args.user_id:
        print(f"Filtering by user ID: {args.user_id}")
    print(f"Reset to: {args.reset_to}")
    print(f"Minimum age: {args.older_than} minutes")
    
    cleanup_stuck_documents(
        user_id=args.user_id,
        reset_to=args.reset_to,
        older_than_minutes=args.older_than
    )
