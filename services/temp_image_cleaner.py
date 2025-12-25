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
_cleanup_lock_id: Optional[str] = None  # This worker's unique lock identifier


def _generate_cleanup_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def acquire_cleanup_lock() -> bool:
    """
    Attempt to acquire the cleanup lock.
    
    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.
    
    Returns:
        True if lock acquired (this worker should clean files)
        False if lock held by another worker
    """
    global _cleanup_lock_id
    
    try:
        from services.redis_client import get_redis, is_redis_available
    except ImportError:
        # Redis not available, assume single worker mode
        return True
    
    if not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[Cleanup] Redis unavailable, assuming single worker mode")
        return True
    
    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode
    
    try:
        # Generate unique ID for this worker
        if _cleanup_lock_id is None:
            _cleanup_lock_id = _generate_cleanup_lock_id()
        
        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        # Use asyncio.to_thread() to avoid blocking event loop
        acquired = await asyncio.to_thread(
            redis.set,
            CLEANUP_LOCK_KEY,
            _cleanup_lock_id,
            nx=True,  # Only set if not exists
            ex=CLEANUP_LOCK_TTL  # TTL in seconds
        )
        
        if acquired:
            logger.debug(f"[Cleanup] Lock acquired by this worker (id={_cleanup_lock_id})")
            return True
        else:
            # Lock held by another worker - check who
            holder = await asyncio.to_thread(redis.get, CLEANUP_LOCK_KEY)
            logger.info(f"[Cleanup] Another worker holds the cleanup lock (holder={holder}), skipping cleanup")
            return False
            
    except Exception as e:
        logger.warning(f"[Cleanup] Lock acquisition failed: {e}, proceeding anyway")
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
                        logger.debug(f"Deleted expired image: {file_path.name} (age: {file_age/3600:.1f}h)")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path.name}: {e}")
            except Exception as e:
                logger.error(f"Failed to stat {file_path.name}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Temp image cleanup: Deleted {deleted_count} expired files")
        else:
            logger.debug("Temp image cleanup: No expired files found")
            
        return deleted_count
        
    except Exception as e:
        logger.error(f"Temp image cleanup failed: {e}", exc_info=True)
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
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
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
    logger.info(f"Starting temp image cleanup scheduler (every {interval_hours}h)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cleanup_temp_images()
        except asyncio.CancelledError:
            logger.info("[Cleanup] Cleanup scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Cleanup scheduler error: {e}", exc_info=True)

