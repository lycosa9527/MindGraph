"""
Automated Database Backup Scheduler for MindGraph
==================================================

Automatic daily backup of SQLite database with configurable retention.
Integrates with the FastAPI lifespan to run as a background task.

Features:
- Daily automatic backups (configurable time)
- Rotation: keeps only N most recent backups (default: 2)
- Uses SQLite backup API for safe WAL-mode backups
- Can run while application is serving requests
- No external dependencies (no Litestream, no rsync)

Usage:
    This module is automatically started by main.py lifespan.
    Configure via environment variables:
    - BACKUP_ENABLED=true (default: true)
    - BACKUP_HOUR=3 (default: 3 = 3:00 AM)
    - BACKUP_RETENTION_COUNT=2 (default: 2 = keep 2 most recent backups)
    - BACKUP_DIR=backup (default: backup/)

Author: MindSpring Team
"""

import os
import asyncio
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# Lock to prevent concurrent backup operations
# This ensures only one backup runs at a time, preventing race conditions
_backup_lock = asyncio.Lock()

# Thread-safe flag to coordinate with WAL checkpoint scheduler
# When backup is running, WAL checkpoint should skip (backup API handles WAL correctly)
_backup_in_progress = threading.Event()

# Configuration from environment with validation
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"

# Validate BACKUP_HOUR (0-23)
_backup_hour_raw = int(os.getenv("BACKUP_HOUR", "3"))
BACKUP_HOUR = max(0, min(23, _backup_hour_raw))  # Clamp to valid range

# Validate BACKUP_RETENTION_COUNT (minimum 1)
_retention_raw = int(os.getenv("BACKUP_RETENTION_COUNT", "2"))
BACKUP_RETENTION_COUNT = max(1, _retention_raw)  # Keep at least 1 backup

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backup"))


def is_backup_in_progress() -> bool:
    """
    Check if a backup operation is currently in progress.
    
    This is used by WAL checkpoint scheduler to skip checkpointing during backup,
    since SQLite backup API handles WAL mode correctly on its own.
    
    Returns:
        True if backup is running, False otherwise
    """
    return _backup_in_progress.is_set()


def get_database_path() -> Optional[Path]:
    """
    Get the database file path from configuration.
    
    Returns:
        Path to database file, or None if not SQLite
    """
    try:
        from config.database import DATABASE_URL
        
        if "sqlite" not in DATABASE_URL:
            return None
        
        # Extract file path from SQLite URL
        if DATABASE_URL.startswith("sqlite:////"):
            # Absolute path (4 slashes)
            db_path = DATABASE_URL.replace("sqlite:////", "/")
        elif DATABASE_URL.startswith("sqlite:///"):
            # Relative path (3 slashes)
            db_path = DATABASE_URL.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            if not os.path.isabs(db_path):
                db_path = str(Path.cwd() / db_path)
        else:
            db_path = DATABASE_URL.replace("sqlite:///", "")
        
        return Path(db_path).resolve()
    except Exception as e:
        logger.error(f"[Backup] Failed to get database path: {e}")
        return None


def _cleanup_partial_backup(backup_path: Path) -> None:
    """
    Clean up partial/failed backup file.
    
    Args:
        backup_path: Path to backup file to remove
    """
    try:
        if backup_path and backup_path.exists():
            backup_path.unlink()
            logger.debug(f"[Backup] Cleaned up partial backup: {backup_path.name}")
    except (OSError, PermissionError) as e:
        logger.warning(f"[Backup] Could not clean up partial backup: {e}")


def _check_disk_space(backup_dir: Path, required_mb: int = 100) -> bool:
    """
    Check if there's enough disk space for backup.
    
    Args:
        backup_dir: Directory where backup will be created
        required_mb: Minimum required disk space in MB
        
    Returns:
        True if enough space available, False otherwise
    """
    try:
        # Unix/Linux disk space check
        stat = os.statvfs(backup_dir)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        if free_mb < required_mb:
            logger.warning(f"[Backup] Low disk space: {free_mb:.1f} MB free, {required_mb} MB required")
            return False
        return True
    except AttributeError:
        # Windows doesn't have statvfs, assume OK
        return True
    except Exception as e:
        logger.warning(f"[Backup] Disk space check failed: {e}")
        return True  # Assume OK if check fails


