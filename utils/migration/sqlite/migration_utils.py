"""
SQLite Migration Utility Functions

Utility functions for SQLite to PostgreSQL migration:
- Database path detection
- Migration progress tracking
- Lock management
- PostgreSQL empty check

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import json
import logging
import sys
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import fcntl
    FCNTL_AVAILABLE = True
except ImportError:
    FCNTL_AVAILABLE = False

from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger(__name__)

# Calculate project root
# File structure: MindGraph/utils/migration/sqlite/migration_utils.py
# So: __file__.parent.parent.parent.parent = MindGraph/ (project root)
_project_root = Path(__file__).parent.parent.parent.parent

# Migration marker file (relative to project root)
MIGRATION_MARKER_FILE = _project_root / "backup" / ".migration_completed"
BACKUP_DIR = _project_root / "backup"
MIGRATION_LOCK_FILE = _project_root / "backup" / ".migration.lock"
MIGRATION_PROGRESS_FILE = _project_root / "backup" / ".migration_progress.json"


def get_sqlite_db_path() -> Optional[Path]:
    """
    Get SQLite database file path from SQLITE_DB_PATH env var, DATABASE_URL, or common locations.

    Returns:
        Path to SQLite database file, or None if not found
    """
    # Check for explicit SQLite path override first
    sqlite_path_override = os.getenv('SQLITE_DB_PATH')
    if sqlite_path_override:
        db_path = Path(sqlite_path_override)
        try:
            if db_path.exists():
                return db_path.resolve()
        except PermissionError:
            logger.debug("[Migration] Permission denied checking SQLITE_DB_PATH: %s", db_path)
        return None

    db_url = os.getenv('DATABASE_URL', '')

    # Check if using SQLite in DATABASE_URL
    if 'sqlite' in db_url.lower():
        # Extract file path from SQLite URL
        if db_url.startswith("sqlite:////"):
            # Absolute path (4 slashes)
            db_path = Path(db_url.replace("sqlite:////", "/"))
        elif db_url.startswith("sqlite:///"):
            # Relative path (3 slashes)
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]
            if not os.path.isabs(db_path_str):
                # Use project root as base for relative paths
                db_path = _project_root / db_path_str
            else:
                db_path = Path(db_path_str)
        else:
            db_path = Path(db_url.replace("sqlite:///", ""))

        try:
            if db_path.exists():
                return db_path.resolve()
        except PermissionError:
            logger.debug("[Migration] Permission denied checking DATABASE_URL path: %s", db_path)

    # If DATABASE_URL is PostgreSQL or not SQLite, check common default locations
    # This allows migration even when DATABASE_URL is already set to PostgreSQL
    common_locations = [
        _project_root / "data" / "mindgraph.db",  # New default location
        _project_root / "mindgraph.db",           # Old default location
        Path("/root/mindgraph/mindgraph.db"),     # Common server location
        Path("/root/mindgraph/data/mindgraph.db"), # Alternative server location
    ]

    # Also check WSL paths if running in WSL (Windows filesystem mounted at /mnt/c/)
    # Try to detect if we're in WSL and project might be on Windows filesystem
    cwd = Path.cwd()
    if str(cwd).startswith("/mnt/"):
        # We're in WSL, check Windows filesystem paths
        # Extract Windows path from WSL path: /mnt/c/Users/... -> C:/Users/...
        windows_path_parts = str(cwd).split("/")
        if len(windows_path_parts) >= 3 and windows_path_parts[1] == "mnt":
            # Reconstruct relative to current WSL directory
            common_locations.extend([
                Path("data/mindgraph.db"),  # Relative path should still work
            ])
    elif str(cwd).startswith("/home/"):
        # Native Linux path, check if there's a Windows mount
        # Try common Windows project locations via WSL mount
        if Path("/mnt/c/Users").exists():
            # Try to find project in Windows Users directory
            # This is a best-effort attempt
            pass

    for db_path in common_locations:
        try:
            if db_path.exists():
                logger.debug("[Migration] Found SQLite database at common location: %s", db_path)
                return db_path.resolve()
        except PermissionError:
            logger.debug("[Migration] Permission denied checking path: %s (skipping)", db_path)
            continue
        except Exception as e:
            logger.debug("[Migration] Error checking path %s: %s (skipping)", db_path, e)
            continue

    return None


def is_migration_completed() -> bool:
    """
    Check if migration has already been completed.

    Returns:
        True if migration marker exists, False otherwise
    """
    return MIGRATION_MARKER_FILE.exists()


def load_migration_progress() -> Dict[str, Any]:
    """
    Load migration progress from file.

    Returns:
        Dictionary with migration progress, or empty dict if no progress file
    """
    if not MIGRATION_PROGRESS_FILE.exists():
        return {}

    try:
        with open(MIGRATION_PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning("[Migration] Failed to load migration progress: %s", e)
        return {}


def save_migration_progress(progress: Dict[str, Any]) -> bool:
    """
    Save migration progress to file.

    Args:
        progress: Dictionary with migration progress

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        with open(MIGRATION_PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2)
        return True
    except Exception as e:
        logger.warning("[Migration] Failed to save migration progress: %s", e)
        return False


