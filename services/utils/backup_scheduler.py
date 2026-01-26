"""
Automated Database Backup Scheduler for MindGraph
==================================================

Automatic daily backup of PostgreSQL database with configurable retention.
Integrates with the FastAPI lifespan to run as a background task.

Features:
- Daily automatic backups (configurable time)
- Rotation: keeps only N most recent backups (default: 2)
- PostgreSQL: Uses pg_dump for consistent database snapshots
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
import subprocess
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

# Thread-safe flag to indicate backup is in progress
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

    Returns:
        True if backup is running, False otherwise
    """
    return _backup_in_progress.is_set()


def is_postgresql() -> bool:
    """
    Check if using PostgreSQL database.

    Returns:
        True if using PostgreSQL, False otherwise
    """
    return "postgresql" in DATABASE_URL.lower()


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


def backup_postgresql_database(backup_path: Path) -> bool:
    """
    Backup PostgreSQL database using pg_dump.

    Args:
        backup_path: Path to backup file (will be created as .sql or .dump)

    Returns:
        True if backup succeeded, False otherwise
    """
    try:
        # Parse PostgreSQL connection URL
        # Format: postgresql://user:password@host:port/database
        db_url = DATABASE_URL
        if not db_url or "postgresql" not in db_url.lower():
            logger.error("[Backup] Not a PostgreSQL database URL")
            return False

        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Use .dump format (custom format) for better compression and restore options
        # Can also use .sql for plain text, but .dump is more efficient
        if not backup_path.suffix:
            backup_path = backup_path.with_suffix('.dump')

        logger.info("[Backup] Starting PostgreSQL backup using pg_dump...")

        # Find pg_dump binary
        pg_dump_paths = [
            '/usr/lib/postgresql/18/bin/pg_dump',
            '/usr/lib/postgresql/16/bin/pg_dump',
            '/usr/lib/postgresql/15/bin/pg_dump',
            '/usr/lib/postgresql/14/bin/pg_dump',
            '/usr/local/pgsql/bin/pg_dump',
            '/usr/bin/pg_dump',
        ]

        pg_dump_binary = None
        for path in pg_dump_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                pg_dump_binary = path
                break

        if not pg_dump_binary:
            # Try to find pg_dump in PATH
            try:
                result = subprocess.run(
                    ['which', 'pg_dump'],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                if result.returncode == 0:
                    pg_dump_binary = result.stdout.decode('utf-8').strip()
            except Exception:
                pass

        if not pg_dump_binary:
            logger.error("[Backup] pg_dump binary not found. Install PostgreSQL client tools.")
            return False

        # Run pg_dump
        # Use custom format (-Fc) for compressed, flexible restore options
        # -Fc: custom format (compressed, can restore specific tables)
        # -Fp: plain SQL format (uncompressed, human-readable)
        # We use -Fc for better compression and restore flexibility
        cmd = [
            pg_dump_binary,
            '-Fc',  # Custom format (compressed)
            '-f', str(backup_path),
            db_url
        ]

        logger.debug("[Backup] Running: %s", ' '.join(cmd[:3]) + ' [URL]')

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=3600,  # 1 hour timeout
            check=False,
            text=True
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error("[Backup] pg_dump failed: %s", error_msg)
            if backup_path.exists():
                backup_path.unlink()
            return False

        # Verify backup file exists and is not empty
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            logger.error("[Backup] Backup file was not created or is empty")
            return False

        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info("[Backup] PostgreSQL backup created: %s (%.2f MB)", backup_path.name, size_mb)
        return True

    except subprocess.TimeoutExpired:
        logger.error("[Backup] pg_dump timed out after 1 hour")
        if backup_path.exists():
            backup_path.unlink()
        return False
    except Exception as e:
        logger.error("[Backup] PostgreSQL backup failed: %s", e, exc_info=True)
        if backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        return False


def verify_backup(backup_path: Path) -> bool:
    """
    Verify PostgreSQL backup database integrity.

    Args:
        backup_path: Path to backup file (PostgreSQL .dump/.sql)

    Returns:
        True if backup is valid, False otherwise
    """
    if not backup_path.exists() or backup_path.stat().st_size == 0:
        return False

    # PostgreSQL backup verification using pg_restore --list (dry-run)
    try:
        pg_restore_paths = [
            '/usr/lib/postgresql/18/bin/pg_restore',
            '/usr/lib/postgresql/16/bin/pg_restore',
            '/usr/lib/postgresql/15/bin/pg_restore',
            '/usr/lib/postgresql/14/bin/pg_restore',
            '/usr/local/pgsql/bin/pg_restore',
            '/usr/bin/pg_restore',
        ]

        pg_restore_binary = None
        for path in pg_restore_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                pg_restore_binary = path
                break

        if not pg_restore_binary:
            # Try PATH
            try:
                result = subprocess.run(
                    ['which', 'pg_restore'],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                if result.returncode == 0:
                    pg_restore_binary = result.stdout.decode('utf-8').strip()
            except Exception:
                pass

        if pg_restore_binary:
            # Use pg_restore --list to verify backup integrity
            result = subprocess.run(
                [pg_restore_binary, '--list', str(backup_path)],
                capture_output=True,
                timeout=60,
                check=False
            )
            if result.returncode == 0:
                logger.debug("[Backup] PostgreSQL backup verification passed")
                return True
            else:
                logger.warning("[Backup] PostgreSQL backup verification failed: %s", result.stderr)
                return False
        else:
            # pg_restore not found, assume backup is valid if file exists and has size
            logger.debug("[Backup] pg_restore not found, skipping verification (backup file exists)")
            return True
    except Exception as e:
        logger.warning("[Backup] PostgreSQL backup verification error: %s", e)
        # Assume valid if file exists and has size
        return True


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
    # Format: {COS_KEY_PREFIX}/mindgraph.postgresql.{timestamp}.dump
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
                resource_location = (
                    e.get_resource_location()
                    if hasattr(e, 'get_resource_location') else 'N/A'
                )  # type: ignore
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

                    # Only include files matching backup pattern (mindgraph.postgresql.*.dump)
                    if 'mindgraph.postgresql.' in obj_key and obj_key.endswith('.dump'):
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
                            error_code = (
                                delete_error.get_error_code()
                                if hasattr(delete_error, 'get_error_code')
                                else 'Unknown'
                            )  # type: ignore
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

    Supports PostgreSQL (.dump) backup files.

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
        # Find all PostgreSQL backup files and sort by modification time (newest first)
        backup_files = []
        # PostgreSQL backups: mindgraph.postgresql.*.dump
        for backup_file in backup_dir.glob("mindgraph.postgresql.*.dump"):
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
            except (OSError, PermissionError) as e:
                logger.warning("[Backup] Could not delete %s: %s", backup_file.name, e)
    except Exception as e:
        logger.warning("[Backup] Cleanup error: %s", e)

    return deleted_count


def create_backup() -> bool:
    """
    Create a timestamped backup of the PostgreSQL database.

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

    # PostgreSQL backup
    if not is_postgresql():
        logger.warning("[Backup] Not using PostgreSQL database, skipping backup")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = BACKUP_DIR / f"mindgraph.postgresql.{timestamp}.dump"

    logger.info("[Backup] Starting PostgreSQL backup...")

    # Check disk space (estimate: assume 2x database size for compressed backup)
    if not _check_disk_space(BACKUP_DIR, required_mb=200):
        logger.error("[Backup] Insufficient disk space (need at least 200 MB), skipping backup")
        return False

    # Create PostgreSQL backup
    if backup_postgresql_database(backup_path):
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info("[Backup] PostgreSQL backup created: %s (%.2f MB)", backup_path.name, size_mb)

        # Verify integrity
        if verify_backup(backup_path):
            logger.info("[Backup] Integrity check passed")
        else:
            logger.warning("[Backup] Integrity check failed - backup may be corrupted")

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
                deleted = cleanup_old_cos_backups(retention_days=2)
                if deleted > 0:
                    logger.info("[Backup] Cleaned up %s old backup(s) from COS", deleted)
            else:
                logger.error("[Backup] COS upload failed, but local backup succeeded")
        else:
            logger.debug("[Backup] COS backup disabled (COS_BACKUP_ENABLED=false), skipping upload")

        return True
    else:
        logger.error("[Backup] PostgreSQL backup failed")
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
        # PostgreSQL backups
        for backup_file in sorted(BACKUP_DIR.glob("mindgraph.postgresql.*.dump"), reverse=True):
            if backup_file.is_file():
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": "postgresql"
                })

    return {
        "enabled": BACKUP_ENABLED,
        "schedule_hour": BACKUP_HOUR,
        "retention_count": BACKUP_RETENTION_COUNT,
        "backup_dir": str(BACKUP_DIR.resolve()),
        "next_backup": get_next_backup_time().isoformat() if BACKUP_ENABLED else None,
        "backups": backups
    }