def backup_database_safely(source_db: Path, backup_db: Path) -> bool:
    """
    Safely backup SQLite database using SQLite's backup API.
    Handles WAL mode correctly and safely even during active WAL operations.
    
    RACE CONDITION SAFETY:
    This function safely handles the critical scenario where:
    - WAL checkpoint scheduler is running (every 5 minutes)
    - WAL files are actively being flushed/written
    - Multiple connections are writing to the database
    
    HOW IT WORKS:
    SQLite backup API is specifically designed for WAL mode:
    1. Reads main database file AND WAL file atomically
    2. Creates consistent snapshot even if WAL is being written to
    3. Coordinates internally with WAL checkpoint operations
    4. No manual checkpoint needed - SQLite handles it
    
    COORDINATION:
    - Signals backup-in-progress flag (WAL checkpoint scheduler checks this)
    - WAL checkpoint scheduler skips checkpoint during backup (optimization)
    - Backup API works correctly even if checkpoint runs simultaneously
    
    KEY INSIGHT: SQLite backup API handles WAL mode correctly on its own.
    We don't need to manually checkpoint - doing so is redundant and could
    interfere with active transactions.
    
    Args:
        source_db: Path to source database file
        backup_db: Path to backup database file
        
    Returns:
        True if backup succeeded, False otherwise
    """
    source_conn = None
    backup_conn = None
    
    if not source_db.exists():
        logger.error(f"[Backup] Source database does not exist: {source_db}")
        return False
    
    try:
        # Connect to source database
        source_conn = sqlite3.connect(str(source_db), timeout=60.0)
        
        # Verify source database is accessible
        source_conn.execute("SELECT 1").fetchone()
        
        # CRITICAL: Coordinate with WAL checkpoint scheduler
        # 
        # IMPORTANT INSIGHT: SQLite backup API handles WAL mode correctly on its own!
        # - It reads both main database file AND WAL file atomically
        # - Creates a consistent snapshot even if WAL is being written to
        # - Works correctly even if WAL checkpoint happens during backup
        # - No manual checkpoint needed before backup
        #
        # We signal that backup is in progress so WAL checkpoint scheduler can skip
        # (optional optimization - backup API works fine even if checkpoint runs)
        _backup_in_progress.set()
        
        # Ensure backup directory exists
        backup_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing backup file and any WAL/SHM files if they exist
        if backup_db.exists():
            backup_db.unlink()
        # Clean up any existing WAL/SHM files from previous failed backups
        for suffix in ["-wal", "-shm"]:
            wal_file = backup_db.parent / f"{backup_db.name}{suffix}"
            if wal_file.exists():
                try:
                    wal_file.unlink()
                    logger.debug(f"[Backup] Removed existing {wal_file.name}")
                except (OSError, PermissionError):
                    pass
        
        # Connect to backup database
        # CRITICAL: Set journal_mode IMMEDIATELY after connection to prevent WAL file creation
        backup_conn = sqlite3.connect(str(backup_db), timeout=60.0)
        
        # Disable WAL mode for backup file (backups are standalone snapshots, don't need WAL)
        # This MUST be done immediately after connection, before any operations
        # This prevents SQLite from creating -wal and -shm files in the backup folder
        journal_mode_set = False
        try:
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA journal_mode=DELETE")
            result = cursor.fetchone()
            # PRAGMA journal_mode returns the new mode, should be "delete"
            if result and result[0].upper() == "DELETE":
                journal_mode_set = True
                logger.debug("[Backup] Successfully set backup journal_mode to DELETE")
            else:
                logger.warning(f"[Backup] Failed to set journal_mode to DELETE, got: {result[0] if result else 'None'}")
            cursor.close()
        except sqlite3.OperationalError as e:
            # If PRAGMA fails, this is a problem - we can't guarantee standalone backup
            logger.error(f"[Backup] CRITICAL: Could not set journal_mode to DELETE: {e}")
            logger.error("[Backup] Backup file may have WAL mode enabled - this is not desired")
            # We'll still try to clean up WAL/SHM files in finally block
        
        # Use SQLite backup API - handles WAL mode correctly
        # The backup API creates a consistent snapshot atomically, even if:
        # - WAL checkpoint happens during backup (it coordinates internally)
        # - WAL files are actively being flushed
        # - Other connections are writing to WAL
        # - Periodic checkpoint scheduler runs simultaneously
        # 
        # This is the SAFE and CORRECT way to backup WAL-mode databases.
        # No manual checkpoint needed - SQLite handles it internally.
        if hasattr(source_conn, 'backup'):
            # Python 3.7+ backup API
            # This API internally:
            # 1. Reads main database file
            # 2. Reads WAL file atomically
            # 3. Creates consistent snapshot
            # 4. Handles concurrent operations safely
            source_conn.backup(backup_conn)
        else:
            # Fallback: dump/restore method
            for line in source_conn.iterdump():
                backup_conn.executescript(line)
            backup_conn.commit()
        
        # CRITICAL: Close backup connection BEFORE checking for WAL/SHM files
        # SQLite may create WAL files when connection is open, but should clean them up on close
        # if journal_mode is DELETE
        if backup_conn:
            try:
                backup_conn.close()
                backup_conn = None  # Mark as closed
            except Exception:
                pass
        
        # Verify backup file exists and is not empty
        if not backup_db.exists() or backup_db.stat().st_size == 0:
            logger.error("[Backup] Backup file was not created or is empty")
            return False
        
        # CRITICAL: Verify backup is standalone (no WAL/SHM files)
        # This ensures we have a clean, standalone backup file
        wal_files_exist = False
        for suffix in ["-wal", "-shm"]:
            wal_file = backup_db.parent / f"{backup_db.name}{suffix}"
            if wal_file.exists():
                wal_files_exist = True
                logger.warning(f"[Backup] WARNING: {wal_file.name} exists - backup is not standalone!")
                try:
                    wal_file.unlink()
                    logger.info(f"[Backup] Removed {wal_file.name} to ensure standalone backup")
                except (OSError, PermissionError) as e:
                    logger.error(f"[Backup] Failed to remove {wal_file.name}: {e}")
                    return False  # Fail backup if we can't remove WAL files
        
        if wal_files_exist:
            logger.warning("[Backup] Backup had WAL/SHM files but they were cleaned up")
        
        # Verify journal_mode is DELETE by checking the backup file
        # Reconnect briefly to verify (read-only)
        verify_conn = None
        try:
            verify_conn = sqlite3.connect(str(backup_db), timeout=10.0)
            cursor = verify_conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            if result and result[0].upper() != "DELETE":
                logger.warning(f"[Backup] Backup file journal_mode is {result[0]}, expected DELETE")
                # Try to fix it
                cursor.execute("PRAGMA journal_mode=DELETE")
                verify_conn.commit()
                logger.info("[Backup] Fixed backup file journal_mode to DELETE")
            cursor.close()
        except Exception as e:
            logger.debug(f"[Backup] Could not verify journal_mode: {e}")
        finally:
            if verify_conn:
                try:
                    verify_conn.close()
                except Exception:
                    pass
        
        return True
            
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        if "database is locked" in error_msg:
            logger.error(f"[Backup] Database is locked - another process may be using it: {e}")
        elif "disk i/o error" in error_msg:
            logger.error(f"[Backup] Disk I/O error - check disk health and space: {e}")
        elif "unable to open database" in error_msg:
            logger.error(f"[Backup] Cannot open database - check file permissions: {e}")
        else:
            logger.error(f"[Backup] SQLite operational error: {e}")
        _cleanup_partial_backup(backup_db)
        return False
    except sqlite3.DatabaseError as e:
        # Covers corruption, malformed database, etc.
        logger.error(f"[Backup] Database error (possibly corrupted): {e}")
        logger.error("[Backup] Consider running: python scripts/recover_database.py")
        _cleanup_partial_backup(backup_db)
        return False
    except PermissionError as e:
        logger.error(f"[Backup] Permission denied - check file/folder permissions: {e}")
        _cleanup_partial_backup(backup_db)
        return False
    except OSError as e:
        # Covers disk full, file system errors, etc.
        if e.errno == 28:  # ENOSPC - No space left on device
            logger.error(f"[Backup] Disk full - cannot create backup: {e}")
        else:
            logger.error(f"[Backup] OS error: {e}")
        _cleanup_partial_backup(backup_db)
        return False
    except Exception as e:
        logger.error(f"[Backup] Unexpected error: {e}", exc_info=True)
        _cleanup_partial_backup(backup_db)
        return False
    finally:
        # Clear backup-in-progress flag
        _backup_in_progress.clear()
        
        # Close connections
        if backup_conn:
            try:
                backup_conn.close()
            except Exception:
                pass
        if source_conn:
            try:
                source_conn.close()
            except Exception:
                pass
        
        # FINAL SAFEGUARD: Clean up any WAL/SHM files that might have been created
        # This is a safety net - we should have prevented their creation, but if they exist, remove them
        # This ensures backups are ALWAYS standalone .db files with no WAL/SHM files
        if backup_db.exists():
            for suffix in ["-wal", "-shm"]:
                wal_file = backup_db.parent / f"{backup_db.name}{suffix}"
                if wal_file.exists():
                    try:
                        wal_file.unlink()
                        logger.info(f"[Backup] Final cleanup: Removed {wal_file.name} to ensure standalone backup")
                    except (OSError, PermissionError) as e:
                        logger.warning(f"[Backup] Could not remove {wal_file.name}: {e}")
                        # Don't fail here - backup might still be valid, just log warning


