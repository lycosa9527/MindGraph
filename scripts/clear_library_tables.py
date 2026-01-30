"""
Clear library-related tables in PostgreSQL (dev environment only).

This script clears all library-related tables to allow a fresh start
with the new schema that includes image-based document support.

Tables cleared (in order due to foreign key constraints):
- library_danmaku_replies
- library_danmaku_likes
- library_danmaku
- library_bookmarks
- library_documents

Usage:
    python scripts/clear_library_tables.py
    python scripts/clear_library_tables.py --yes  # Skip confirmation
    python scripts/clear_library_tables.py --dry-run  # Preview only
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def clear_library_tables(db, dry_run: bool = False) -> tuple[int, dict]:
    """
    Clear all library-related tables.
    
    Args:
        db: Database session
        dry_run: If True, only show what would be deleted
        
    Returns:
        Tuple of (total_deleted, counts_dict)
    """
    from sqlalchemy import text
    
    counts = {}
    
    # Get counts before deletion using raw SQL to avoid model column issues
    # This works even if new columns haven't been added yet
    counts['danmaku_replies'] = db.execute(text("SELECT COUNT(*) FROM library_danmaku_replies")).scalar() or 0
    counts['danmaku_likes'] = db.execute(text("SELECT COUNT(*) FROM library_danmaku_likes")).scalar() or 0
    counts['danmaku'] = db.execute(text("SELECT COUNT(*) FROM library_danmaku")).scalar() or 0
    counts['bookmarks'] = db.execute(text("SELECT COUNT(*) FROM library_bookmarks")).scalar() or 0
    counts['documents'] = db.execute(text("SELECT COUNT(*) FROM library_documents")).scalar() or 0
    
    total = sum(counts.values())
    
    if dry_run:
        logger.info("DRY RUN - Would delete:")
        logger.info(f"  library_danmaku_replies: {counts['danmaku_replies']} records")
        logger.info(f"  library_danmaku_likes: {counts['danmaku_likes']} records")
        logger.info(f"  library_danmaku: {counts['danmaku']} records")
        logger.info(f"  library_bookmarks: {counts['bookmarks']} records")
        logger.info(f"  library_documents: {counts['documents']} records")
        logger.info(f"  Total: {total} records")
        return total, counts
    
    # Delete in order (respecting foreign key constraints) using raw SQL
    # This avoids issues with model columns that might not exist yet
    deleted_replies = db.execute(text("DELETE FROM library_danmaku_replies")).rowcount
    db.commit()
    logger.info(f"Deleted {deleted_replies} danmaku replies")
    
    deleted_likes = db.execute(text("DELETE FROM library_danmaku_likes")).rowcount
    db.commit()
    logger.info(f"Deleted {deleted_likes} danmaku likes")
    
    deleted_danmaku = db.execute(text("DELETE FROM library_danmaku")).rowcount
    db.commit()
    logger.info(f"Deleted {deleted_danmaku} danmaku")
    
    deleted_bookmarks = db.execute(text("DELETE FROM library_bookmarks")).rowcount
    db.commit()
    logger.info(f"Deleted {deleted_bookmarks} bookmarks")
    
    deleted_documents = db.execute(text("DELETE FROM library_documents")).rowcount
    db.commit()
    logger.info(f"Deleted {deleted_documents} documents")
    
    total_deleted = deleted_replies + deleted_likes + deleted_danmaku + deleted_bookmarks + deleted_documents
    
    return total_deleted, counts


def main():
    parser = argparse.ArgumentParser(
        description="Clear library-related tables in PostgreSQL (dev environment)"
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    try:
        from config.database import get_db
        from sqlalchemy.orm import Session
        
        logger.info("=" * 80)
        logger.info("CLEAR LIBRARY TABLES (Dev Environment)")
        logger.info("=" * 80)
        logger.info("")
        
        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            # Get counts (always use dry_run=True for counting)
            total, _ = clear_library_tables(db, dry_run=True)
            
            if args.dry_run:
                logger.info("")
                logger.info("Dry run complete - no changes made")
                return 0
            
            # Confirm unless --yes flag
            if not args.yes:
                logger.info("")
                logger.info(f"This will delete {total} records from library tables.")
                response = input("Are you sure? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    logger.info("Cancelled")
                    return 0
            
            # Clear tables
            logger.info("")
            logger.info("Clearing library tables...")
            total_deleted, _ = clear_library_tables(db, dry_run=False)
            
            logger.info("")
            logger.info("=" * 80)
            logger.info("SUCCESS")
            logger.info("=" * 80)
            logger.info(f"Deleted {total_deleted} records total")
            logger.info("")
            logger.info("Library tables cleared. You can now re-import documents with new schema.")
            
            return 0
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
