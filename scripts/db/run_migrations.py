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

from config.database import Base, engine
from utils.migration.postgresql.schema_migration import (
    check_database_status,
    run_migrations,
    verify_migration_results,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def ensure_models_registered(base):
    """
    Ensure all models are imported and registered with Base.metadata.

    This is important because config.database imports models, but we want
    to ensure they're all registered before checking database status.

    Args:
        base: SQLAlchemy Base metadata object

    Returns:
        bool: True if models are registered, False otherwise
    """
    logger.info("Ensuring all models are registered with Base.metadata...")

    try:
        registered_tables = set(base.metadata.tables.keys())
        logger.info(
            "✓ Models registered: %d table(s) in Base.metadata",
            len(registered_tables)
        )
        logger.debug("Registered tables: %s", ', '.join(sorted(registered_tables)))
        return True
    except Exception as e:
        logger.error("Failed to check model registration: %s", e)
        return False


def check_status(engine, base):
    """
    Check current database status using module function.

    Returns:
        tuple: (expected_tables, existing_tables, missing_tables)
    """
    logger.info("%s", "=" * 60)
    logger.info("STEP 1: CHECK - Current Database Status")
    logger.info("%s", "=" * 60)

    # Use module function to check status
    status = check_database_status(engine, base)
    expected_tables = status['expected_tables']
    existing_tables = status['existing_tables']
    missing_tables = status['missing_tables']
    missing_columns = status['missing_columns']

    # Log status
    logger.info("\nExpected tables in Base.metadata (%d):", len(expected_tables))
    for table_name in sorted(expected_tables):
        logger.info("  - %s", table_name)

    logger.info("\nExisting tables in database (%d):", len(existing_tables))
    for table_name in sorted(existing_tables):
        logger.info("  - %s", table_name)

    if missing_tables:
        logger.warning("\n⚠ Found %d missing table(s):", len(missing_tables))
        for table_name in sorted(missing_tables):
            logger.warning("  - %s", table_name)
    else:
        logger.info("\n✓ All expected tables exist in database")

    if missing_columns:
        missing_columns_count = sum(len(cols) for cols in missing_columns.values())
        logger.warning("\n⚠ Found %d missing column(s) across tables:", missing_columns_count)
        for table_name, missing_cols in missing_columns.items():
            logger.warning(
                "  - Table '%s': %d missing column(s): %s",
                table_name, len(missing_cols), ', '.join(sorted(missing_cols))
            )
    else:
        logger.info("\n✓ All tables have all expected columns")

    return expected_tables, existing_tables, missing_tables


def verify_results(engine, base, expected_tables):
    """
    Verify migration results using module function.

    Returns:
        bool: True if verification passed, False otherwise
    """
    logger.info("\n%s", "=" * 60)
    logger.info("STEP 3: VERIFY - Migration Results")
    logger.info("%s", "=" * 60)

    verification_passed, verification_details = verify_migration_results(
        engine, base, expected_tables
    )

    # Log verification results
    if verification_details['tables_missing']:
        logger.error(
            "\n✗ VERIFICATION FAILED: %d table(s) still missing:",
            len(verification_details['tables_missing'])
        )
        for table_name in sorted(verification_details['tables_missing']):
            logger.error("  - %s", table_name)
        return False
    else:
        logger.info("\n✓ All %d expected tables exist in database", len(expected_tables))

    if verification_details['columns_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some columns are still missing:")
        for table_name, missing_cols in verification_details['columns_missing'].items():
            logger.error(
                "  ✗ Table '%s': Missing columns: %s",
                table_name, ', '.join(sorted(missing_cols))
            )
        return False
    else:
        logger.info("✓ All tables have all expected columns")

    if verification_details['sequences_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some sequences are still missing:")
        for table_name, missing_seqs in verification_details['sequences_missing'].items():
            logger.error(
                "  ✗ Table '%s': Missing sequences: %s",
                table_name, ', '.join(sorted(missing_seqs))
            )
        return False
    else:
        logger.info("✓ All required sequences exist")

    if verification_details['indexes_missing']:
        logger.error("\n✗ VERIFICATION FAILED: Some indexes are still missing:")
        for table_name, missing_idxs in verification_details['indexes_missing'].items():
            logger.error(
                "  ✗ Table '%s': Missing indexes: %s",
                table_name, ', '.join(sorted(missing_idxs))
            )
        return False
    else:
        logger.info("✓ All tables have all expected indexes")

    logger.info("\n%s", "=" * 60)
    logger.info("✓ VERIFICATION PASSED - All migrations applied successfully")
    logger.info("%s", "=" * 60)
    return verification_passed


def main():
    """Run database migrations."""
    try:
        logger.info("%s", "=" * 60)
        logger.info("Database Migration Script")
        logger.info("%s", "=" * 60)

        logger.info("Importing database configuration...")

        # Ensure all models are registered before proceeding
        if not ensure_models_registered(Base):
            logger.error("Failed to verify model registration - cannot proceed")
            return 1

        # STEP 1: CHECK - Current status
        _, _, _ = check_status(engine, Base)

        # STEP 2: ACT - Run migrations
        logger.info("\n%s", "=" * 60)
        logger.info("STEP 2: ACT - Running Migrations")
        logger.info("%s", "=" * 60)

        result = run_migrations()

        if not result:
            logger.error("\n✗ Migrations encountered errors")
            logger.error(
                "The run_migrations() function returned False, indicating "
                "that some migrations failed. Check the logs above for details."
            )
            # Still run verification to see what's missing
            logger.info(
                "\nRunning verification anyway to see current state..."
            )
        else:
            logger.info("\n✓ Migrations completed successfully")

        # STEP 3: VERIFY - Confirm results
        # Refresh expected_tables from Base.metadata (shouldn't change, but be safe)
        expected_tables_after = set(Base.metadata.tables.keys())

        verification_passed = verify_results(engine, Base, expected_tables_after)

        if verification_passed and result:
            logger.info("\n%s", "=" * 60)
            logger.info("✓ ALL CHECKS PASSED - Migration completed successfully")
            logger.info("%s", "=" * 60)
            return 0
        else:
            logger.error("\n%s", "=" * 60)
            logger.error("✗ MIGRATION FAILED OR VERIFICATION FAILED")
            logger.error("%s", "=" * 60)
            if not result:
                logger.error("Migration function returned False")
            if not verification_passed:
                logger.error("Verification failed - see details above")
            return 1

    except ImportError as e:
        logger.error("Import error: %s", e, exc_info=True)
        logger.error("\nMake sure you're running this from the project root")
        logger.error("and that all dependencies are installed.")
        return 1
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