def verify_backup(backup_path: Path) -> bool:
    """
    Verify backup database integrity.
    
    Args:
        backup_path: Path to backup database file
        
    Returns:
        True if backup is valid, False otherwise
    """
    if not backup_path.exists() or backup_path.stat().st_size == 0:
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(str(backup_path), timeout=30.0)
        cursor = conn.cursor()
        
        # Disable WAL mode for backup verification (backups are read-only snapshots)
        # This prevents SQLite from creating -wal and -shm files in the backup folder
        # Handle potential race condition: if file is being restored or accessed by another process
        try:
            cursor.execute("PRAGMA journal_mode=DELETE")
            result = cursor.fetchone()
            if result and result[0].upper() != "DELETE":
                logger.debug(f"[Backup] Verification: journal_mode is {result[0]}, expected DELETE")
        except sqlite3.OperationalError as e:
            # If PRAGMA fails (e.g., database locked), log and continue verification
            # The integrity check can still proceed
            logger.debug(f"[Backup] Could not set journal_mode during verification: {e}")
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        return result and result[0] == "ok"
    except Exception as e:
        logger.error(f"[Backup] Integrity check failed: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        
        # Clean up any WAL/SHM files that might have been created before we disabled WAL mode
        # These files are not needed for backup files (backups are standalone snapshots)
        for suffix in ["-wal", "-shm"]:
            wal_file = backup_path.parent / f"{backup_path.name}{suffix}"
            if wal_file.exists():
                try:
                    wal_file.unlink()
                    logger.debug(f"[Backup] Cleaned up {wal_file.name}")
                except (OSError, PermissionError):
                    pass  # Ignore cleanup errors


def verify_backup_is_standalone(backup_path: Path) -> Tuple[bool, List[str]]:
    """
    Verify that a backup file is standalone (no WAL/SHM files).
    
    Args:
        backup_path: Path to backup file
        
    Returns:
        tuple: (is_standalone, list_of_wal_files_found)
    """
    wal_files = []
    for suffix in ["-wal", "-shm"]:
        wal_file = backup_path.parent / f"{backup_path.name}{suffix}"
        if wal_file.exists():
            wal_files.append(str(wal_file))
    
    return len(wal_files) == 0, wal_files


def cleanup_old_backups(backup_dir: Path, keep_count: int) -> int:
    """
    Remove old backups, keeping only the N most recent files.
    
    Uses count-based retention (not time-based) to ensure we always
    have backups even if server was down for extended periods.
    
    Args:
        backup_dir: Directory containing backups
        keep_count: Number of backup files to keep
        
    Returns:
        Number of backups deleted
    """
    if not backup_dir.exists():
        return 0
    
    deleted_count = 0
    
    try:
        # Find all backup files and sort by modification time (newest first)
        backup_files = []
        for backup_file in backup_dir.glob("mindgraph.db.*"):
            if backup_file.is_file():
                try:
                    mtime = backup_file.stat().st_mtime
                    backup_files.append((mtime, backup_file))
                except (OSError, PermissionError):
                    continue
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[0], reverse=True)
        
        # Delete files beyond the keep_count
        for _, backup_file in backup_files[keep_count:]:
            try:
                backup_file.unlink()
                logger.info(f"[Backup] Deleted old backup: {backup_file.name}")
                deleted_count += 1
                
                # Also clean up any WAL/SHM files that might exist for this backup
                # (shouldn't exist with our fixes, but clean up legacy files)
                for suffix in ["-wal", "-shm"]:
                    wal_file = backup_file.parent / f"{backup_file.name}{suffix}"
                    if wal_file.exists():
                        try:
                            wal_file.unlink()
                            logger.debug(f"[Backup] Cleaned up {wal_file.name}")
                        except (OSError, PermissionError):
                            pass  # Ignore cleanup errors
            except (OSError, PermissionError) as e:
                logger.warning(f"[Backup] Could not delete {backup_file.name}: {e}")
    except Exception as e:
        logger.warning(f"[Backup] Cleanup error: {e}")
    
    return deleted_count


