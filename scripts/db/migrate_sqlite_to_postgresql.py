"""
SQLite to PostgreSQL Data Migration Script

This script migrates all data from SQLite database to PostgreSQL database.
It can be run independently of the server startup process.

Usage:
    python scripts/db/migrate_sqlite_to_postgresql.py
    
    # With options:
    python scripts/db/migrate_sqlite_to_postgresql.py --force
    python scripts/db/migrate_sqlite_to_postgresql.py --verify-only
    python scripts/db/migrate_sqlite_to_postgresql.py --check-status

Options:
    --force              Force migration even if PostgreSQL is not empty (DANGEROUS)
    --verify-only        Only verify migration status without running migration
    --check-status       Check if migration is needed/completed
    --sqlite-path PATH   Specify custom SQLite database path
    --pg-url URL         Specify custom PostgreSQL connection URL

Examples:
    # Check migration status
    python scripts/db/migrate_sqlite_to_postgresql.py --check-status
    
    # Run migration
    python scripts/db/migrate_sqlite_to_postgresql.py
    
    # Verify existing migration
    python scripts/db/migrate_sqlite_to_postgresql.py --verify-only

Note: This script requires:
    - psycopg2-binary: pip install psycopg2-binary
    - SQLite database file (if migrating)
    - PostgreSQL database (empty or with --force flag)
    - DATABASE_URL environment variable set to PostgreSQL URL

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import argparse
import json
import logging
import sqlite3
import sys
import os
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ.setdefault('PYTHONPATH', str(project_root))

# Load .env file if it exists (before importing migration module)
try:
    from dotenv import load_dotenv
    from utils.env_utils import ensure_utf8_env_file

    # Ensure .env file is UTF-8 encoded before loading
    env_path = project_root / ".env"
    if env_path.exists():
        ensure_utf8_env_file(str(env_path))

    # Load environment variables from .env file
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not available, skip .env loading
    pass
except Exception as e:
    # If .env loading fails, continue anyway (might not exist)
    print(f"[WARNING] Could not load .env file: {e}")

# Set default PostgreSQL data directory for Ubuntu when running as root
# This avoids permission issues with /root/ directories
if sys.platform != 'win32':
    try:
        # Check if running as root
        IS_ROOT = os.geteuid() == 0 if hasattr(os, 'geteuid') else False

        # Check if POSTGRESQL_DATA_DIR is not already set
        if IS_ROOT and not os.getenv('POSTGRESQL_DATA_DIR'):
            # Check if we're on Ubuntu/Linux (not macOS)
            try:
                with open('/etc/os-release', 'r', encoding='utf-8') as os_file:
                    os_release = os_file.read()
                    if 'ubuntu' in os_release.lower() or 'debian' in os_release.lower():
                        # Use /var/lib/postgresql/mindgraph as default on Ubuntu/Debian
                        DEFAULT_PG_DIR = '/var/lib/postgresql/mindgraph'
                        os.environ['POSTGRESQL_DATA_DIR'] = DEFAULT_PG_DIR
                        print(f"[INFO] Running as root on Ubuntu - using PostgreSQL data directory: {DEFAULT_PG_DIR}")
                        print("[INFO] (Set POSTGRESQL_DATA_DIR environment variable to override)")
            except (FileNotFoundError, OSError, PermissionError):
                # Not Ubuntu/Debian or can't read /etc/os-release, skip
                pass
    except (AttributeError, OSError):
        # Windows or can't determine root status, skip
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

try:
    from utils.migration.sqlite_to_postgresql.data_migration import migrate_sqlite_to_postgresql
    from utils.migration.sqlite.migration_utils import (
        get_sqlite_db_path,
        is_migration_completed,
        is_postgresql_empty,
        MIGRATION_MARKER_FILE
    )
    from utils.migration.sqlite.migration_tables import verify_migration
except ImportError as e:
    print(f"[ERROR] Failed to import migration module: {e}")
    print("\nRequired dependencies:")
    print("  - psycopg2-binary: pip install psycopg2-binary")
    sys.exit(1)

# Import PostgreSQL startup functions
try:
    from services.infrastructure.utils.dependency_checker import check_postgresql_installed
    from services.infrastructure.process.process_manager import start_postgresql_server
    POSTGRESQL_STARTUP_AVAILABLE = True
except ImportError:
    POSTGRESQL_STARTUP_AVAILABLE = False
    logger.warning("[Migration] PostgreSQL startup functions not available - PostgreSQL must be started manually")


def ensure_postgresql_running() -> bool:
    """
    Ensure PostgreSQL is running, starting it if necessary.
    
    Returns:
        bool: True if PostgreSQL is running, False otherwise
    """
    if not POSTGRESQL_STARTUP_AVAILABLE:
        logger.warning("[Migration] Cannot start PostgreSQL automatically - please start it manually")
        return False

    # Check if PostgreSQL is installed
    is_installed, message = check_postgresql_installed()
    if not is_installed:
        print(f"[ERROR] PostgreSQL is not installed: {message}")
        print("\nPlease install PostgreSQL:")
        print("  - Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib")
        print("  - macOS: brew install postgresql")
        print("  - Or download from: https://www.postgresql.org/download/")
        return False

    print(f"[POSTGRESQL] {message}")

    # Try to start PostgreSQL (will return None if already running)
    print("[POSTGRESQL] Ensuring PostgreSQL is running...")
    try:
        process = start_postgresql_server()
        if process:
            print(f"[POSTGRESQL] ✓ PostgreSQL server started (PID: {process.pid})")
        else:
            print("[POSTGRESQL] ✓ PostgreSQL server is already running")
        return True
    except SystemExit:
        # start_postgresql_server() calls sys.exit(1) on failure
        print("[ERROR] Failed to start PostgreSQL server")
        print("        Please check PostgreSQL logs and ensure PostgreSQL can be started")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to start PostgreSQL: {e}")
        return False


def check_migration_status() -> None:
    """Check and display migration status."""
    print("=" * 80)
    print("SQLite to PostgreSQL Migration Status Check")
    print("=" * 80)
    print()

    # Check if migration already completed
    if is_migration_completed():
        print("✓ Migration already completed")
        if MIGRATION_MARKER_FILE.exists():
            try:
                with open(MIGRATION_MARKER_FILE, 'r', encoding='utf-8') as f:
                    marker_data = json.load(f)
                print(f"  Completed at: {marker_data.get('migration_completed_at', 'Unknown')}")
                if marker_data.get('backup_path'):
                    print(f"  Backup location: {marker_data['backup_path']}")
                stats = marker_data.get('statistics', {})
                if stats:
                    print(f"  Tables migrated: {stats.get('tables_migrated', 0)}")
                    print(f"  Total records: {stats.get('total_records', 0)}")
            except Exception as e:
                print(f"  (Could not read marker file details: {e})")
        print()
        return

    # Check SQLite database
    sqlite_path = get_sqlite_db_path()
    if sqlite_path and sqlite_path.exists():
        print(f"✓ SQLite database found: {sqlite_path}")
        print(f"  Size: {sqlite_path.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        print("✗ No SQLite database found")
        print("  Migration not needed (no SQLite data to migrate)")
        print()
        return

    # Ensure PostgreSQL is running
    if not ensure_postgresql_running():
        print("\n[ERROR] Cannot check migration status - PostgreSQL is not running")
        print("        Please start PostgreSQL manually or fix the startup issue")
        return

    # Check PostgreSQL - use defaults from env.example if not set
    pg_url = os.getenv('DATABASE_URL', '')

    # If DATABASE_URL not set, construct from individual PostgreSQL settings
    # Defaults match env.example values
    if not pg_url or 'postgresql' not in pg_url.lower():
        # Try to construct from individual PostgreSQL environment variables
        pg_user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
        pg_password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
        pg_host = os.getenv('POSTGRESQL_HOST', 'localhost')
        pg_port = os.getenv('POSTGRESQL_PORT', '5432')
        pg_database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

        # Construct PostgreSQL URL from components
        pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
        print("✓ PostgreSQL configured (using defaults from env.example)")
        print(f"  User: {pg_user}")
        print(f"  Host: {pg_host}:{pg_port}")
        print(f"  Database: {pg_database}")
    else:
        print("✓ PostgreSQL configured (from DATABASE_URL)")

    try:
        sqlite_path = get_sqlite_db_path()
        is_empty, empty_error = is_postgresql_empty(pg_url, sqlite_path=sqlite_path)
        if is_empty:
            print("  Database is empty - ready for migration")
        else:
            print("  Database is NOT empty - migration will be skipped")
            if empty_error:
                print(f"  Reason: {empty_error}")
            print("  Use --force flag to force migration (DANGEROUS)")
    except Exception as e:
        error_msg = str(e)
        if "password authentication failed" in error_msg.lower():
            print("  ⚠️  Authentication failed - PostgreSQL credentials don't match")
            print("  Options:")
            print("    1. Check your .env file for correct POSTGRESQL_USER and POSTGRESQL_PASSWORD")
            print("    2. Or PostgreSQL may need to be initialized (run 'python main.py' first)")
            print("    3. Or use --pg-url to specify correct connection string")
        elif "connection" in error_msg.lower() or "could not connect" in error_msg.lower():
            print("  ⚠️  Cannot connect to PostgreSQL")
            print("  Options:")
            print("    1. Ensure PostgreSQL is running")
            print("    2. Check POSTGRESQL_HOST and POSTGRESQL_PORT in .env")
            print("    3. Run 'python main.py' to start PostgreSQL subprocess")
        else:
            print(f"  Error checking PostgreSQL: {e}")

    print()
    print("Status: Migration can be run")
    print()


def verify_existing_migration() -> None:
    """Verify an existing migration by comparing record counts."""
    print("=" * 80)
    print("Verifying SQLite to PostgreSQL Migration")
    print("=" * 80)
    print()

    # Ensure PostgreSQL is running
    if not ensure_postgresql_running():
        print("\n[ERROR] Cannot verify migration - PostgreSQL is not running")
        print("        Please start PostgreSQL manually or fix the startup issue")
        sys.exit(1)

    sqlite_path = get_sqlite_db_path()
    if not sqlite_path or not sqlite_path.exists():
        print("[ERROR] SQLite database not found")
        sys.exit(1)

    # Get PostgreSQL URL - use defaults if not set
    pg_url = os.getenv('DATABASE_URL', '')

    # If DATABASE_URL not set, construct from individual PostgreSQL settings or use defaults
    if not pg_url or 'postgresql' not in pg_url.lower():
        # Try to construct from individual PostgreSQL environment variables
        pg_user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
        pg_password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
        pg_host = os.getenv('POSTGRESQL_HOST', 'localhost')
        pg_port = os.getenv('POSTGRESQL_PORT', '5432')
        pg_database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

        # Construct PostgreSQL URL from components
        pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"

    print(f"SQLite database: {sqlite_path}")
    print(f"PostgreSQL URL: {pg_url.split('@')[0]}@***" if '@' in pg_url else pg_url)
    print()

    try:
        is_valid, stats = verify_migration(sqlite_path, pg_url)
        print("Verification Results:")
        print(f"  Status: {'✓ PASSED' if is_valid else '✗ FAILED'}")
        print(f"  Tables verified: {stats.get('tables_migrated', 0)}")
        print(f"  Total records: {stats.get('total_records', 0)}")

        mismatches = stats.get('mismatches', [])
        if mismatches:
            print("\n  Mismatches found:")
            for mismatch in mismatches:
                if 'error' in mismatch:
                    print(f"    - {mismatch.get('table', 'unknown')}: {mismatch['error']}")
                else:
                    print(
                        f"    - {mismatch.get('table', 'unknown')}: "
                        f"SQLite={mismatch.get('sqlite_count', 0)}, "
                        f"PostgreSQL={mismatch.get('postgresql_count', 0)}"
                    )

        if is_valid:
            print("\n✓ Migration verification passed!")
        else:
            print("\n✗ Migration verification failed!")
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        logger.exception("Verification error")
        sys.exit(1)


def run_migration(force: bool = False, sqlite_path_override: Optional[str] = None,
                  pg_url_override: Optional[str] = None) -> None:
    """
    Run the SQLite to PostgreSQL migration.
    
    Args:
        force: If True, allow migration even if PostgreSQL has some tables (for resume)
        sqlite_path_override: Custom SQLite database path
        pg_url_override: Custom PostgreSQL connection URL
    """
    print("=" * 80)
    print("SQLite to PostgreSQL Data Migration")
    print("=" * 80)
    print()

    # Ensure PostgreSQL is running
    if not ensure_postgresql_running():
        print("\n[ERROR] Cannot run migration - PostgreSQL is not running")
        print("        Please start PostgreSQL manually or fix the startup issue")
        sys.exit(1)

    # Override environment variables if provided
    if sqlite_path_override:
        # Validate path exists
        sqlite_override_path = Path(sqlite_path_override)
        if not sqlite_override_path.exists():
            print(f"[ERROR] SQLite database not found at: {sqlite_path_override}")
            sys.exit(1)
        # Validate it's actually a SQLite database file
        try:
            test_conn = sqlite3.connect(str(sqlite_override_path))
            test_conn.execute("SELECT 1")
            test_conn.close()
        except sqlite3.DatabaseError as e:
            print(f"[ERROR] File at {sqlite_path_override} is not a valid SQLite database: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Could not validate SQLite database at {sqlite_path_override}: {e}")
            sys.exit(1)

        os.environ['SQLITE_DB_PATH'] = str(sqlite_override_path.resolve())
        print(f"[INFO] Using custom SQLite path: {os.environ['SQLITE_DB_PATH']}")

    if pg_url_override:
        os.environ['DATABASE_URL'] = pg_url_override
        masked_pg_url = (
            f"{pg_url_override.split('@')[0]}@***"
            if '@' in pg_url_override
            else pg_url_override
        )
        print(f"[INFO] Using custom PostgreSQL URL: {masked_pg_url}")

    # Check prerequisites
    sqlite_path = get_sqlite_db_path()
    if not sqlite_path or not sqlite_path.exists():
        print("[ERROR] SQLite database not found")
        if sqlite_path_override:
            print(f"  Specified path: {sqlite_path_override}")
        else:
            print("  Set SQLITE_DB_PATH environment variable or use --sqlite-path")
        sys.exit(1)

    # Validate SQLite database file format
    try:
        test_conn = sqlite3.connect(str(sqlite_path))
        test_conn.execute("SELECT 1")
        test_conn.close()
        logger.debug("[Migration] SQLite database validated successfully")
    except sqlite3.DatabaseError as e:
        print(f"[ERROR] File at {sqlite_path} is not a valid SQLite database: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Could not validate SQLite database at {sqlite_path}: {e}")
        sys.exit(1)

    # Get PostgreSQL URL - use defaults from env.example if not set
    pg_url = os.getenv('DATABASE_URL', '')

    # If DATABASE_URL not set or is SQLite, construct from individual PostgreSQL settings
    # Defaults match env.example values
    if not pg_url or 'postgresql' not in pg_url.lower():
        # Try to construct from individual PostgreSQL environment variables
        pg_user = os.getenv('POSTGRESQL_USER', 'mindgraph_user')
        pg_password = os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')
        pg_host = os.getenv('POSTGRESQL_HOST', 'localhost')
        pg_port = os.getenv('POSTGRESQL_PORT', '5432')
        pg_database = os.getenv('POSTGRESQL_DATABASE', 'mindgraph')

        # Construct PostgreSQL URL from components
        pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
        # Set DATABASE_URL in environment so migration function uses correct URL
        os.environ['DATABASE_URL'] = pg_url
        print(f"[INFO] Using PostgreSQL defaults from env.example: {pg_user}@{pg_host}:{pg_port}/{pg_database}")

    # Check if PostgreSQL is empty (unless forcing)
    if not force:
        try:
            sqlite_path = get_sqlite_db_path()
            is_empty, empty_error = is_postgresql_empty(pg_url, force=False, sqlite_path=sqlite_path)
            if not is_empty:
                print(f"[ERROR] PostgreSQL database is not empty: {empty_error}")
                print("  Migration will not proceed to prevent data loss.")
                print("  Use --force flag to override (DANGEROUS - will not delete existing data)")
                sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Failed to check PostgreSQL: {e}")
            sys.exit(1)

    print(f"SQLite database: {sqlite_path}")
    print(f"PostgreSQL URL: {pg_url.split('@')[0]}@***" if '@' in pg_url else pg_url)
    if force:
        print("⚠️  FORCE MODE: Migration will proceed even if PostgreSQL is not empty")
    print()

    # Run migration
    try:
        success, error, stats = migrate_sqlite_to_postgresql(force=force)
        if not success:
            print(f"[ERROR] Migration failed: {error}")
            sys.exit(1)

        if stats:
            print("\n" + "=" * 80)
            print("Migration Completed Successfully!")
            print("=" * 80)
            print(f"Tables migrated: {stats.get('tables_migrated', 0)}")
            print(f"Total records: {stats.get('total_records', 0)}")

            # Display warnings separately from errors (warnings are non-fatal)
            warnings = stats.get('warnings', [])
            if warnings:
                print(f"\n⚠️  Warnings ({len(warnings)}):")
                print("  (These are non-fatal - migration completed with partial issues)")
                for warning in warnings[:10]:  # Show first 10 warnings
                    print(f"  - {warning}")
                if len(warnings) > 10:
                    print(f"  ... and {len(warnings) - 10} more")

            # Display errors (these are failures)
            errors = stats.get('errors', [])
            if errors:
                print(f"\n❌ Errors ({len(errors)}):")
                print("  (These indicate failed table migrations)")
                for err in errors[:10]:  # Show first 10 errors
                    print(f"  - {err}")
                if len(errors) > 10:
                    print(f"  ... and {len(errors) - 10} more")

            verification = stats.get('verification', {})
            if verification:
                print("\nVerification:")
                print(f"  Tables verified: {verification.get('tables_migrated', 0)}")
                print(f"  Total records: {verification.get('total_records', 0)}")
                mismatches = verification.get('mismatches', [])
                if mismatches:
                    print(f"  ⚠️  Mismatches: {len(mismatches)}")
                    for mismatch in mismatches[:5]:
                        print(f"    - {mismatch.get('table', 'unknown')}")

            backup_path = stats.get('backup_path')
            if backup_path:
                print(f"\nBackup created: {backup_path}")
        else:
            print("\nMigration not needed (already completed or no SQLite database)")

        print("\n✓ Migration process completed")
        print()

    except Exception as e:
        print(f"[ERROR] Migration failed with exception: {e}")
        logger.exception("Migration error")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate data from SQLite to PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check if migration is needed
  python scripts/db/migrate_sqlite_to_postgresql.py --check-status
  
  # Run migration
  python scripts/db/migrate_sqlite_to_postgresql.py
  
  # Verify existing migration
  python scripts/db/migrate_sqlite_to_postgresql.py --verify-only
  
  # Force migration (dangerous)
  python scripts/db/migrate_sqlite_to_postgresql.py --force
        """
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force migration even if PostgreSQL is not empty (DANGEROUS)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify migration status without running migration'
    )
    parser.add_argument(
        '--check-status',
        action='store_true',
        help='Check if migration is needed/completed'
    )
    parser.add_argument(
        '--sqlite-path',
        type=str,
        help='Specify custom SQLite database path'
    )
    parser.add_argument(
        '--pg-url',
        type=str,
        help='Specify custom PostgreSQL connection URL'
    )

    args = parser.parse_args()

    # Handle different modes
    if args.check_status:
        check_migration_status()
    elif args.verify_only:
        verify_existing_migration()
    else:
        run_migration(
            force=args.force,
            sqlite_path_override=args.sqlite_path,
            pg_url_override=args.pg_url
        )


if __name__ == '__main__':
    main()
