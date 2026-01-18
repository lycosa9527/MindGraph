"""
Temporary Image Cleanup Service
================================

Background task to clean up old PNG files from temp_images/ directory.
Automatically removes files older than 24 hours.

100% async implementation - all file operations use asyncio.
Compatible with Windows and Ubuntu when running under Uvicorn.

Uses Redis distributed lock to ensure only ONE worker cleans files.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional
import aiofiles.os  # Async file system operations

try:
    from services.redis.redis_client import get_redis, is_redis_available
    _REDIS_AVAILABLE = True
except ImportError:
    get_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to run cleanup schedulers.
#
# Solution: Redis-based distributed lock ensures only ONE worker cleans files.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: cleanup:temp_images:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 10 minutes (auto-release if worker crashes)
# ============================================================================

CLEANUP_LOCK_KEY = "cleanup:temp_images:lock"
CLEANUP_LOCK_TTL = 600  # 10 minutes - auto-release if worker crashes


class CleanupLockState:
    """Encapsulates cleanup lock state to avoid global variables."""
    def __init__(self):
        self.lock_id: Optional[str] = None

    def generate_lock_id(self) -> str:
        """Generate unique lock ID for this worker: {pid}:{uuid}"""
        if self.lock_id is None:
            self.lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        return self.lock_id

    def get_lock_id(self) -> Optional[str]:
        """Get current lock ID."""
        return self.lock_id

    def set_lock_id(self, lock_id: str) -> None:
        """Set lock ID."""
        self.lock_id = lock_id


_cleanup_lock_state = CleanupLockState()


async def refresh_cleanup_lock() -> bool:
    """
    Refresh the cleanup lock TTL if held by this worker.

    Uses atomic Lua script to check-and-refresh in one operation,
    preventing race conditions where lock could be lost between check and refresh.

    Returns:
        True if lock refreshed, False if not held by this worker
    """
    if not _REDIS_AVAILABLE:
        return False

    if not is_redis_available or not is_redis_available():
        return False

    lock_id = _cleanup_lock_state.get_lock_id()
    if lock_id is None:
        return False

    if not get_redis:
        return False

    redis = get_redis()
    if not redis:
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
        result = await asyncio.to_thread(
            redis.eval,
            lua_script,
            1,
            CLEANUP_LOCK_KEY,
            lock_id,
            CLEANUP_LOCK_TTL
        )

        if result == 1:
            return True
        # Lock not held by us
        holder = await asyncio.to_thread(redis.get, CLEANUP_LOCK_KEY)
        logger.debug("[Cleanup] Lock lost! Holder: %s, our ID: %s", holder, lock_id)
        return False

    except Exception as e:
        logger.debug("[Cleanup] Lock refresh failed: %s", e)
        return False


async def acquire_cleanup_lock() -> bool:
    """
    Attempt to acquire the cleanup lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should clean files)
        False if lock held by another worker
    """
    if not _REDIS_AVAILABLE:
        # Redis not available, assume single worker mode
        return True

    if not is_redis_available or not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[Cleanup] Redis unavailable, assuming single worker mode")
        return True

    if not get_redis:
        return True  # Fallback to single worker mode

    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode

    try:
        # Generate unique ID for this worker
        lock_id = _cleanup_lock_state.generate_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        # Use asyncio.to_thread() to avoid blocking event loop
        acquired = await asyncio.to_thread(
            redis.set,
            CLEANUP_LOCK_KEY,
            lock_id,
            nx=True,  # Only set if not exists
            ex=CLEANUP_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.debug("[Cleanup] Lock acquired by this worker (id=%s)", lock_id)
            return True
        # Lock held by another worker - check who
        holder = await asyncio.to_thread(redis.get, CLEANUP_LOCK_KEY)
        logger.info("[Cleanup] Another worker holds the cleanup lock (holder=%s), skipping cleanup", holder)
        return False

    except Exception as e:
        logger.warning("[Cleanup] Lock acquisition failed: %s, proceeding anyway", e)
        return True  # On error, proceed (better to have duplicate than no cleanup)


async def cleanup_temp_images(max_age_seconds: int = 86400):
    """
    Remove PNG files older than max_age_seconds from temp_images/ directory.

    100% async implementation - uses aiofiles.os for non-blocking file operations.

    Args:
        max_age_seconds: Maximum age in seconds (default 24 hours)

    Returns:
        Number of files deleted
    """
    temp_dir = Path("temp_images")

    if not temp_dir.exists():
        # Silently skip if directory doesn't exist - nothing to clean
        return 0

    current_time = time.time()
    deleted_count = 0

    try:
        # Use asyncio to run blocking glob operation in thread pool
        files = await asyncio.to_thread(list, temp_dir.glob("dingtalk_*.png"))

        for file_path in files:
            # Get file stats asynchronously
            try:
                stat_result = await aiofiles.os.stat(file_path)
                file_age = current_time - stat_result.st_mtime

                if file_age > max_age_seconds:
                    try:
                        # Delete file asynchronously (non-blocking)
                        await aiofiles.os.remove(file_path)
                        deleted_count += 1
                        logger.debug("Deleted expired image: %s (age: %.1fh)", file_path.name, file_age / 3600)
                    except Exception as e:
                        logger.error("Failed to delete %s: %s", file_path.name, e)
            except Exception as e:
                logger.error("Failed to stat %s: %s", file_path.name, e)

        if deleted_count > 0:
            logger.info("Temp image cleanup: Deleted %d expired files", deleted_count)
        else:
            logger.debug("Temp image cleanup: No expired files found")

        return deleted_count

    except Exception as e:
        logger.error("Temp image cleanup failed: %s", e, exc_info=True)
        return deleted_count


async def start_cleanup_scheduler(interval_hours: int = 1):
    """
    Run cleanup task periodically in background.

    Uses Redis distributed lock to ensure only ONE worker cleans files.
    This prevents multiple workers from cleaning the same files simultaneously.

    Args:
        interval_hours: How often to run cleanup (default: every 1 hour)
    """
    # Attempt to acquire distributed lock
    # Only ONE worker across all processes will succeed
    if not await acquire_cleanup_lock():
        # Lock acquisition already logged the skip message
        # Keep running but don't do anything - just monitor
        # If the lock holder dies, this worker can try to acquire on next check
        # Check every 5 minutes (lock TTL is 10 minutes, so 5 min is safe)
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes (reduced from 1 minute)
                if await acquire_cleanup_lock():
                    logger.info("[Cleanup] Lock acquired, this worker will now clean temp images")
                    break
            except asyncio.CancelledError:
                logger.info("[Cleanup] Cleanup scheduler monitor stopped")
                return
            except Exception:
                pass

    # This worker holds the lock - run the scheduler
    interval_seconds = interval_hours * 3600
    logger.info("Starting temp image cleanup scheduler (every %dh)", interval_hours)

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            # Refresh lock before cleanup to prevent expiration
            if not await refresh_cleanup_lock():
                logger.warning("[Cleanup] Lost cleanup lock, stopping scheduler on this worker")
                # Try to reacquire lock
                if not await acquire_cleanup_lock():
                    continue  # Another worker has it, keep waiting
                    # Lock reacquired, continue with cleanup

            await cleanup_temp_images()
        except asyncio.CancelledError:
            logger.info("[Cleanup] Cleanup scheduler stopped")
            break
        except Exception as e:
            logger.error("Cleanup scheduler error: %s", e, exc_info=True)
