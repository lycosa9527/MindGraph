"""
Clear library-related tables in SQLite or PostgreSQL (dev environment only).

This script clears all library-related tables to allow a fresh start
with the new schema that includes image-based document support.

Tables cleared (in order due to foreign key constraints):
- library_danmaku_replies
- library_danmaku_likes
- library_danmaku
- library_bookmarks
- library_documents

Usage:
    python scripts/db/clear_library_tables.py
    python scripts/db/clear_library_tables.py --yes  # Skip confirmation
    python scripts/db/clear_library_tables.py --dry-run  # Preview only
"""
import argparse
import importlib
import logging
import sys
from pathlib import Path

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

# Add project root to path before importing project modules
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

# Dynamic imports to avoid Ruff E402 warning
_config_database = importlib.import_module('config.database')
get_db = _config_database.get_db
engine = _config_database.engine

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def is_sqlite_database() -> bool:
    """
    Check if the current database is SQLite.

    Returns:
        True if SQLite, False otherwise
    """
    return engine.dialect.name == 'sqlite'


def table_exists(_db: Session, table_name: str) -> bool:
    """
    Check if a table exists in the database.

    Args:
        _db: Database session (unused, kept for API consistency)
        table_name: Name of the table to check

    Returns:
        True if table exists, False otherwise
    """
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def get_table_count(db: Session, table_name: str) -> int:
    """
    Get the count of records in a table, returning 0 if table doesn't exist.

    Args:
        db: Database session
        table_name: Name of the table

    Returns:
        Count of records, or 0 if table doesn't exist
    """
    if not table_exists(db, table_name):
        return 0
    try:
        result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0
    except Exception as e:
        logger.warning("Error counting records in %s: %s", table_name, e)
        return 0


def clear_library_tables(db: Session, dry_run: bool = False) -> tuple[int, dict]:
    """
    Clear all library-related tables.

    Args:
        db: Database session
        dry_run: If True, only show what would be deleted

    Returns:
        Tuple of (total_deleted, counts_dict)
    """
    # Enable foreign keys for SQLite (required for CASCADE deletes)
    if is_sqlite_database():
        db.execute(text("PRAGMA foreign_keys = ON"))
        db.commit()

    counts = {}

    # Get counts before deletion using raw SQL to avoid model column issues
    # This works even if new columns haven't been added yet
    # Check table existence first to avoid errors
    counts['danmaku_replies'] = get_table_count(db, 'library_danmaku_replies')
    counts['danmaku_likes'] = get_table_count(db, 'library_danmaku_likes')
    counts['danmaku'] = get_table_count(db, 'library_danmaku')
    counts['bookmarks'] = get_table_count(db, 'library_bookmarks')
    counts['documents'] = get_table_count(db, 'library_documents')

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
    # Use pre-computed counts for deleted totals (full table delete = count before)
    if table_exists(db, 'library_danmaku_replies'):
        db.execute(text("DELETE FROM library_danmaku_replies"))
        db.commit()
        logger.info("Deleted %s danmaku replies", counts['danmaku_replies'])

    if table_exists(db, 'library_danmaku_likes'):
        db.execute(text("DELETE FROM library_danmaku_likes"))
        db.commit()
        logger.info("Deleted %s danmaku likes", counts['danmaku_likes'])

    if table_exists(db, 'library_danmaku'):
        db.execute(text("DELETE FROM library_danmaku"))
        db.commit()
        logger.info("Deleted %s danmaku", counts['danmaku'])

    if table_exists(db, 'library_bookmarks'):
        db.execute(text("DELETE FROM library_bookmarks"))
        db.commit()
        logger.info("Deleted %s bookmarks", counts['bookmarks'])

    if table_exists(db, 'library_documents'):
        db.execute(text("DELETE FROM library_documents"))
        db.commit()
        logger.info("Deleted %s documents", counts['documents'])

    total_deleted = sum(counts.values())

    return total_deleted, counts


def main():
    """
    Main entry point for clearing library tables.

    Parses command line arguments and executes the table clearing operation.
    """
    parser = argparse.ArgumentParser(
        description="Clear library-related tables in SQLite or PostgreSQL (dev environment)"
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

        # Detect database type
        db_type = "SQLite" if is_sqlite_database() else "PostgreSQL"
        logger.info("Database type: %s", db_type)
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
