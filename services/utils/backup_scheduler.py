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
import json
import logging
import os
import subprocess
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import get_redis, is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.utils.pg_backup_manifest import (
    build_pg_dump_manifest,
    prepare_pg_dump_rls,
    resolve_stats_engine,
)
from services.utils.pg_client_binaries import (
    build_pg_dump_cmd,
    find_pg_client_binary,
    log_pg_dump_failure,
    pg_tools_connection_username,
    pg_tools_libpq_url,
)
from services.utils import tencent_cos_client

try:
    from config.database import DATABASE_URL
except ImportError:
    DATABASE_URL = ""

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


class _BackupSchedulerLockState:
    """Holds worker lock id for Redis coordination without a global statement."""

    __slots__ = ("worker_lock_id",)

    def __init__(self) -> None:
        """init  ."""
        self.worker_lock_id: Optional[str] = None


_backup_scheduler_lock = _BackupSchedulerLockState()


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
    if not is_redis_available():
        # Redis is REQUIRED for multi-worker coordination
        # Without Redis, we cannot guarantee only one worker runs backups
        logger.error(
            "[Backup] Redis unavailable - cannot coordinate backups across workers. Backup scheduler disabled."
        )
        return False

    redis = get_redis()
    if not redis:
        logger.error("[Backup] Redis client not available - cannot coordinate backups. Backup scheduler disabled.")
        return False

    try:
        # Generate unique ID for this worker
        if _backup_scheduler_lock.worker_lock_id is None:
            _backup_scheduler_lock.worker_lock_id = _generate_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            BACKUP_LOCK_KEY,
            _backup_scheduler_lock.worker_lock_id,
            nx=True,  # Only set if not exists
            ex=BACKUP_LOCK_TTL,  # TTL in seconds
        )

        if acquired:
            logger.info(
                "[Backup] Lock acquired by this worker (id=%s)",
                _backup_scheduler_lock.worker_lock_id,
            )
            return True
        # Lock held by another worker - check who
        holder = redis.get(BACKUP_LOCK_KEY)
        logger.debug(
            "[Backup] Another worker holds the scheduler lock (holder=%s), this worker will not run backups",
            holder,
        )
        return False

    except BACKGROUND_INFRA_ERRORS as e:
        # On Redis error, fail safe - do not allow backup to prevent duplicates
        logger.error(
            "[Backup] Lock acquisition failed: %s. Backup scheduler disabled to prevent duplicate backups.",
            e,
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

    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
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
        result = redis.eval(lua_script, 1, BACKUP_LOCK_KEY, _backup_scheduler_lock.worker_lock_id)

        if result == 1:
            logger.info(
                "[Backup] Lock released by this worker (id=%s)",
                _backup_scheduler_lock.worker_lock_id,
            )

        return result == 1

    except BACKGROUND_INFRA_ERRORS as e:
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

    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
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
        result = redis.eval(
            lua_script,
            1,
            BACKUP_LOCK_KEY,
            _backup_scheduler_lock.worker_lock_id,
            BACKUP_LOCK_TTL,
        )

        if result == 1:
            logger.debug("[Backup] Lock refreshed (TTL=%ss)", BACKUP_LOCK_TTL)
            return True
        # Lock not held by us - check who holds it
        holder = redis.get(BACKUP_LOCK_KEY)
        logger.warning(
            "[Backup] Lock lost! Holder: %s, our ID: %s",
            holder,
            _backup_scheduler_lock.worker_lock_id,
        )
        return False

    except BACKGROUND_INFRA_ERRORS as e:
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

    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
        # Redis unavailable - cannot verify lock ownership
        logger.error("[Backup] Cannot verify lock ownership: Redis unavailable or lock ID not set")
        return False

    redis = get_redis()
    if not redis:
        logger.error("[Backup] Cannot verify lock ownership: Redis client not available")
        return False

    try:
        holder = redis.get(BACKUP_LOCK_KEY)
        return holder == _backup_scheduler_lock.worker_lock_id
    except BACKGROUND_INFRA_ERRORS as e:
        # On error, fail safe - do not assume we hold the lock
        logger.warning("[Backup] Error checking lock ownership: %s", e)
        return False


# ============================================================================
# Async variants of the lock helpers
#
# These mirror the sync helpers above but use the shared async Redis client.
# They are intended for callers running on the asyncio event loop (e.g.
# ``start_backup_scheduler`` / ``run_backup_now``), so the loop is never
# blocked on a synchronous Redis round-trip.  The sync variants are kept for
# code paths that genuinely run off-loop (the synchronous ``create_backup``
# helper executed via ``asyncio.to_thread``).
# ============================================================================


async def acquire_backup_scheduler_lock_async() -> bool:
    """Async counterpart of :func:`acquire_backup_scheduler_lock`."""
    if not is_redis_available():
        logger.error(
            "[Backup] Redis unavailable - cannot coordinate backups across workers. Backup scheduler disabled."
        )
        return False

    redis = get_async_redis()
    if not redis:
        logger.error(
            "[Backup] Redis async client not available - cannot coordinate backups. Backup scheduler disabled."
        )
        return False

    try:
        if _backup_scheduler_lock.worker_lock_id is None:
            _backup_scheduler_lock.worker_lock_id = _generate_lock_id()

        acquired = await redis.set(
            BACKUP_LOCK_KEY,
            _backup_scheduler_lock.worker_lock_id,
            nx=True,
            ex=BACKUP_LOCK_TTL,
        )

        if acquired:
            logger.info(
                "[Backup] Lock acquired by this worker (id=%s)",
                _backup_scheduler_lock.worker_lock_id,
            )
            return True

        holder = await redis.get(BACKUP_LOCK_KEY)
        logger.debug(
            "[Backup] Another worker holds the scheduler lock (holder=%s), this worker will not run backups",
            holder,
        )
        return False

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error(
            "[Backup] Lock acquisition failed: %s. Backup scheduler disabled to prevent duplicate backups.",
            e,
        )
        return False


async def release_backup_scheduler_lock_async() -> bool:
    """Async counterpart of :func:`release_backup_scheduler_lock`."""
    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
        return True

    redis = get_async_redis()
    if not redis:
        return True

    try:
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await redis.eval(lua_script, 1, BACKUP_LOCK_KEY, _backup_scheduler_lock.worker_lock_id)

        if result == 1:
            logger.info(
                "[Backup] Lock released by this worker (id=%s)",
                _backup_scheduler_lock.worker_lock_id,
            )

        return result == 1

    except BACKGROUND_INFRA_ERRORS as e:
        logger.warning("[Backup] Lock release failed: %s", e)
        return False


async def refresh_backup_scheduler_lock_async() -> bool:
    """Async counterpart of :func:`refresh_backup_scheduler_lock`."""
    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
        logger.error("[Backup] Cannot refresh lock: Redis unavailable or lock ID not set")
        return False

    redis = get_async_redis()
    if not redis:
        logger.error("[Backup] Cannot refresh lock: Redis async client not available")
        return False

    try:
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("expire", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """
        result = await redis.eval(
            lua_script,
            1,
            BACKUP_LOCK_KEY,
            _backup_scheduler_lock.worker_lock_id,
            BACKUP_LOCK_TTL,
        )

        if result == 1:
            logger.debug("[Backup] Lock refreshed (TTL=%ss)", BACKUP_LOCK_TTL)
            return True

        holder = await redis.get(BACKUP_LOCK_KEY)
        logger.warning(
            "[Backup] Lock lost! Holder: %s, our ID: %s",
            holder,
            _backup_scheduler_lock.worker_lock_id,
        )
        return False

    except BACKGROUND_INFRA_ERRORS as e:
        logger.warning("[Backup] Lock refresh failed: %s", e)
        return False


async def is_backup_lock_holder_async() -> bool:
    """Async counterpart of :func:`is_backup_lock_holder`."""
    if not is_redis_available() or _backup_scheduler_lock.worker_lock_id is None:
        logger.error("[Backup] Cannot verify lock ownership: Redis unavailable or lock ID not set")
        return False

    redis = get_async_redis()
    if not redis:
        logger.error("[Backup] Cannot verify lock ownership: Redis async client not available")
        return False

    try:
        holder = await redis.get(BACKUP_LOCK_KEY)
        return holder == _backup_scheduler_lock.worker_lock_id
    except BACKGROUND_INFRA_ERRORS as e:
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

_BACKUP_DIR_ENV = os.getenv("BACKUP_DIR", "backup")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = Path(_BACKUP_DIR_ENV) if Path(_BACKUP_DIR_ENV).is_absolute() else _PROJECT_ROOT / _BACKUP_DIR_ENV

# COS (Tencent Cloud Object Storage) configuration
# Note: Uses same Tencent Cloud credentials as SMS module (TENCENT_SMS_SECRET_ID/SECRET_KEY)
COS_BACKUP_ENABLED = os.getenv("COS_BACKUP_ENABLED", "false").lower() == "true"
COS_SECRET_ID = tencent_cos_client.COS_SECRET_ID
COS_SECRET_KEY = tencent_cos_client.COS_SECRET_KEY
COS_BUCKET = tencent_cos_client.COS_BUCKET
COS_REGION = tencent_cos_client.COS_REGION
COS_KEY_PREFIX = tencent_cos_client.COS_KEY_PREFIX


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
                required_mb,
            )
            return False
        return True
    except AttributeError:
        # Windows doesn't have statvfs, assume OK
        return True
    except BACKGROUND_INFRA_ERRORS as e:
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
        # Migrate role (BYPASSRLS) — runtime DATABASE_URL cannot dump RLS tables.
        db_url = pg_tools_libpq_url()
        if not db_url or "postgresql" not in db_url.lower():
            logger.error("[Backup] Not a PostgreSQL database URL")
            return False

        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Use .dump format (custom format) for better compression and restore options
        # Can also use .sql for plain text, but .dump is more efficient
        if not backup_path.suffix:
            backup_path = backup_path.with_suffix(".dump")

        rls_ok, rls_msg = prepare_pg_dump_rls()
        if not rls_ok:
            logger.error("[Backup] RLS bootstrap failed before pg_dump: %s", rls_msg)
            return False

        dump_user = pg_tools_connection_username(db_url)
        logger.info(
            "[Backup] Starting PostgreSQL backup using pg_dump (connection user=%s)",
            dump_user,
        )

        pg_dump_binary = find_pg_client_binary("pg_dump")
        if not pg_dump_binary:
            logger.error("[Backup] pg_dump binary not found. Install PostgreSQL client tools.")
            return False

        # Run pg_dump (shared flags with admin export: custom format, no owner, no policies)
        cmd = build_pg_dump_cmd(pg_dump_binary, backup_path, db_url)

        logger.debug("[Backup] Running: %s", " ".join(cmd[:3]) + " [URL]")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=3600,  # 1 hour timeout
            check=False,
            text=True,
        )

        if result.returncode != 0:
            log_pg_dump_failure(result.stderr or result.stdout or "Unknown error")
            if backup_path.exists():
                backup_path.unlink()
            return False

        # Verify backup file exists and is not empty
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            logger.error("[Backup] Backup file was not created or is empty")
            return False

        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(
            "[Backup] PostgreSQL backup created: %s (%.2f MB)",
            backup_path.name,
            size_mb,
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error("[Backup] pg_dump timed out after 1 hour")
        if backup_path.exists():
            backup_path.unlink()
        return False
    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[Backup] PostgreSQL backup failed: %s", e, exc_info=True)
        if backup_path.exists():
            try:
                backup_path.unlink()
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.debug("Failed backup file cleanup failed: %s", exc)
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
        pg_restore_binary = find_pg_client_binary("pg_restore")
        if pg_restore_binary:
            # Use pg_restore --list to verify backup integrity
            result = subprocess.run(
                [pg_restore_binary, "--list", str(backup_path)],
                capture_output=True,
                timeout=60,
                check=False,
            )
            if result.returncode == 0:
                logger.debug("[Backup] PostgreSQL backup verification passed")
                return True
            logger.warning("[Backup] PostgreSQL backup verification failed: %s", result.stderr)
            return False
        # pg_restore not found, assume backup is valid if file exists and has size
        logger.debug("[Backup] pg_restore not found, skipping verification (backup file exists)")
        return True
    except BACKGROUND_INFRA_ERRORS as e:
        logger.warning("[Backup] PostgreSQL backup verification error: %s", e)
        # Assume valid if file exists and has size
        return True


def upload_backup_to_cos(backup_path: Path, max_retries: int = 3) -> bool:
    """Upload backup file to Tencent Cloud Object Storage (COS)."""
    if not COS_BACKUP_ENABLED:
        logger.debug("[Backup] COS backup disabled, skipping upload")
        return True

    if not backup_path.exists():
        logger.error("[Backup] Backup file does not exist: %s", backup_path)
        return False

    if not tencent_cos_client.cos_credentials_configured():
        logger.warning(
            "[Backup] COS backup enabled but Tencent Cloud credentials not configured "
            "(TENCENT_SMS_SECRET_ID/SECRET_KEY), skipping upload"
        )
        return False

    try:
        file_size_bytes = backup_path.stat().st_size
    except (OSError, PermissionError) as exc:
        logger.error("[Backup] Cannot access backup file %s: %s", backup_path, exc)
        return False

    if file_size_bytes == 0:
        logger.error("[Backup] Backup file is empty: %s", backup_path)
        return False

    object_key = tencent_cos_client.cos_object_key(backup_path.name)
    return tencent_cos_client.upload_file(
        backup_path,
        object_key,
        max_retries=max_retries,
        log_prefix="[Backup]",
    )


def list_cos_backups() -> List[dict]:
    """List PostgreSQL backup dumps in COS under the configured prefix."""
    if not COS_BACKUP_ENABLED:
        return []
    if not tencent_cos_client.cos_credentials_configured():
        return []

    prefix = tencent_cos_client.normalized_cos_prefix()
    objects = tencent_cos_client.list_prefix(
        prefix,
        suffix_filter=".dump",
        contains_filter="mindgraph.postgresql.",
    )
    backups: List[dict] = []
    for obj in objects:
        backups.append(
            {
                "key": obj["key"],
                "size": obj["size"],
                "last_modified": obj["last_modified"],
                "filename": obj["filename"],
            }
        )
    logger.debug("[Backup] Found %s backup(s) in COS", len(backups))
    return backups


def cleanup_old_cos_backups(retention_days: int = 2) -> int:
    """Delete COS backups older than retention_days."""
    if not COS_BACKUP_ENABLED:
        return 0
    if not tencent_cos_client.cos_credentials_configured():
        return 0

    backups = list_cos_backups()
    if not backups:
        logger.debug("[Backup] No COS backups found with prefix: %s", COS_KEY_PREFIX)
        return 0

    cutoff_time = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    for backup in backups:
        last_modified = tencent_cos_client.parse_cos_timestamp(backup.get("last_modified"))
        if last_modified is None:
            continue
        if last_modified >= cutoff_time:
            continue
        age_days = (datetime.now() - last_modified).days
        logger.info(
            "[Backup] Deleting old COS backup: %s (age: %s days)",
            backup["key"],
            age_days,
        )
        if tencent_cos_client.delete_object(backup["key"]):
            deleted_count += 1
            manifest_key = f"{backup['key']}.manifest.json"
            tencent_cos_client.delete_object(manifest_key)

    if deleted_count > 0:
        logger.info("[Backup] Deleted %s old backup(s) from COS", deleted_count)
    return deleted_count


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

        # Delete files beyond the keep_count (dump + manifest)
        for _, backup_file in backup_files[keep_count:]:
            try:
                backup_file.unlink()
                logger.info("[Backup] Deleted old backup: %s", backup_file.name)
                deleted_count += 1

                manifest_file = Path(f"{backup_file}.manifest.json")
                if manifest_file.exists():
                    manifest_file.unlink()
                    logger.debug("[Backup] Deleted manifest: %s", manifest_file.name)
            except (OSError, PermissionError) as e:
                logger.warning("[Backup] Could not delete %s: %s", backup_file.name, e)
    except BACKGROUND_INFRA_ERRORS as e:
        logger.warning("[Backup] Cleanup error: %s", e)

    return deleted_count


def _write_backup_manifest(backup_path: Path) -> Optional[Path]:
    """
    Write a manifest JSON alongside a pg_dump backup file.

    The manifest records table row counts and summary statistics so that
    restores can be verified (matching the pattern used by
    ``database_export_service`` and ``dump_import_postgres``).

    Returns:
        Path to the manifest file, or None on failure.
    """
    try:
        stats_engine = resolve_stats_engine(bootstrap_rls=False)
        try:
            manifest = build_pg_dump_manifest(backup_path, stats_engine)
        finally:
            stats_engine.dispose()

        manifest_path = Path(f"{backup_path}.manifest.json")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("[Backup] Manifest written: %s", manifest_path.name)
        return manifest_path

    except DATABASE_ERRORS as exc:
        logger.warning("[Backup] Failed to write manifest: %s", exc)
        return None


def _upload_to_cos_if_enabled(
    backup_path: Path,
    manifest_path: Optional[Path],
) -> None:
    """Upload dump and manifest to COS, then clean up old COS backups."""
    if not COS_BACKUP_ENABLED:
        logger.debug("[Backup] COS backup disabled (COS_BACKUP_ENABLED=false), skipping upload")
        return

    logger.info("[Backup] COS backup enabled, starting upload...")
    logger.info(
        "[Backup] COS config: bucket=%s, region=%s, prefix=%s",
        COS_BUCKET,
        COS_REGION,
        COS_KEY_PREFIX,
    )

    if not upload_backup_to_cos(backup_path):
        logger.error("[Backup] COS upload failed, but local backup succeeded")
        return

    logger.info("[Backup] COS dump upload completed successfully")

    if manifest_path and manifest_path.exists():
        if upload_backup_to_cos(manifest_path):
            logger.info("[Backup] COS manifest upload completed")
        else:
            logger.warning("[Backup] COS manifest upload failed")

    deleted = cleanup_old_cos_backups(retention_days=2)
    if deleted > 0:
        logger.info("[Backup] Cleaned up %s old backup(s) from COS", deleted)


def create_backup() -> bool:
    """
    Create a timestamped backup of the PostgreSQL database.

    Returns:
        True if backup succeeded, False otherwise
    """
    if not is_backup_lock_holder():
        logger.warning("[Backup] Backup rejected: this worker does not hold the scheduler lock")
        return False

    if not is_postgresql():
        logger.warning("[Backup] Not using PostgreSQL database, skipping backup")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = BACKUP_DIR / f"mindgraph.postgresql.{timestamp}.dump"

    logger.info("[Backup] Starting PostgreSQL backup...")

    if not _check_disk_space(BACKUP_DIR, required_mb=200):
        logger.error("[Backup] Insufficient disk space (need at least 200 MB), skipping backup")
        return False

    if not backup_postgresql_database(backup_path):
        logger.error("[Backup] PostgreSQL backup failed")
        return False

    if verify_backup(backup_path):
        logger.info("[Backup] Integrity check passed")
    else:
        logger.warning("[Backup] Integrity check failed - backup may be corrupted")

    manifest_path = _write_backup_manifest(backup_path)

    deleted = cleanup_old_backups(BACKUP_DIR, BACKUP_RETENTION_COUNT)
    if deleted > 0:
        logger.info("[Backup] Cleaned up %s old backup(s)", deleted)

    _upload_to_cos_if_enabled(backup_path, manifest_path)

    return True


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


async def _notify_scheduled_backup_failure(error_message: str) -> None:
    """Send deduplicated SMS alert when scheduled backup fails."""
    try:
        await CriticalAlertService.send_runtime_error_alert(
            component="Backup",
            error_message=error_message,
            details=(
                "Scheduled PostgreSQL backup failed. Verify DATABASE_MIGRATION_URL uses "
                "mindgraph_migrate (BYPASSRLS) and pg_dump can COPY RLS-protected tables."
            ),
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[Backup] Failed to send backup failure alert: %s", exc)


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
    if not await acquire_backup_scheduler_lock_async():
        # Lock acquisition already logged the skip message
        # Keep running but don't do anything - just monitor
        # If the lock holder dies, this worker can try to acquire on next check
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                if await acquire_backup_scheduler_lock_async():
                    logger.info("[Backup] Lock acquired, this worker will now run backups")
                    break
            except asyncio.CancelledError:
                logger.info("[Backup] Scheduler monitor stopped")
                return
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.debug("Backup scheduler lock acquisition retry failed: %s", exc)

    # This worker holds the lock - run the scheduler
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("[Backup] Scheduler started (this worker is the lock holder)")
    logger.info(
        "[Backup] Configuration: daily at %02d:00, keep %s backups",
        BACKUP_HOUR,
        BACKUP_RETENTION_COUNT,
    )
    logger.info("[Backup] Backup directory: %s", BACKUP_DIR.resolve())
    if COS_BACKUP_ENABLED:
        logger.info(
            "[Backup] COS backup enabled: bucket=%s, region=%s, prefix=%s",
            COS_BUCKET,
            COS_REGION,
            COS_KEY_PREFIX,
        )
    else:
        logger.info("[Backup] COS backup disabled")

    while True:
        try:
            # Refresh lock to prevent expiration during long waits
            if not await refresh_backup_scheduler_lock_async():
                logger.warning("[Backup] Lost scheduler lock, stopping scheduler on this worker")
                break

            # Calculate time until next backup
            next_backup = get_next_backup_time()
            wait_seconds = (next_backup - datetime.now()).total_seconds()

            logger.debug(
                "[Backup] Next backup scheduled at %s",
                next_backup.strftime("%Y-%m-%d %H:%M:%S"),
            )

            # Wait until backup time, refreshing lock every 5 minutes
            while wait_seconds > 0:
                sleep_time = min(wait_seconds, 300)  # 5 minutes
                await asyncio.sleep(sleep_time)
                wait_seconds -= sleep_time

                # Refresh lock during wait
                if wait_seconds > 0 and not await refresh_backup_scheduler_lock_async():
                    logger.warning("[Backup] Lost scheduler lock during wait")
                    return

            # CRITICAL: Verify we still hold the lock before running backup
            # Use atomic refresh to verify ownership and extend TTL in one operation
            if not await refresh_backup_scheduler_lock_async():
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
                    await _notify_scheduled_backup_failure("Scheduled PostgreSQL backup failed")
            except BACKGROUND_INFRA_ERRORS as e:
                logger.error(
                    "[Backup] Scheduled backup failed with exception: %s",
                    e,
                    exc_info=True,
                )
                await _notify_scheduled_backup_failure(f"Scheduled backup exception: {e}")

            # Refresh lock after backup completes
            await refresh_backup_scheduler_lock_async()

            # Wait a bit to avoid running twice in the same minute
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("[Backup] Scheduler stopped")
            # Release lock on shutdown
            await release_backup_scheduler_lock_async()
            break
        except BACKGROUND_INFRA_ERRORS as e:
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
    if not await is_backup_lock_holder_async():
        logger.warning("[Backup] Manual backup rejected: this worker does not hold the scheduler lock")
        return False

    logger.info("[Backup] Manual backup triggered")
    await refresh_backup_scheduler_lock_async()

    try:
        result = await asyncio.to_thread(create_backup)
        await refresh_backup_scheduler_lock_async()
        return result
    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[Backup] Backup failed with exception: %s", e, exc_info=True)
        return False


def _read_manifest(dump_path: Path) -> Optional[Dict[str, Any]]:
    """Read a manifest file accompanying a .dump backup, if it exists."""
    manifest_path = Path(f"{dump_path}.manifest.json")
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("[Backup] Could not read manifest %s: %s", manifest_path.name, exc)
        return None


def get_backup_status() -> dict:
    """
    Get the current backup status and list of backups.

    Returns:
        dict with backup configuration and list of existing backups.
        Each backup entry includes manifest data (row counts) when available.
    """
    backups: List[Dict[str, Any]] = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("mindgraph.postgresql.*.dump"), reverse=True):
            if backup_file.is_file():
                stat = backup_file.stat()
                entry: Dict[str, Any] = {
                    "filename": backup_file.name,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": "postgresql",
                }
                manifest = _read_manifest(backup_file)
                if manifest:
                    entry["total_tables"] = manifest.get("total_tables")
                    entry["total_records"] = manifest.get("total_records")
                    entry["manifest"] = manifest
                backups.append(entry)

    cos_summary: Dict[str, Any] = {
        "enabled": COS_BACKUP_ENABLED,
        "configured": tencent_cos_client.cos_credentials_configured(),
        "count": 0,
        "latest": None,
    }
    if COS_BACKUP_ENABLED and tencent_cos_client.cos_credentials_configured():
        cos_items = list_cos_backups()
        cos_summary["count"] = len(cos_items)
        if cos_items:
            sorted_items = sorted(
                cos_items,
                key=lambda item: tencent_cos_client.parse_cos_timestamp(item.get("last_modified")) or datetime.min,
                reverse=True,
            )
            latest = sorted_items[0]
            last_mod = tencent_cos_client.parse_cos_timestamp(latest.get("last_modified"))
            cos_summary["latest"] = {
                "key": latest.get("key"),
                "filename": latest.get("filename") or latest.get("key", "").rsplit("/", 1)[-1],
                "size_mb": round(int(latest.get("size", 0)) / (1024 * 1024), 2),
                "last_modified": last_mod.isoformat() if last_mod else None,
            }

    return {
        "enabled": BACKUP_ENABLED,
        "schedule_hour": BACKUP_HOUR,
        "retention_count": BACKUP_RETENTION_COUNT,
        "backup_dir": str(BACKUP_DIR.resolve()),
        "next_backup": get_next_backup_time().isoformat() if BACKUP_ENABLED else None,
        "backups": backups,
        "cos": cos_summary,
    }