def create_backup() -> bool:
    """
    Create a timestamped backup of the database.
    
    Returns:
        True if backup succeeded, False otherwise
    """
    source_db = get_database_path()
    if source_db is None:
        logger.warning("[Backup] Not using SQLite database, skipping backup")
        return False
    
    if not source_db.exists():
        logger.error(f"[Backup] Database not found: {source_db}")
        return False
    
    # Check disk space before backup
    # Calculate required space: database size + 50MB buffer (for backup overhead and WAL checkpointing)
    try:
        db_size_mb = source_db.stat().st_size / (1024 * 1024)
        required_mb = max(100, int(db_size_mb) + 50)  # At least 100MB, or DB size + 50MB buffer
    except Exception:
        required_mb = 100  # Fallback to default if we can't get DB size
    
    if not _check_disk_space(BACKUP_DIR, required_mb=required_mb):
        logger.error(f"[Backup] Insufficient disk space (need {required_mb} MB), skipping backup")
        return False
    
    # Generate timestamped backup filename
    # Use microsecond precision to avoid collisions if multiple backups are triggered simultaneously
    # Even with lock protection, this ensures unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = BACKUP_DIR / f"mindgraph.db.{timestamp}"
    
    logger.info(f"[Backup] Starting backup: {source_db} -> {backup_path}")
    
    # Create backup
    if backup_database_safely(source_db, backup_path):
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"[Backup] Backup created: {backup_path.name} ({size_mb:.2f} MB)")
        
        # Verify integrity
        if verify_backup(backup_path):
            logger.info("[Backup] Integrity check passed")
        else:
            logger.warning("[Backup] Integrity check failed - backup may be corrupted")
        
        # CRITICAL: Verify backup is standalone (no WAL/SHM files)
        is_standalone, wal_files = verify_backup_is_standalone(backup_path)
        if not is_standalone:
            logger.error(f"[Backup] Backup is NOT standalone - found WAL/SHM files: {wal_files}")
            # Try to clean them up
            for wal_file in wal_files:
                try:
                    Path(wal_file).unlink()
                    logger.info(f"[Backup] Removed {wal_file}")
                except Exception as e:
                    logger.error(f"[Backup] Failed to remove {wal_file}: {e}")
            # Verify again
            is_standalone, _ = verify_backup_is_standalone(backup_path)
            if not is_standalone:
                logger.error("[Backup] Failed to create standalone backup - WAL/SHM files persist")
                return False
        else:
            logger.info("[Backup] Backup verified as standalone (no WAL/SHM files)")
        
        # Cleanup old backups (keep only N most recent)
        deleted = cleanup_old_backups(BACKUP_DIR, BACKUP_RETENTION_COUNT)
        if deleted > 0:
            logger.info(f"[Backup] Cleaned up {deleted} old backup(s)")
        
        return True
    else:
        logger.error("[Backup] Backup failed")
        return False


