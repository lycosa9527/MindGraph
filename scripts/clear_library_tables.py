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
import importlib.util
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

# Add project root to path before importing project modules
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

# Dynamic imports to avoid Ruff E402 warning
_config_database = importlib.import_module('config.database')
get_db = _config_database.get_db

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
        logger.info("  library_danmaku_replies: %s records", counts['danmaku_replies'])
        logger.info("  library_danmaku_likes: %s records", counts['danmaku_likes'])
        logger.info("  library_danmaku: %s records", counts['danmaku'])
        logger.info("  library_bookmarks: %s records", counts['bookmarks'])
        logger.info("  library_documents: %s records", counts['documents'])
        logger.info("  Total: %s records", total)
        return total, counts

    # Delete in order (respecting foreign key constraints) using raw SQL
    # This avoids issues with model columns that might not exist yet
    deleted_replies = db.execute(text("DELETE FROM library_danmaku_replies")).rowcount
    db.commit()
    logger.info("Deleted %s danmaku replies", deleted_replies)

    deleted_likes = db.execute(text("DELETE FROM library_danmaku_likes")).rowcount
    db.commit()
    logger.info("Deleted %s danmaku likes", deleted_likes)

    deleted_danmaku = db.execute(text("DELETE FROM library_danmaku")).rowcount
    db.commit()
    logger.info("Deleted %s danmaku", deleted_danmaku)

    deleted_bookmarks = db.execute(text("DELETE FROM library_bookmarks")).rowcount
    db.commit()
    logger.info("Deleted %s bookmarks", deleted_bookmarks)

    deleted_documents = db.execute(text("DELETE FROM library_documents")).rowcount
    db.commit()
    logger.info("Deleted %s documents", deleted_documents)

    total_deleted = deleted_replies + deleted_likes + deleted_danmaku + deleted_bookmarks + deleted_documents

    return total_deleted, counts


def main():
    """
    Main entry point for clearing library tables.

    Parses command line arguments and executes the table clearing operation.
    """
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
                logger.info("This will delete %s records from library tables.", total)
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
            logger.info("Deleted %s records total", total_deleted)
            logger.info("")
            logger.info("Library tables cleared. You can now re-import documents with new schema.")

            return 0

        finally:
            db.close()

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