def clear_migration_progress() -> None:
    """
    Clear migration progress file (called after successful migration).
    """
    try:
        if MIGRATION_PROGRESS_FILE.exists():
            MIGRATION_PROGRESS_FILE.unlink()
            logger.debug("[Migration] Cleared migration progress file")
    except Exception as e:
        logger.debug("[Migration] Failed to clear migration progress: %s", e)


def acquire_migration_lock() -> Optional[Any]:
    """
    Acquire file-based lock to prevent concurrent migrations.

    Checks for stale lock files (process no longer running) and removes them.

    Returns:
        Lock file handle if successful, None if lock already held
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Check for stale lock file
        if MIGRATION_LOCK_FILE.exists():
            try:
                # Read PID from lock file
                with open(MIGRATION_LOCK_FILE, 'r', encoding='utf-8') as f:
                    pid_str = f.read().strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        # Check if process is still running
                        if sys.platform != 'win32':
                            # Unix: use kill(pid, 0) to check if process exists
                            try:
                                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                                # Process exists - lock is valid
                                logger.warning(
                                    "[Migration] Migration lock held by process %d (still running)",
                                    pid
                                )
                                return None
                            except ProcessLookupError:
                                # Process doesn't exist - stale lock
                                logger.warning(
                                    "[Migration] Removing stale migration lock (process %d not running)",
                                    pid
                                )
                                MIGRATION_LOCK_FILE.unlink()
                            except PermissionError:
                                # Permission denied - might be different user, assume valid
                                logger.warning(
                                    "[Migration] Cannot check lock file PID (permission denied), assuming valid"
                                )
                                return None
                        else:
                            # Windows: try to check if process exists
                            # This is a best-effort check
                            if PSUTIL_AVAILABLE:
                                if psutil.pid_exists(pid):
                                    logger.warning(
                                        "[Migration] Migration lock held by process %d (still running)",
                                        pid
                                    )
                                    return None
                                else:
                                    logger.warning(
                                        "[Migration] Removing stale migration lock (process %d not running)",
                                        pid
                                    )
                                    MIGRATION_LOCK_FILE.unlink()
                            else:
                                # psutil not available, skip stale check
                                logger.debug(
                                    "[Migration] psutil not available, skipping stale lock check"
                                )
                                if MIGRATION_LOCK_FILE.exists():
                                    logger.warning(
                                        "[Migration] Migration lock file exists - "
                                        "another migration may be in progress"
                                    )
                                    return None
            except Exception as e:
                logger.debug("[Migration] Error checking stale lock: %s", e)
                # If we can't check, assume lock is valid to be safe
                if MIGRATION_LOCK_FILE.exists():
                    logger.warning("[Migration] Migration lock file exists - another migration may be in progress")
                    return None

        # Try to create lock file
        lock_file = open(MIGRATION_LOCK_FILE, 'w', encoding='utf-8')

        # Try to acquire exclusive lock (non-blocking)
        if sys.platform != 'win32':
            if FCNTL_AVAILABLE:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Write PID to lock file for debugging
                    lock_file.write(str(os.getpid()))
                    lock_file.flush()
                    logger.debug("[Migration] Acquired migration lock (PID: %d)", os.getpid())
                    return lock_file
                except BlockingIOError:
                    lock_file.close()
                    logger.warning("[Migration] Migration lock already held by another process")
                    return None
            else:
                # fcntl is Unix-only, not available on Windows
                lock_file.close()
                logger.warning("[Migration] fcntl not available on this platform")
                return None
        else:
            # Windows: use simple file existence check
            # More sophisticated locking would require pywin32
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            logger.debug("[Migration] Acquired migration lock (PID: %d)", os.getpid())
            return lock_file

    except Exception as e:
        logger.warning("[Migration] Failed to acquire migration lock: %s", e)
        return None


def release_migration_lock(lock_file: Optional[Any]) -> None:
    """
    Release migration lock.

    Args:
        lock_file: Lock file handle returned by acquire_migration_lock()
    """
    if lock_file:
        try:
            if sys.platform != 'win32' and FCNTL_AVAILABLE:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            if MIGRATION_LOCK_FILE.exists():
                MIGRATION_LOCK_FILE.unlink()
            logger.debug("[Migration] Released migration lock")
        except Exception as e:
            logger.warning("[Migration] Failed to release migration lock: %s", e)


def check_table_completeness(
    sqlite_path: Optional[Path],
    pg_url: str,
    table_name: str,
    pg_engine: Optional[Any] = None,
    pg_inspector: Optional[Any] = None
) -> Tuple[bool, Optional[int], Optional[int]]:
    """
    Check if a PostgreSQL table has complete data by comparing row counts with SQLite.

    Args:
        sqlite_path: Path to SQLite database file
        pg_url: PostgreSQL connection URL (used only if pg_engine not provided)
        table_name: Name of the table to check
        pg_engine: Optional PostgreSQL engine to reuse (for performance)
        pg_inspector: Optional PostgreSQL inspector to reuse (for performance)

    Returns:
        Tuple of (is_complete, sqlite_count, postgresql_count)
        - is_complete: True if PostgreSQL has same or more rows as SQLite
        - sqlite_count: Row count in SQLite (None if table doesn't exist)
        - postgresql_count: Row count in PostgreSQL (None if table doesn't exist)
    """
    sqlite_count = None
    postgresql_count = None

    # Get SQLite row count
    if sqlite_path and sqlite_path.exists():
        try:
            sqlite_conn = sqlite3.connect(str(sqlite_path))
            cursor = sqlite_conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if cursor.fetchone():
                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                sqlite_count = cursor.fetchone()[0]
            sqlite_conn.close()
        except Exception as e:
            logger.debug("[Migration] Could not get SQLite count for %s: %s", table_name, e)

    # Get PostgreSQL row count (reuse engine if provided)
    try:
        if pg_engine is not None:
            # Reuse provided engine
            with pg_engine.connect() as conn:
                if pg_inspector is not None:
                    table_exists = table_name in pg_inspector.get_table_names()
                else:
                    inspector = inspect(pg_engine)
                    table_exists = table_name in inspector.get_table_names()

                if table_exists:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    postgresql_count = result.scalar()
        else:
            # Create new engine (fallback)
            engine = create_engine(pg_url)
            with engine.connect() as conn:
                inspector = inspect(engine)
                if table_name in inspector.get_table_names():
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    postgresql_count = result.scalar()
            engine.dispose()
    except Exception as e:
        logger.debug("[Migration] Could not get PostgreSQL count for %s: %s", table_name, e)

    # Determine completeness
    if sqlite_count is None:
        # Table doesn't exist in SQLite - consider PostgreSQL complete (nothing to migrate)
        return True, None, postgresql_count

    if postgresql_count is None:
        # Table doesn't exist in PostgreSQL - not complete
        return False, sqlite_count, None

    # Compare counts
    is_complete = postgresql_count >= sqlite_count
    return is_complete, sqlite_count, postgresql_count


def is_postgresql_empty(
    pg_url: str,
    force: bool = False,
    sqlite_path: Optional[Path] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if PostgreSQL database is empty or has incomplete data.

    If force=True, only checks for migration-specific tables to allow resume.
    If force=False, checks if tables exist but are empty or incomplete (allows resume of failed migrations).
    Compares row counts with SQLite to determine if data is complete.

    Args:
        pg_url: PostgreSQL connection URL
        force: If True, allow migration even if some tables exist (for resume)
        sqlite_path: Optional path to SQLite database for completeness comparison

    Returns:
        Tuple of (is_empty_or_allowed, error_message)
    """
    try:
        engine = create_engine(pg_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if len(tables) == 0:
            return True, None

        # Check if migration already completed
        # BUT: If SQLite still exists in original location, allow migration to sync and move it
        if is_migration_completed():
            # Check if SQLite was actually moved to backup
            sqlite_path_for_check = sqlite_path if sqlite_path else get_sqlite_db_path()

            # If SQLite still exists in original location, allow migration to sync and move it
            # This handles cases where migration completed but move failed, or SQLite was restored
            if sqlite_path_for_check:
                try:
                    if sqlite_path_for_check.exists():
                        # SQLite exists in original location - allow migration to sync and move
                        logger.warning(
                            "[Migration] Marker file exists but SQLite database still in original location: %s. "
                            "Allowing migration to sync data and move SQLite to backup.",
                            sqlite_path_for_check
                        )
                        # Don't return False - allow migration to proceed
                    else:
                        # SQLite doesn't exist in original location - migration truly complete
                        return False, "Migration already completed (marker file exists, SQLite moved)"
                except Exception:
                    # If we can't check, be conservative but still allow if SQLite path was provided
                    if sqlite_path:
                        logger.warning(
                            "[Migration] Marker file exists but cannot verify SQLite location. "
                            "Allowing migration to proceed (SQLite path provided)."
                        )
                    else:
                        return False, "Migration already completed (marker file exists)"
            else:
                # No SQLite path - migration truly complete
                return False, "Migration already completed (marker file exists)"

        if force:
            # In force mode, allow migration even if tables exist (for resume)
            logger.warning(
                "[Migration] Force mode: PostgreSQL has %d tables, proceeding anyway",
                len(tables)
            )
            return True, None

        # Get SQLite path if not provided
        if sqlite_path is None:
            sqlite_path = get_sqlite_db_path()

        # Normal mode: VERIFY completeness first if tables exist
        # Compare with SQLite to determine if data migration is needed
        try:
            user_tables = [t for t in tables if not (t.startswith('pg_') or t.startswith('sql_'))]

            if not user_tables:
                # Only system tables exist
                return True, None

            # Create engine and inspector once for reuse (needed for both empty check and completeness check)
            pg_engine = create_engine(pg_url)
            pg_inspector = inspect(pg_engine)

            # If SQLite database doesn't exist, check if PostgreSQL is truly empty
            if not sqlite_path or not sqlite_path.exists():
                logger.warning(
                    "[Migration] SQLite database not found at %s - checking if PostgreSQL is empty",
                    sqlite_path
                )
                # Check if all tables are empty (allow migration if PostgreSQL is empty)
                try:
                    with pg_engine.connect() as conn:
                        total_rows = 0
                        for table_name in user_tables:
                            result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                            row_count = result.scalar()
                            total_rows += row_count if row_count else 0

                        if total_rows == 0:
                            # PostgreSQL is empty - allow migration
                            logger.info(
                                "[Migration] PostgreSQL has %d tables but all are empty - allowing migration",
                                len(user_tables)
                            )
                            pg_engine.dispose()
                            return True, None
                        else:
                            # PostgreSQL has data but we can't verify completeness
                            pg_engine.dispose()
                            return False, (
                                f"PostgreSQL has {len(user_tables)} tables with {total_rows} total rows "
                                "but SQLite database not found. Cannot verify if data is complete. "
                                "Use --force flag to override."
                            )
                except Exception as check_error:
                    logger.warning(
                        "[Migration] Could not check if PostgreSQL is empty: %s. Blocking migration.",
                        check_error
                    )
                    pg_engine.dispose()
                    return False, (
                        f"PostgreSQL has {len(user_tables)} tables but SQLite database not found. "
                        "Cannot verify if data is complete. Use --force flag to override."
                    )

            # VERIFY completeness of each table by comparing with SQLite
            # Note: We allow incremental migration - if SQLite exists (even if backup has moved files),
            # we compare and migrate only missing data
            logger.info(
                "[Migration] Verifying completeness of %d existing table(s) by comparing with SQLite...",
                len(user_tables)
            )

            incomplete_tables = []
            complete_tables = []
            empty_tables = []
            tables_not_in_sqlite = []
            total_pg_rows = 0
            total_sqlite_rows = 0

            try:
                for table_name in user_tables:
                    is_complete, sqlite_count, pg_count = check_table_completeness(
                        sqlite_path, pg_url, table_name, pg_engine, pg_inspector
                    )

                    if sqlite_count is not None:
                        total_sqlite_rows += sqlite_count
                    if pg_count is not None:
                        total_pg_rows += pg_count

                    if sqlite_count is None:
                        # Table doesn't exist in SQLite - not relevant for migration
                        tables_not_in_sqlite.append(table_name)
                        logger.debug("[Migration] Table %s not in SQLite, skipping verification", table_name)
                        continue

                    # After continue, we know sqlite_count is not None
                    if pg_count is None:
                        # Table doesn't exist in PostgreSQL - incomplete
                        incomplete_tables.append(table_name)
                        logger.info(
                            "[Migration] Table %s missing in PostgreSQL (SQLite has %d rows)",
                            table_name, sqlite_count
                        )
                    elif pg_count == 0:
                        # Table exists but is empty - incomplete
                        empty_tables.append(table_name)
                        incomplete_tables.append(table_name)
                        logger.info(
                            "[Migration] Table %s is empty in PostgreSQL (SQLite has %d rows)",
                            table_name, sqlite_count
                        )
                    elif not is_complete:
                        # Table has fewer rows than SQLite - incomplete
                        incomplete_tables.append(table_name)
                        logger.info(
                            "[Migration] Table %s is incomplete: SQLite=%d rows, PostgreSQL=%d rows",
                            table_name, sqlite_count, pg_count
                        )
                    else:
                        # Table has complete data (same or more rows than SQLite)
                        complete_tables.append(table_name)
                        logger.info(
                            "[Migration] Table %s has complete data: SQLite=%d rows, PostgreSQL=%d rows",
                            table_name, sqlite_count, pg_count
                        )

                # Decision based on verification results
                if incomplete_tables:
                    # Some tables are incomplete - allow migration to resume
                    logger.info(
                        "[Migration] Verification complete: %d table(s) need migration: %s",
                        len(incomplete_tables),
                        ', '.join(incomplete_tables[:5]) + ('...' if len(incomplete_tables) > 5 else '')
                    )
                    if complete_tables:
                        logger.info(
                            "[Migration] %d table(s) already have complete data and will be skipped: %s",
                            len(complete_tables),
                            ', '.join(complete_tables[:5]) + ('...' if len(complete_tables) > 5 else '')
                        )
                    return True, None

                # All tables that exist in SQLite have complete data (by row count)
                # However, SQLite might have newer data (updated records) even if row counts match
                # Since we use timestamp-aware updates, it's safe to allow migration
                # The migration will only update records if SQLite has newer timestamps
                if complete_tables:
                    logger.info(
                        "[Migration] Verification complete: All %d table(s) have matching row counts "
                        "(PostgreSQL=%d rows, SQLite=%d rows). "
                        "However, SQLite may have newer data. Migration will proceed with timestamp-aware updates.",
                        len(complete_tables), total_pg_rows, total_sqlite_rows
                    )
                    # Allow migration to proceed - timestamp-aware updates will handle data freshness
                    # This ensures PostgreSQL gets the newest data even if row counts match
                    return True, None

                # All tables are empty
                if total_pg_rows == 0:
                    logger.info(
                        "[Migration] Verification complete: All %d tables are empty - allowing migration",
                        len(user_tables)
                    )
                    return True, None

                # Edge case: couldn't determine status
                return False, (
                    f"PostgreSQL database verification inconclusive "
                    f"({len(user_tables)} tables exist, {total_pg_rows} total rows). "
                    f"Use --force flag to override."
                )
            finally:
                # Clean up engine
                pg_engine.dispose()

        except Exception as check_error:
            # If we can't check row counts, be conservative and block
            logger.warning(
                "[Migration] Could not check table completeness: %s. Blocking migration.",
                check_error
            )
            return False, (
                f"PostgreSQL database is not empty ({len(tables)} tables exist) "
                "and could not verify table completeness. Use --force flag to override."
            )

    except Exception as e:
        logger.error("[Migration] Failed to check if PostgreSQL is empty: %s", e)
        return False, f"Failed to check PostgreSQL: {str(e)}"
