"""
Manually create the library_bookmarks table.

This script ensures the LibraryBookmark model is registered and creates the table.
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
    format='[%(asctime)s] %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

try:
    # Import database configuration
    from config.database import engine, Base
    from sqlalchemy import inspect

    # Import LibraryBookmark to ensure it's registered
    from models.domain.library import LibraryBookmark

    logger.info("LibraryBookmark model imported successfully")
    logger.info("Table name: %s", LibraryBookmark.__tablename__)

    # Check if table is registered in metadata
    if LibraryBookmark.__tablename__ in Base.metadata.tables:
        logger.info("Table '%s' is registered in Base.metadata", LibraryBookmark.__tablename__)
    else:
        logger.error("Table '%s' is NOT registered in Base.metadata", LibraryBookmark.__tablename__)
        logger.info("Available tables in metadata: %s", list(Base.metadata.tables.keys()))
        sys.exit(1)

    # Check current database state
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    logger.info("Existing tables in database: %s", sorted(existing_tables))

    if LibraryBookmark.__tablename__ in existing_tables:
        logger.info("Table '%s' already exists in database", LibraryBookmark.__tablename__)
    else:
        logger.info("Table '%s' does not exist, creating it...", LibraryBookmark.__tablename__)

        # Create the table
        try:
            Base.metadata.create_all(
                bind=engine,
                tables=[Base.metadata.tables[LibraryBookmark.__tablename__]],
                checkfirst=True
            )
            logger.info("Table '%s' created successfully", LibraryBookmark.__tablename__)
        except Exception as e:
            logger.error("Failed to create table: %s", e, exc_info=True)
            sys.exit(1)

    # Verify table was created
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if LibraryBookmark.__tablename__ in existing_tables:
        logger.info("✓ Table creation verified successfully")

        # Show table structure
        columns = inspector.get_columns(LibraryBookmark.__tablename__)
        logger.info("Table '%s' has %d columns:", LibraryBookmark.__tablename__, len(columns))
        for col in columns:
            logger.info("  - %s: %s", col['name'], col['type'])
    else:
        logger.error("Table was not created!")
        sys.exit(1)

except ImportError as e:
    logger.error("Import error: %s", e, exc_info=True)
    sys.exit(1)
except Exception as e:
    logger.error("Unexpected error: %s", e, exc_info=True)
    sys.exit(1)
