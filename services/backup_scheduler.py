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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration from environment with validation
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"

# Validate BACKUP_HOUR (0-23)
_backup_hour_raw = int(os.getenv("BACKUP_HOUR", "3"))
BACKUP_HOUR = max(0, min(23, _backup_hour_raw))  # Clamp to valid range

# Validate BACKUP_RETENTION_COUNT (minimum 1)
_retention_raw = int(os.getenv("BACKUP_RETENTION_COUNT", "2"))
BACKUP_RETENTION_COUNT = max(1, _retention_raw)  # Keep at least 1 backup

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backup"))


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
    Handles WAL mode correctly by automatically checkpointing.
    
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
        
        # Ensure backup directory exists
        backup_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing backup file if it exists
        if backup_db.exists():
            backup_db.unlink()
        
        # Connect to backup database
        backup_conn = sqlite3.connect(str(backup_db), timeout=60.0)
        
        # Use SQLite backup API - handles WAL mode correctly
        if hasattr(source_conn, 'backup'):
            # Python 3.7+ backup API
            source_conn.backup(backup_conn)
        else:
            # Fallback: dump/restore method
            for line in source_conn.iterdump():
                backup_conn.executescript(line)
            backup_conn.commit()
        
        # Verify backup
        if backup_db.exists() and backup_db.stat().st_size > 0:
            return True
        else:
            logger.error("[Backup] Backup file was not created or is empty")
            return False
            
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
    if not _check_disk_space(BACKUP_DIR, required_mb=100):
        logger.error("[Backup] Insufficient disk space, skipping backup")
        return False
    
    # Generate timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
            
            # Perform backup
            logger.info("[Backup] Starting scheduled backup...")
            success = await asyncio.to_thread(create_backup)
            
            if success:
                logger.info("[Backup] Scheduled backup completed successfully")
            else:
                logger.error("[Backup] Scheduled backup failed")
            
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
    
    Returns:
        True if backup succeeded, False otherwise
    """
    logger.info("[Backup] Manual backup triggered")
    return await asyncio.to_thread(create_backup)


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

