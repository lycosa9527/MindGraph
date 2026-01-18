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
- Optional online backup to Tencent Cloud Object Storage (COS)

Usage:
    This module is automatically started by main.py lifespan.
    Configure via environment variables:
    - BACKUP_ENABLED=true (default: true)
    - BACKUP_HOUR=3 (default: 3 = 3:00 AM)
    - BACKUP_RETENTION_COUNT=2 (default: 2 = keep 2 most recent backups)
    - BACKUP_DIR=backup (default: backup/)
    - COS_BACKUP_ENABLED=false (default: false)
    - COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET, COS_REGION (required if COS enabled)

Author: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from config.database import DATABASE_URL
except ImportError:
    DATABASE_URL = ""

try:
    from qcloud_cos import CosConfig, CosS3Client
    from qcloud_cos.cos_exception import CosClientError, CosServiceError
except ImportError:
    CosConfig = None
    CosS3Client = None
    CosClientError = None
    CosServiceError = None

from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to run backup schedulers.
#
# Solution: Redis-based distributed lock ensures only ONE worker runs backups.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: backup:scheduler:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 10 minutes (auto-release if worker crashes)
# ============================================================================

BACKUP_LOCK_KEY = "backup:scheduler:lock"
BACKUP_LOCK_TTL = 600  # 10 minutes - plenty of time for backup, auto-release on crash
_worker_lock_id: Optional[str] = None  # This worker's unique lock identifier


def _generate_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


def acquire_backup_scheduler_lock() -> bool:
    """
    Attempt to acquire the backup scheduler lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    CRITICAL: Redis is REQUIRED. If Redis is unavailable, this function returns False
    to prevent duplicate backups. The application should not start without Redis.

    Returns:
        True if lock acquired (this worker should run scheduler)
        False if lock held by another worker or Redis unavailable
    """
    global _worker_lock_id

    if not is_redis_available():
        # Redis is REQUIRED for multi-worker coordination
        # Without Redis, we cannot guarantee only one worker runs backups
        logger.error(
            "[Backup] Redis unavailable - cannot coordinate backups across workers. "
            "Backup scheduler disabled."
        )
        return False

    redis = get_redis()
    if not redis:
        logger.error("[Backup] Redis client not available - cannot coordinate backups. Backup scheduler disabled.")
        return False

    try:
        # Generate unique ID for this worker
        if _worker_lock_id is None:
            _worker_lock_id = _generate_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            BACKUP_LOCK_KEY,
            _worker_lock_id,
            nx=True,  # Only set if not exists
            ex=BACKUP_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.info("[Backup] Lock acquired by this worker (id=%s)", _worker_lock_id)
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(BACKUP_LOCK_KEY)
            logger.debug(
                "[Backup] Another worker holds the scheduler lock (holder=%s), "
                "this worker will not run backups",
                holder
            )
            return False

    except Exception as e:
        # On Redis error, fail safe - do not allow backup to prevent duplicates
        logger.error(
            "[Backup] Lock acquisition failed: %s. Backup scheduler disabled to prevent duplicate backups.",
            e
        )
        return False


def release_backup_scheduler_lock() -> bool:
    """
    Release the backup scheduler lock if held by this worker.

    Uses Lua script for atomic check-and-delete to prevent
    accidentally releasing another worker's lock.

    Returns:
        True if lock released, False otherwise
    """

    if not is_redis_available() or _worker_lock_id is None:
        return True

    redis = get_redis()
    if not redis:
        return True

    try:
        # Atomic check-and-delete using Lua script
        # Only deletes if current holder matches our ID
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = redis.eval(lua_script, 1, BACKUP_LOCK_KEY, _worker_lock_id)

        if result == 1:
            logger.info("[Backup] Lock released by this worker (id=%s)", _worker_lock_id)

        return result == 1

    except Exception as e:
        logger.warning("[Backup] Lock release failed: %s", e)
        return False