def get_next_backup_time() -> datetime:
    """
    Calculate the next scheduled backup time.
    
    Returns:
        datetime of next backup
    """
    now = datetime.now()
    next_backup = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
    
    # If we've already passed today's backup time, schedule for tomorrow
    if now >= next_backup:
        next_backup += timedelta(days=1)
    
    return next_backup


async def start_backup_scheduler():
    """
    Start the automatic backup scheduler.
    
    Runs daily at the configured hour (default: 3:00 AM).
    This function runs forever until cancelled.
    """
    if not BACKUP_ENABLED:
        logger.info("[Backup] Automatic backup is disabled (BACKUP_ENABLED=false)")
        return
    
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[Backup] Scheduler started")
    logger.info(f"[Backup] Configuration: daily at {BACKUP_HOUR:02d}:00, keep {BACKUP_RETENTION_COUNT} backups")
    logger.info(f"[Backup] Backup directory: {BACKUP_DIR.resolve()}")
    
    while True:
        try:
            # Calculate time until next backup
            next_backup = get_next_backup_time()
            wait_seconds = (next_backup - datetime.now()).total_seconds()
            
            logger.debug(f"[Backup] Next backup scheduled at {next_backup.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Wait until backup time
            await asyncio.sleep(wait_seconds)
            
            # Perform backup (with lock to prevent concurrent operations)
            logger.info("[Backup] Starting scheduled backup...")
            async with _backup_lock:
                logger.debug("[Backup] Acquired backup lock for scheduled backup...")
                try:
                    success = await asyncio.to_thread(create_backup)
                    if success:
                        logger.info("[Backup] Scheduled backup completed successfully")
                    else:
                        logger.error("[Backup] Scheduled backup failed")
                except Exception as e:
                    logger.error(f"[Backup] Scheduled backup failed with exception: {e}", exc_info=True)
                    success = False
                finally:
                    logger.debug("[Backup] Released backup lock")
            
            # Wait a bit to avoid running twice in the same minute
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            logger.info("[Backup] Scheduler stopped")
            break
        except Exception as e:
            logger.error(f"[Backup] Scheduler error: {e}", exc_info=True)
            # Wait before retrying
            await asyncio.sleep(300)  # 5 minutes


async def run_backup_now() -> bool:
    """
    Run a backup immediately (for manual trigger or API call).
    
    Uses a lock to prevent concurrent backup operations, which could cause:
    - Race conditions when setting journal_mode
    - Multiple backups accessing source database simultaneously
    - File conflicts if backups use same timestamp
    
    Returns:
        True if backup succeeded, False otherwise
    """
    logger.info("[Backup] Manual backup triggered")
    
    # Acquire lock to prevent concurrent backups
    # If another backup is running, wait for it to complete
    async with _backup_lock:
        logger.debug("[Backup] Acquired backup lock, starting backup...")
        try:
            result = await asyncio.to_thread(create_backup)
            return result
        except Exception as e:
            logger.error(f"[Backup] Backup failed with exception: {e}", exc_info=True)
            return False
        finally:
            logger.debug("[Backup] Released backup lock")


def get_backup_status() -> dict:
    """
    Get the current backup status and list of backups.
    
    Returns:
        dict with backup configuration and list of existing backups
    """
    backups = []
    
    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("mindgraph.db.*"), reverse=True):
            if backup_file.is_file():
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    
    return {
        "enabled": BACKUP_ENABLED,
        "schedule_hour": BACKUP_HOUR,
        "retention_count": BACKUP_RETENTION_COUNT,
        "backup_dir": str(BACKUP_DIR.resolve()),
        "next_backup": get_next_backup_time().isoformat() if BACKUP_ENABLED else None,
        "backups": backups
    }

