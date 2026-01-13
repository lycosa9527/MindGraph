#!/usr/bin/env python3
"""
Drop knowledge space tables to allow recreation with new schema.

This script drops document_chunks and child_chunks tables so they can be
recreated with the renamed meta_data column (instead of metadata which is
a SQLAlchemy reserved name).

Usage:
    python scripts/drop_knowledge_tables.py
    or
    python3 scripts/drop_knowledge_tables.py
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up environment before importing
os.environ.setdefault('PYTHONPATH', str(project_root))

try:
    import sqlite3
    USE_SQLITE_DIRECT = True
except ImportError:
    USE_SQLITE_DIRECT = False

try:
    from sqlalchemy import text, create_engine
    from config.database import DATABASE_URL
    USE_SQLALCHEMY = True
except ImportError:
    USE_SQLALCHEMY = False

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_db_path():
    """Extract database file path from DATABASE_URL."""
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./data/mindgraph.db')
    
    if db_url.startswith('sqlite:///'):
        # Remove sqlite:/// prefix
        path_str = db_url.replace('sqlite:///', '')
        # Handle relative paths
        if path_str.startswith('./'):
            path_str = path_str[2:]
        # Convert to absolute path
        if not os.path.isabs(path_str):
            return Path(project_root) / path_str
        return Path(path_str)
    return None


def drop_knowledge_tables():
    """Drop document_chunks and child_chunks tables."""
    db_path = get_db_path()
    
    if not db_path or not db_path.exists():
        logger.warning(f"Database file not found at {db_path}")
        logger.info("No tables to drop - database will be created on first run")
        return True
    
    logger.info(f"Connecting to database: {db_path}")
    
    # Use direct SQLite connection (simpler and doesn't require SQLAlchemy imports)
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check which tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('document_chunks', 'child_chunks')
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if not existing_tables:
            logger.info("No knowledge space tables found to drop")
            conn.close()
            return True
        
        logger.info(f"Found {len(existing_tables)} table(s) to drop: {', '.join(existing_tables)}")
        
        # Drop tables (in reverse dependency order)
        # child_chunks depends on document_chunks, so drop child_chunks first
        for table in ['child_chunks', 'document_chunks']:
            if table in existing_tables:
                logger.info(f"Dropping table: {table}")
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Successfully dropped table: {table}")
        
        conn.commit()
        conn.close()
        
        logger.info("Knowledge space tables dropped successfully")
        logger.info("Tables will be recreated automatically on next server start with new schema")
        return True
        
    except Exception as e:
        logger.error(f"Error dropping tables: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("Starting knowledge space table drop...")
    success = drop_knowledge_tables()
    if success:
        logger.info("Done!")
        sys.exit(0)
    else:
        logger.error("Failed to drop tables")
        sys.exit(1)