def refresh_backup_scheduler_lock() -> bool:
    """
    Refresh the lock TTL if held by this worker.

    Uses atomic Lua script to check-and-refresh in one operation,
    preventing race conditions where lock could be lost between check and refresh.

    Returns:
        True if lock refreshed, False if not held by this worker
    """

    if not is_redis_available() or _worker_lock_id is None:
        # Redis unavailable - cannot verify lock, but this should not happen
        # in production since Redis is required
        logger.error("[Backup] Cannot refresh lock: Redis unavailable or lock ID not set")
        return False

    redis = get_redis()
    if not redis:
        logger.error("[Backup] Cannot refresh lock: Redis client not available")
        return False

    try:
        # Atomic check-and-refresh using Lua script
        # Only refreshes TTL if current holder matches our ID
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("expire", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """
        result = redis.eval(lua_script, 1, BACKUP_LOCK_KEY, _worker_lock_id, BACKUP_LOCK_TTL)

        if result == 1:
            logger.debug("[Backup] Lock refreshed (TTL=%ss)", BACKUP_LOCK_TTL)
            return True
        else:
            # Lock not held by us - check who holds it
            holder = redis.get(BACKUP_LOCK_KEY)
            logger.warning("[Backup] Lock lost! Holder: %s, our ID: %s", holder, _worker_lock_id)
            return False

    except Exception as e:
        logger.warning("[Backup] Lock refresh failed: %s", e)
        return False


def is_backup_lock_holder() -> bool:
    """
    Check if this worker currently holds the backup lock.

    CRITICAL: Redis is REQUIRED. Returns False if Redis unavailable to prevent
    duplicate backups when Redis coordination is not possible.

    Returns:
        True if this worker holds the lock
        False if lock held by another worker or Redis unavailable
    """

    if not is_redis_available() or _worker_lock_id is None:
        # Redis unavailable - cannot verify lock ownership
        logger.error("[Backup] Cannot verify lock ownership: Redis unavailable or lock ID not set")
        return False

    redis = get_redis()
    if not redis:
        logger.error("[Backup] Cannot verify lock ownership: Redis client not available")
        return False

    try:
        holder = redis.get(BACKUP_LOCK_KEY)
        return holder == _worker_lock_id
    except Exception as e:
        # On error, fail safe - do not assume we hold the lock
        logger.warning("[Backup] Error checking lock ownership: %s", e)
        return False

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

# COS (Tencent Cloud Object Storage) configuration
# Note: Uses same Tencent Cloud credentials as SMS module (TENCENT_SMS_SECRET_ID/SECRET_KEY)
COS_BACKUP_ENABLED = os.getenv("COS_BACKUP_ENABLED", "false").lower() == "true"
COS_SECRET_ID = os.getenv("TENCENT_SMS_SECRET_ID", "").strip()  # Reuse SMS credentials
COS_SECRET_KEY = os.getenv("TENCENT_SMS_SECRET_KEY", "").strip()  # Reuse SMS credentials
COS_BUCKET = os.getenv("COS_BUCKET", "")
COS_REGION = os.getenv("COS_REGION", "ap-beijing")
COS_KEY_PREFIX = os.getenv("COS_KEY_PREFIX", "backups/mindgraph")


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
        logger.error("[Backup] Failed to get database path: %s", e)
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
            logger.debug("[Backup] Cleaned up partial backup: %s", backup_path.name)
    except (OSError, PermissionError) as e:
        logger.warning("[Backup] Could not clean up partial backup: %s", e)


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
            logger.warning(
                "[Backup] Low disk space: %.1f MB free, %s MB required",
                free_mb,
                required_mb
            )
            return False
        return True
    except AttributeError:
        # Windows doesn't have statvfs, assume OK
        return True
    except Exception as e:
        logger.warning("[Backup] Disk space check failed: %s", e)
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
        logger.error("[Backup] Source database does not exist: %s", source_db)
        return False

    # Check file permissions before backup
    try:
        # Check if source database is readable
        if not os.access(source_db, os.R_OK):
            logger.error(
                "[Backup] Source database is not readable: %s. Check file permissions.",
                source_db
            )
            return False

        # Check if backup directory is writable
        backup_dir = backup_db.parent
        if not backup_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)

        if not os.access(backup_dir, os.W_OK):
            logger.error(
                "[Backup] Backup directory is not writable: %s. Check directory permissions.",
                backup_dir
            )
            return False

        # Check if backup file already exists and is writable (or can be overwritten)
        if backup_db.exists() and not os.access(backup_db, os.W_OK):
            logger.error(
                "[Backup] Backup file exists but is not writable: %s. Check file permissions.",
                backup_db
            )
            return False
    except OSError as e:
        logger.error("[Backup] Permission check failed: %s", e)
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
                    logger.debug("[Backup] Removed existing %s", wal_file.name)
                except (OSError, PermissionError):
                    pass

        # Connect to backup database
        # CRITICAL: Set journal_mode IMMEDIATELY after connection to prevent WAL file creation
        backup_conn = sqlite3.connect(str(backup_db), timeout=60.0)

        # Disable WAL mode for backup file (backups are standalone snapshots, don't need WAL)
        # This MUST be done immediately after connection, before any operations
        # This prevents SQLite from creating -wal and -shm files in the backup folder
        try:
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA journal_mode=DELETE")
            result = cursor.fetchone()
            # PRAGMA journal_mode returns the new mode, should be "delete"
            if result and result[0].upper() == "DELETE":
                logger.debug("[Backup] Successfully set backup journal_mode to DELETE")
            else:
                logger.warning(
                    "[Backup] Failed to set journal_mode to DELETE, got: %s",
                    result[0] if result else 'None'
                )
            cursor.close()
        except sqlite3.OperationalError as e:
            # If PRAGMA fails, this is a problem - we can't guarantee standalone backup
            logger.error("[Backup] CRITICAL: Could not set journal_mode to DELETE: %s", e)
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
                logger.warning("[Backup] WARNING: %s exists - backup is not standalone!", wal_file.name)
                try:
                    wal_file.unlink()
                    logger.info("[Backup] Removed %s to ensure standalone backup", wal_file.name)
                except (OSError, PermissionError) as e:
                    logger.error("[Backup] Failed to remove %s: %s", wal_file.name, e)
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
                logger.warning("[Backup] Backup file journal_mode is %s, expected DELETE", result[0])
                # Try to fix it
                cursor.execute("PRAGMA journal_mode=DELETE")
                verify_conn.commit()
                logger.info("[Backup] Fixed backup file journal_mode to DELETE")
            cursor.close()
        except Exception as e:
            logger.debug("[Backup] Could not verify journal_mode: %s", e)
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
            logger.error("[Backup] Database is locked - another process may be using it: %s", e)
        elif "disk i/o error" in error_msg:
            logger.error("[Backup] Disk I/O error - check disk health and space: %s", e)
        elif "unable to open database" in error_msg:
            logger.error("[Backup] Cannot open database - check file permissions: %s", e)
        else:
            logger.error("[Backup] SQLite operational error: %s", e)
        _cleanup_partial_backup(backup_db)
        return False
    except sqlite3.DatabaseError as e:
        # Covers corruption, malformed database, etc.
        logger.error("[Backup] Database error (possibly corrupted): %s", e)
        logger.error("[Backup] Consider running: python scripts/recover_database.py")
        _cleanup_partial_backup(backup_db)
        return False
    except PermissionError as e:
        logger.error("[Backup] Permission denied - check file/folder permissions: %s", e)
        _cleanup_partial_backup(backup_db)
        return False
    except OSError as e:
        # Covers disk full, file system errors, etc.
        if e.errno == 28:  # ENOSPC - No space left on device
            logger.error("[Backup] Disk full - cannot create backup: %s", e)
        else:
            logger.error("[Backup] OS error: %s", e)
        _cleanup_partial_backup(backup_db)
        return False
    except Exception as e:
        logger.error("[Backup] Unexpected error: %s", e, exc_info=True)
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
                        logger.info(
                            "[Backup] Final cleanup: Removed %s to ensure standalone backup",
                            wal_file.name
                        )
                    except (OSError, PermissionError) as e:
                        logger.warning("[Backup] Could not remove %s: %s", wal_file.name, e)
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
                logger.debug("[Backup] Verification: journal_mode is %s, expected DELETE", result[0])
        except sqlite3.OperationalError as e:
            # If PRAGMA fails (e.g., database locked), log and continue verification
            # The integrity check can still proceed
            logger.debug("[Backup] Could not set journal_mode during verification: %s", e)

        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()

        return result and result[0] == "ok"
    except Exception as e:
        logger.error("[Backup] Integrity check failed: %s", e)
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
                    logger.debug("[Backup] Cleaned up %s", wal_file.name)
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


def upload_backup_to_cos(backup_path: Path, max_retries: int = 3) -> bool:
    """
    Upload backup file to Tencent Cloud Object Storage (COS).

    This function uploads the backup file to COS after successful local backup.
    Uses the advanced upload interface which supports large files and resumable uploads.

    Based on COS SDK demo patterns:
    https://github.com/tencentyun/cos-python-sdk-v5/tree/master/demo

    Args:
        backup_path: Path to the backup file to upload

    Returns:
        True if upload succeeded, False otherwise
    """
    if not COS_BACKUP_ENABLED:
        logger.debug("[Backup] COS backup disabled, skipping upload")
        return True  # COS backup disabled, consider it successful

    # Validate backup file exists
    if not backup_path.exists():
        logger.error("[Backup] Backup file does not exist: %s", backup_path)
        return False

    # Validate COS configuration
    # Note: COS uses same Tencent Cloud credentials as SMS (TENCENT_SMS_SECRET_ID/SECRET_KEY)
    if not COS_SECRET_ID or not COS_SECRET_KEY:
        logger.warning(
            "[Backup] COS backup enabled but Tencent Cloud credentials not configured "
            "(TENCENT_SMS_SECRET_ID/SECRET_KEY), skipping upload"
        )
        return False

    if not COS_BUCKET:
        logger.warning(
            "[Backup] COS backup enabled but bucket not configured (COS_BUCKET), skipping upload"
        )
        return False

    if not COS_REGION:
        logger.warning(
            "[Backup] COS backup enabled but region not configured (COS_REGION), skipping upload"
        )
        return False

    # Get file information for logging and validation
    try:
        file_stat = backup_path.stat()
        file_size_mb = file_stat.st_size / (1024 * 1024)
        file_size_bytes = file_stat.st_size
    except (OSError, PermissionError) as e:
        logger.error("[Backup] Cannot access backup file %s: %s", backup_path, e)
        return False

    # Validate file is not empty
    if file_size_bytes == 0:
        logger.error("[Backup] Backup file is empty: %s", backup_path)
        return False

    # Construct object key with prefix (before try block for error handling)
    # Format: {COS_KEY_PREFIX}/mindgraph.db.{timestamp}
    # Normalize prefix (remove trailing slash) to avoid double slashes
    normalized_prefix = COS_KEY_PREFIX.rstrip('/')
    object_key = f"{normalized_prefix}/{backup_path.name}"

    # Remove leading slash if object_key starts with one (shouldn't happen, but safety check)
    if object_key.startswith('/'):
        object_key = object_key[1:]

    # Log configuration for debugging
    logger.debug(
        "[Backup] COS configuration: bucket=%s, region=%s, prefix=%s, object_key=%s",
        COS_BUCKET,
        COS_REGION,
        COS_KEY_PREFIX,
        object_key
    )

    if CosConfig is None or CosS3Client is None:
        logger.error(
            "[Backup] COS SDK not installed. Install with: pip install cos-python-sdk-v5",
            exc_info=True
        )
        return False

    try:
        # Initialize COS client
        # Following demo pattern: https://github.com/tencentyun/cos-python-sdk-v5/tree/master/demo
        logger.debug("[Backup] Initializing COS client for region: %s", COS_REGION)
        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
            Scheme='https'
        )
        client = CosS3Client(config)

        logger.info(
            "[Backup] Uploading to COS: bucket=%s, key=%s, size=%.2f MB, region=%s",
            COS_BUCKET,
            object_key,
            file_size_mb,
            COS_REGION
        )

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                # Use advanced upload interface (supports large files and resumable uploads)
                # Following demo pattern for large file uploads
                # PartSize=1 means 1MB per part (good for files up to 5GB)
                # MAXThread=10 means up to 10 concurrent upload threads
                # EnableMD5=False for faster upload (MD5 verification optional)
                response = client.upload_file(
                    Bucket=COS_BUCKET,
                    LocalFilePath=str(backup_path),
                    Key=object_key,
                    PartSize=1,  # 1MB per part
                    MAXThread=10,  # Up to 10 concurrent threads
                    EnableMD5=False  # Disable MD5 for faster upload
                )

                # Log upload result with details
                # Response contains ETag, Location, etc.
                if 'ETag' in response:
                    logger.info(
                        "[Backup] Successfully uploaded to COS: %s (ETag: %s, bucket: %s)",
                        object_key,
                        response['ETag'],
                        COS_BUCKET
                    )
                else:
                    logger.info("[Backup] Successfully uploaded to COS: %s (bucket: %s)", object_key, COS_BUCKET)

                return True

            except Exception as e:
                # Check if error is retryable
                # Only handle COS exceptions if SDK is available
                if CosClientError is None or CosServiceError is None:
                    raise
                if not isinstance(e, (CosClientError, CosServiceError)):
                    raise
                is_retryable = False
                # Type narrowing: after isinstance check, e is CosServiceError or CosClientError
                if CosServiceError is not None and isinstance(e, CosServiceError):
                    try:
                        # Type checker doesn't know CosServiceError methods, use hasattr checks
                        status_code = e.get_status_code() if hasattr(e, 'get_status_code') else None  # type: ignore
                        error_code = e.get_error_code() if hasattr(e, 'get_error_code') else None  # type: ignore
                        # Retry on 5xx errors and rate limits
                        if status_code and str(status_code).startswith('5'):
                            is_retryable = True
                        elif error_code in ('SlowDown', 'RequestLimitExceeded'):
                            is_retryable = True
                    except Exception:
                        pass
                else:
                    # Retry on client errors (network issues)
                    is_retryable = True

                if not is_retryable or attempt == max_retries - 1:
                    # Not retryable or last attempt - re-raise to be handled by outer exception handler
                    raise

                # Calculate delay with exponential backoff: 5s, 10s, 20s
                delay = min(5.0 * (2 ** attempt), 30.0)
                logger.warning(
                    "[Backup] COS upload attempt %s/%s failed: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries,
                    e,
                    delay
                )
                time.sleep(delay)
                continue

        # If we get here, all retries failed but exception was caught and handled
        # This should never happen, but satisfy type checker
        return False

    except (OSError, PermissionError) as e:
        # File system errors (permissions, disk errors, etc.)
        # Handle before general Exception to avoid unreachable code
        logger.error(
            "[Backup] File system error uploading %s to COS: %s",
            backup_path.name,
            e,
            exc_info=True
        )
        return False
    except Exception as e:
        # Client-side errors (network, configuration, etc.)
        if CosClientError is not None and isinstance(e, CosClientError):
            logger.error(
                "[Backup] COS client error uploading %s to %s/%s: %s",
                backup_path.name,
                COS_BUCKET,
                object_key,
                e,
                exc_info=True
            )
            return False
        # Server-side errors (permissions, bucket not found, etc.)
        if CosServiceError is not None and isinstance(e, CosServiceError):
            # Following official COS SDK exception handling pattern:
            # https://cloud.tencent.com/document/product/436/35154
            # Error codes reference: https://cloud.tencent.com/document/product/436/7730
            try:
                # Type checker doesn't know CosServiceError methods, use hasattr checks
                status_code = e.get_status_code() if hasattr(e, 'get_status_code') else 'Unknown'  # type: ignore
                error_code = e.get_error_code() if hasattr(e, 'get_error_code') else 'Unknown'  # type: ignore
                error_msg = e.get_error_msg() if hasattr(e, 'get_error_msg') else str(e)  # type: ignore
                request_id = e.get_request_id() if hasattr(e, 'get_request_id') else 'N/A'  # type: ignore
                trace_id = e.get_trace_id() if hasattr(e, 'get_trace_id') else 'N/A'  # type: ignore
                resource_location = e.get_resource_location() if hasattr(e, 'get_resource_location') else 'N/A'  # type: ignore
            except Exception:
                # Fallback if methods don't exist or fail
                status_code = 'Unknown'
                error_code = 'Unknown'
                error_msg = str(e)
                request_id = 'N/A'
                trace_id = 'N/A'
                resource_location = 'N/A'

            # Provide actionable error messages for common error codes
            # Reference: https://cloud.tencent.com/document/product/436/7730
            actionable_msg = ""
            if error_code == 'AccessDenied':
                actionable_msg = " - Check COS credentials and bucket permissions"
            elif error_code == 'NoSuchBucket':
                actionable_msg = " - Bucket '%s' does not exist or is inaccessible" % COS_BUCKET
            elif error_code == 'InvalidAccessKeyId':
                actionable_msg = " - Check TENCENT_SMS_SECRET_ID configuration"
            elif error_code == 'SignatureDoesNotMatch':
                actionable_msg = " - Check TENCENT_SMS_SECRET_KEY configuration"
            elif error_code == 'EntityTooLarge':
                actionable_msg = " - Backup file exceeds COS size limit (5GB for single upload)"
            elif error_code == 'SlowDown' or error_code == 'RequestLimitExceeded':
                actionable_msg = " - Rate limit exceeded, backup will retry on next schedule"
            elif status_code and str(status_code).startswith('5'):
                actionable_msg = " - Server error, may be transient - backup will retry on next schedule"

            # Log detailed error information
            logger.error(
                "[Backup] COS service error uploading %s to %s/%s: HTTP %s, Error %s - %s%s",
                backup_path.name,
                COS_BUCKET,
                object_key,
                status_code,
                error_code,
                error_msg,
                actionable_msg
            )
            logger.error(
                "[Backup] COS error details: RequestID=%s, TraceID=%s, Resource=%s",
                request_id,
                trace_id,
                resource_location
            )
            logger.debug("[Backup] COS service error full details", exc_info=True)
            return False
        # Unexpected errors
        logger.error(
            "[Backup] Unexpected error uploading %s to COS (bucket: %s, key: %s): %s",
            backup_path.name,
            COS_BUCKET,
            object_key,
            e,
            exc_info=True
        )
        return False


def list_cos_backups() -> List[dict]:
    """
    List all backup files in COS bucket with the configured prefix.

    Returns:
        List of dicts with backup information: {'key': str, 'size': int, 'last_modified': datetime}
        Returns empty list if COS is disabled or on error
    """
    if not COS_BACKUP_ENABLED:
        return []

    if not COS_SECRET_ID or not COS_SECRET_KEY or not COS_BUCKET:
        return []

    if CosConfig is None or CosS3Client is None:
        logger.debug("[Backup] COS SDK not installed, cannot list backups")
        return []

    try:
        # Initialize COS client
        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
            Scheme='https'
        )
        client = CosS3Client(config)

        # List objects with prefix
        # IMPORTANT: Only list backups with the configured prefix to prevent cross-environment access
        # This ensures dev machines (mindgraph-Test) and production (mindgraph-Master) don't mix backups
        backups = []
        marker = ""
        is_truncated = True

        logger.debug("[Backup] Listing COS backups with prefix: %s (bucket: %s)", COS_KEY_PREFIX, COS_BUCKET)

        # Normalize prefix (remove trailing slash for consistency)
        normalized_prefix = COS_KEY_PREFIX.rstrip('/')

        while is_truncated:
            response = client.list_objects(
                Bucket=COS_BUCKET,
                Prefix=normalized_prefix,
                Marker=marker
            )

            if 'Contents' in response:
                for obj in response['Contents']:
                    obj_key = obj['Key']

                    # Double-check: ensure key starts with our prefix (security)
                    if not obj_key.startswith(normalized_prefix):
                        logger.warning("[Backup] Skipping object with unexpected prefix: %s", obj_key)
                        continue

                    # Only include files matching backup pattern (mindgraph.db.*)
                    if 'mindgraph.db.' in obj_key:
                        backups.append({
                            'key': obj_key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })

            is_truncated = response.get('IsTruncated', 'false') == 'true'
            if is_truncated:
                marker = response.get('NextMarker', '')

        logger.debug("[Backup] Found %s backup(s) in COS", len(backups))
        return backups

    except Exception as e:
        if CosClientError is not None and isinstance(e, CosClientError):
            logger.error("[Backup] COS client error listing backups: %s", e, exc_info=True)
            return []
        if CosServiceError is not None and isinstance(e, CosServiceError):
            # Server-side errors - reference: https://cloud.tencent.com/document/product/436/7730
            try:
                # Type checker doesn't know CosServiceError methods, use hasattr checks
                status_code = e.get_status_code() if hasattr(e, 'get_status_code') else 'Unknown'  # type: ignore
                error_code = e.get_error_code() if hasattr(e, 'get_error_code') else 'Unknown'  # type: ignore
                error_msg = e.get_error_msg() if hasattr(e, 'get_error_msg') else str(e)  # type: ignore
                request_id = e.get_request_id() if hasattr(e, 'get_request_id') else 'N/A'  # type: ignore
            except Exception:
                status_code = 'Unknown'
                error_code = 'Unknown'
                error_msg = str(e)
                request_id = 'N/A'

            logger.error(
                "[Backup] COS service error listing backups: HTTP %s, Error %s - %s (RequestID: %s)",
                status_code,
                error_code,
                error_msg,
                request_id,
                exc_info=True
            )
            return []
        logger.error("[Backup] Unexpected error listing COS backups: %s", e, exc_info=True)
        return []


def cleanup_old_cos_backups(retention_days: int = 2) -> int:
    """
    Delete old backups from COS, keeping only backups from the last N days.

    Uses time-based retention (keeps backups from last N days).
    Deletes backups older than retention_days (e.g., if retention_days=2, deletes backups older than 2 days).

    Args:
        retention_days: Number of days to keep backups (default: 2)

    Returns:
        Number of backups deleted
    """
    if not COS_BACKUP_ENABLED:
        return 0

    if not COS_SECRET_ID or not COS_SECRET_KEY or not COS_BUCKET:
        return 0

    if CosConfig is None or CosS3Client is None:
        logger.debug("[Backup] COS SDK not installed, cannot cleanup backups")
        return 0

    try:
        # Initialize COS client
        config = CosConfig(
            Region=COS_REGION,
            SecretId=COS_SECRET_ID,
            SecretKey=COS_SECRET_KEY,
            Scheme='https'
        )
        client = CosS3Client(config)

        # Get all backups (already filtered by COS_KEY_PREFIX in list_cos_backups)
        backups = list_cos_backups()
        if not backups:
            logger.debug("[Backup] No COS backups found with prefix: %s", COS_KEY_PREFIX)
            return 0

        logger.debug("[Backup] Found %s COS backup(s) with prefix: %s", len(backups), COS_KEY_PREFIX)

        # Calculate cutoff time (backups older than this will be deleted)
        cutoff_time = datetime.now() - timedelta(days=retention_days)

        # Parse timestamps and filter old backups
        deleted_count = 0
        for backup in backups:
            try:
                # Parse LastModified timestamp
                # COS returns timestamps as strings in ISO format: "2023-05-23T15:41:30.000Z"
                last_modified_value = backup['last_modified']

                if isinstance(last_modified_value, datetime):
                    # Already a datetime object
                    last_modified = last_modified_value
                elif isinstance(last_modified_value, str):
                    # Parse string timestamp
                    # Remove 'Z' suffix if present and parse ISO format
                    timestamp_str = last_modified_value.replace('Z', '')
                    try:
                        # Try parsing with microseconds
                        if '.' in timestamp_str:
                            last_modified = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%f')
                        else:
                            last_modified = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        # Fallback: try fromisoformat
                        try:
                            last_modified = datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            logger.warning("[Backup] Cannot parse timestamp: %s", last_modified_value)
                            continue
                else:
                    logger.warning("[Backup] Unexpected timestamp type: %s", type(last_modified_value))
                    continue

                # Delete if older than retention period
                if last_modified < cutoff_time:
                    age_days = (datetime.now() - last_modified).days
                    logger.info(
                        "[Backup] Deleting old COS backup: %s (age: %s days)",
                        backup['key'],
                        age_days
                    )

                    try:
                        client.delete_object(
                            Bucket=COS_BUCKET,
                            Key=backup['key']
                        )
                        deleted_count += 1
                        logger.debug("[Backup] Deleted COS backup: %s", backup['key'])
                    except Exception as delete_error:
                        if CosServiceError is not None and isinstance(delete_error, CosServiceError):
                            # Type checker doesn't know CosServiceError methods, use hasattr checks
                            error_code = delete_error.get_error_code() if hasattr(delete_error, 'get_error_code') else 'Unknown'  # type: ignore
                            logger.warning("[Backup] Failed to delete COS backup %s: %s", backup['key'], error_code)
                        else:
                            logger.warning("[Backup] Failed to delete COS backup %s: %s", backup['key'], delete_error)

            except Exception as e:
                logger.warning(
                    "[Backup] Error processing COS backup %s: %s",
                    backup.get('key', 'unknown'),
                    e
                )
                continue

        if deleted_count > 0:
            logger.info("[Backup] Deleted %s old backup(s) from COS", deleted_count)

        return deleted_count

    except Exception as e:
        if CosClientError is not None and isinstance(e, CosClientError):
            logger.error("[Backup] COS client error cleaning up backups: %s", e, exc_info=True)
            return 0
        if CosServiceError is not None and isinstance(e, CosServiceError):
            # Server-side errors - reference: https://cloud.tencent.com/document/product/436/7730
            try:
                # Type checker doesn't know CosServiceError methods, use hasattr checks
                status_code = e.get_status_code() if hasattr(e, 'get_status_code') else 'Unknown'  # type: ignore
                error_code = e.get_error_code() if hasattr(e, 'get_error_code') else 'Unknown'  # type: ignore
                error_msg = e.get_error_msg() if hasattr(e, 'get_error_msg') else str(e)  # type: ignore
                request_id = e.get_request_id() if hasattr(e, 'get_request_id') else 'N/A'  # type: ignore
            except Exception:
                status_code = 'Unknown'
                error_code = 'Unknown'
                error_msg = str(e)
                request_id = 'N/A'

            logger.error(
                "[Backup] COS service error cleaning up backups: HTTP %s, Error %s - %s (RequestID: %s)",
                status_code,
                error_code,
                error_msg,
                request_id,
                exc_info=True
            )
            return 0
        logger.error("[Backup] Unexpected error cleaning up COS backups: %s", e, exc_info=True)
        return 0


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
                logger.info("[Backup] Deleted old backup: %s", backup_file.name)
                deleted_count += 1

                # Also clean up any WAL/SHM files that might exist for this backup
                # (shouldn't exist with our fixes, but clean up legacy files)
                for suffix in ["-wal", "-shm"]:
                    wal_file = backup_file.parent / f"{backup_file.name}{suffix}"
                    if wal_file.exists():
                        try:
                            wal_file.unlink()
                            logger.debug("[Backup] Cleaned up %s", wal_file.name)
                        except (OSError, PermissionError):
                            pass  # Ignore cleanup errors
            except (OSError, PermissionError) as e:
                logger.warning("[Backup] Could not delete %s: %s", backup_file.name, e)
    except Exception as e:
        logger.warning("[Backup] Cleanup error: %s", e)

    return deleted_count


def create_backup() -> bool:
    """
    Create a timestamped backup of the database.

    Returns:
        True if backup succeeded, False otherwise
    """
    # CRITICAL: Verify this worker holds the lock before creating backup
    # This prevents race conditions where multiple workers pass the initial lock check
    # The atomic lock refresh in the scheduler loop should prevent this, but this is
    # a final safety check
    if not is_backup_lock_holder():
        logger.warning("[Backup] Backup rejected: this worker does not hold the scheduler lock")
        return False

    source_db = get_database_path()
    if source_db is None:
        logger.warning("[Backup] Not using SQLite database, skipping backup")
        return False

    if not source_db.exists():
        logger.error("[Backup] Database not found: %s", source_db)
        return False

    # Check disk space before backup
    # Calculate required space: database size + 50MB buffer (for backup overhead and WAL checkpointing)
    try:
        db_size_mb = source_db.stat().st_size / (1024 * 1024)
        required_mb = max(100, int(db_size_mb) + 50)  # At least 100MB, or DB size + 50MB buffer
    except Exception:
        required_mb = 100  # Fallback to default if we can't get DB size

    if not _check_disk_space(BACKUP_DIR, required_mb=required_mb):
        logger.error("[Backup] Insufficient disk space (need %s MB), skipping backup", required_mb)
        return False

    # Generate timestamped backup filename
    # Use microsecond precision to avoid collisions if multiple backups are triggered simultaneously
    # Even with lock protection, this ensures unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = BACKUP_DIR / f"mindgraph.db.{timestamp}"

    logger.info("[Backup] Starting backup: %s -> %s", source_db, backup_path)

    # Create backup
    if backup_database_safely(source_db, backup_path):
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info("[Backup] Backup created: %s (%.2f MB)", backup_path.name, size_mb)

        # Verify integrity
        if verify_backup(backup_path):
            logger.info("[Backup] Integrity check passed")
        else:
            logger.warning("[Backup] Integrity check failed - backup may be corrupted")

        # CRITICAL: Verify backup is standalone (no WAL/SHM files)
        is_standalone, wal_files = verify_backup_is_standalone(backup_path)
        if not is_standalone:
            logger.error("[Backup] Backup is NOT standalone - found WAL/SHM files: %s", wal_files)
            # Try to clean them up
            for wal_file in wal_files:
                try:
                    Path(wal_file).unlink()
                    logger.info("[Backup] Removed %s", wal_file)
                except Exception as e:
                    logger.error("[Backup] Failed to remove %s: %s", wal_file, e)
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
            logger.info("[Backup] Cleaned up %s old backup(s)", deleted)

        # Upload to COS if enabled
        if COS_BACKUP_ENABLED:
            logger.info("[Backup] COS backup enabled, starting upload...")
            logger.info(
                "[Backup] COS config: bucket=%s, region=%s, prefix=%s",
                COS_BUCKET,
                COS_REGION,
                COS_KEY_PREFIX
            )
            if upload_backup_to_cos(backup_path):
                logger.info("[Backup] COS upload completed successfully")

                # Cleanup old COS backups (keep only last 2 days)
                # Delete backups older than 2 days (3 days old)
                deleted = cleanup_old_cos_backups(retention_days=2)
                if deleted > 0:
                    logger.info("[Backup] Cleaned up %s old backup(s) from COS", deleted)
            else:
                logger.error("[Backup] COS upload failed, but local backup succeeded")
                # Don't fail the backup if COS upload fails - local backup is still valid
        else:
            logger.debug("[Backup] COS backup disabled (COS_BACKUP_ENABLED=false), skipping upload")

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

    Uses Redis distributed lock to ensure only ONE worker runs the scheduler
    across all uvicorn workers. This prevents duplicate backups.

    Runs daily at the configured hour (default: 3:00 AM).
    This function runs forever until cancelled.
    """
    if not BACKUP_ENABLED:
        logger.info("[Backup] Automatic backup is disabled (BACKUP_ENABLED=false)")
        return

    # Attempt to acquire distributed lock
    # Only ONE worker across all processes will succeed
    if not acquire_backup_scheduler_lock():
        # Lock acquisition already logged the skip message
        # Keep running but don't do anything - just monitor
        # If the lock holder dies, this worker can try to acquire on next check
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                if acquire_backup_scheduler_lock():
                    logger.info("[Backup] Lock acquired, this worker will now run backups")
                    break
            except asyncio.CancelledError:
                logger.info("[Backup] Scheduler monitor stopped")
                return
            except Exception:
                pass

    # This worker holds the lock - run the scheduler
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("[Backup] Scheduler started (this worker is the lock holder)")
    logger.info(
        "[Backup] Configuration: daily at %02d:00, keep %s backups",
        BACKUP_HOUR,
        BACKUP_RETENTION_COUNT
    )
    logger.info("[Backup] Backup directory: %s", BACKUP_DIR.resolve())
    if COS_BACKUP_ENABLED:
        logger.info(
            "[Backup] COS backup enabled: bucket=%s, region=%s, prefix=%s",
            COS_BUCKET,
            COS_REGION,
            COS_KEY_PREFIX
        )
    else:
        logger.info("[Backup] COS backup disabled")

    while True:
        try:
            # Refresh lock to prevent expiration during long waits
            if not refresh_backup_scheduler_lock():
                logger.warning("[Backup] Lost scheduler lock, stopping scheduler on this worker")
                break

            # Calculate time until next backup
            next_backup = get_next_backup_time()
            wait_seconds = (next_backup - datetime.now()).total_seconds()

            logger.debug(
                "[Backup] Next backup scheduled at %s",
                next_backup.strftime('%Y-%m-%d %H:%M:%S')
            )

            # Wait until backup time, refreshing lock every 5 minutes
            while wait_seconds > 0:
                sleep_time = min(wait_seconds, 300)  # 5 minutes
                await asyncio.sleep(sleep_time)
                wait_seconds -= sleep_time

                # Refresh lock during wait
                if wait_seconds > 0 and not refresh_backup_scheduler_lock():
                    logger.warning("[Backup] Lost scheduler lock during wait")
                    return

            # CRITICAL: Verify we still hold the lock before running backup
            # Use atomic refresh to verify ownership and extend TTL in one operation
            if not refresh_backup_scheduler_lock():
                logger.warning("[Backup] Lock lost before backup execution, skipping")
                continue

            # Perform backup
            logger.info("[Backup] Starting scheduled backup...")

            try:
                success = await asyncio.to_thread(create_backup)
                if success:
                    logger.info("[Backup] Scheduled backup completed successfully")
                else:
                    logger.error("[Backup] Scheduled backup failed")
            except Exception as e:
                logger.error("[Backup] Scheduled backup failed with exception: %s", e, exc_info=True)

            # Refresh lock after backup completes
            refresh_backup_scheduler_lock()

            # Wait a bit to avoid running twice in the same minute
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("[Backup] Scheduler stopped")
            # Release lock on shutdown
            release_backup_scheduler_lock()
            break
        except Exception as e:
            logger.error("[Backup] Scheduler error: %s", e, exc_info=True)
            # Wait before retrying
            await asyncio.sleep(300)  # 5 minutes


async def run_backup_now() -> bool:
    """
    Run a backup immediately (for manual trigger or API call).

    Only the worker holding the scheduler lock can run backups.
    This prevents duplicate backups across workers.

    Returns:
        True if backup succeeded, False otherwise
    """
    # Only the lock holder can run manual backups
    # This prevents duplicate backups from multiple workers
    if not is_backup_lock_holder():
        logger.warning("[Backup] Manual backup rejected: this worker does not hold the scheduler lock")
        return False

    logger.info("[Backup] Manual backup triggered")
    refresh_backup_scheduler_lock()

    try:
        result = await asyncio.to_thread(create_backup)
        refresh_backup_scheduler_lock()
        return result
    except Exception as e:
        logger.error("[Backup] Backup failed with exception: %s", e, exc_info=True)
        return False


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
