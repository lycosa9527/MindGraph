"""
Run database migrations standalone.

This script runs the database migration module to:
1. Create missing tables
2. Add missing columns to existing tables
3. Fix PostgreSQL sequences

Usage:
    python scripts/db/run_migrations.py
"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_status(engine, Base):
    """
    Check current database status using module function.
    
    Returns:
        tuple: (expected_tables, existing_tables, missing_tables)
    """
    from utils.migration.db_migration import check_database_status
    
    logger.info("=" * 60)
    logger.info("STEP 1: CHECK - Current Database Status")
    logger.info("=" * 60)
    
    # Import all models to ensure they're registered
    logger.info("Importing models to register with Base.metadata...")
    try:
        from models.domain.library import (
            LibraryDocument, LibraryDanmaku, LibraryDanmakuLike,
            LibraryDanmakuReply, LibraryBookmark
        )
        logger.info("✓ Library models imported")
        logger.debug(f"  - LibraryBookmark table: {LibraryBookmark.__tablename__}")
    except Exception as e:
        logger.warning(f"Could not import library models: {e}")
    
    # Use module function to check status
    status = check_database_status(engine, Base)
    expected_tables = status['expected_tables']
    existing_tables = status['existing_tables']
    missing_tables = status['missing_tables']
    missing_columns = status['missing_columns']
    
    # Log status
    logger.info(f"\nExpected tables in Base.metadata ({len(expected_tables)}):")
    for table_name in sorted(expected_tables):
        logger.info(f"  - {table_name}")
    
    logger.info(f"\nExisting tables in database ({len(existing_tables)}):")
    for table_name in sorted(existing_tables):
        logger.info(f"  - {table_name}")
    
    if missing_tables:
        logger.warning(f"\n⚠ Found {len(missing_tables)} missing table(s):")
        for table_name in sorted(missing_tables):
            logger.warning(f"  - {table_name}")
    else:
        logger.info("\n✓ All expected tables exist in database")
    
    if missing_columns:
        missing_columns_count = sum(len(cols) for cols in missing_columns.values())
        logger.warning(f"\n⚠ Found {missing_columns_count} missing column(s) across tables:")
        for table_name, missing_cols in missing_columns.items():
            logger.warning(
                f"  - Table '{table_name}': {len(missing_cols)} missing column(s): {', '.join(sorted(missing_cols))}"
            )
    else:
        logger.info("\n✓ All tables have all expected columns")
    
    return expected_tables, existing_tables, missing_tables


def verify_results(engine, Base, expected_tables):
    """
    Verify migration results using module function.
    
    Returns:
        bool: True if verification passed, False otherwise
    """
    from utils.migration.db_migration import verify_migration_results
    
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: VERIFY - Migration Results")
    logger.info("=" * 60)
    
    verification_passed, verification_details = verify_migration_results(
        engine, Base, expected_tables
    )
    
    # Log verification results
    if verification_details['tables_missing']:
        logger.error(f"\n✗ VERIFICATION FAILED: {len(verification_details['tables_missing'])} table(s) still missing:")
        for table_name in sorted(verification_details['tables_missing']):
            logger.error(f"  - {table_name}")
        return False
    else:
        logger.info(f"\n✓ All {len(expected_tables)} expected tables exist in database")
    
    if verification_details['columns_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some columns are still missing:")
        for table_name, missing_cols in verification_details['columns_missing'].items():
            logger.error(
                f"  ✗ Table '{table_name}': Missing columns: {', '.join(sorted(missing_cols))}"
            )
        return False
    else:
        logger.info("✓ All tables have all expected columns")
    
    if verification_details['sequences_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some sequences are still missing:")
        for table_name, missing_seqs in verification_details['sequences_missing'].items():
            logger.error(
                f"  ✗ Table '{table_name}': Missing sequences: {', '.join(sorted(missing_seqs))}"
            )
        return False
    else:
        logger.info("✓ All required sequences exist")
    
    if verification_details['indexes_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some indexes are still missing:")
        for table_name, missing_idxs in verification_details['indexes_missing'].items():
            logger.error(
                f"  ✗ Table '{table_name}': Missing indexes: {', '.join(sorted(missing_idxs))}"
            )
        return False
    else:
        logger.info("✓ All tables have all expected indexes")
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ VERIFICATION PASSED - All migrations applied successfully")
    logger.info("=" * 60)
    return True


def main():
    """Run database migrations."""
    try:
        logger.info("=" * 60)
        logger.info("Database Migration Script")
        logger.info("=" * 60)
        
        # Import database configuration
        logger.info("Importing database configuration...")
        from config.database import engine, Base
        
        # STEP 1: CHECK - Current status
        expected_tables, existing_tables, missing_tables = check_status(engine, Base)
        
        # STEP 2: ACT - Run migrations
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: ACT - Running Migrations")
        logger.info("=" * 60)
        
        from utils.migration.db_migration import run_migrations
        result = run_migrations()
        
        if not result:
            logger.error("\n✗ Migrations encountered errors")
            return 1
        
        # STEP 3: VERIFY - Confirm results
        verification_passed = verify_results(engine, Base, expected_tables)
        
        if verification_passed:
            return 0
        else:
            return 1
            
    except ImportError as e:
        logger.error(f"Import error: {e}", exc_info=True)
        logger.error("\nMake sure you're running this from the project root")
        logger.error("and that all dependencies are installed.")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
