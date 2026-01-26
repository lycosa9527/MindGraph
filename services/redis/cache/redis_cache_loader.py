"""
Redis Cache Loader Service
==========================

Loads all users and organizations from database into Redis cache at application startup.

Features:
- Pre-populates cache for fast lookups
- Handles errors gracefully (continues loading other data)
- Logs progress and statistics
- Uses Redis distributed lock to ensure only ONE worker loads cache
- Database-agnostic (works with PostgreSQL, etc.)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import time
import os
import uuid
from typing import Tuple, Optional

from services.redis.cache.redis_user_cache import get_user_cache
from services.redis.cache.redis_org_cache import get_org_cache
from services.redis.redis_client import get_redis, is_redis_available
from config.database import SessionLocal
from models.domain.auth import User, Organization

logger = logging.getLogger(__name__)

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to run cache loaders.
#
# Solution: Redis-based distributed lock ensures only ONE worker loads cache.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: cache:loader:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 5 minutes (enough for cache loading, auto-release if worker crashes)
# ============================================================================

CACHE_LOADER_LOCK_KEY = "cache:loader:lock"
CACHE_LOADER_LOCK_TTL = 300  # 5 minutes - enough for cache loading, auto-release on crash


class _LockIdManager:
    """Manages the worker lock ID to avoid global variables."""
    _lock_id: Optional[str] = None

    @classmethod
    def get_lock_id(cls) -> str:
        """Get or generate the lock ID for this worker."""
        if cls._lock_id is None:
            cls._lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        return cls._lock_id

    @classmethod
    def has_lock_id(cls) -> bool:
        """Check if lock ID has been generated."""
        return cls._lock_id is not None


def is_cache_loading_in_progress() -> bool:
    """
    Check if cache loading is already in progress by another worker.

    Returns:
        True if lock exists (another worker is loading), False otherwise
    """
    if not is_redis_available():
        return False

    redis = get_redis()
    if not redis:
        return False

    try:
        return redis.exists(CACHE_LOADER_LOCK_KEY) > 0
    except Exception:
        return False


def acquire_cache_loader_lock() -> bool:
    """
    Attempt to acquire the cache loader lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should load cache)
        False if lock held by another worker
    """
    if not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[CacheLoader] Redis unavailable, assuming single worker mode")
        return True

    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode

    try:
        # Generate unique ID for this worker
        worker_lock_id = _LockIdManager.get_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            CACHE_LOADER_LOCK_KEY,
            worker_lock_id,
            nx=True,  # Only set if not exists
            ex=CACHE_LOADER_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.debug("[CacheLoader] Lock acquired by this worker (id=%s)", worker_lock_id)
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(CACHE_LOADER_LOCK_KEY)
            logger.debug(
                "[CacheLoader] Another worker holds the cache loader lock "
                "(holder=%s), skipping cache load",
                holder
            )
            return False  # Return False to indicate lock not acquired

    except Exception as e:
        logger.warning("[CacheLoader] Lock acquisition failed: %s, proceeding anyway", e)
        return True  # On error, proceed (better to have duplicate than no cache)


def release_cache_loader_lock() -> bool:
    """
    Release the cache loader lock if held by this worker.

    Uses Lua script to ensure we only release our own lock.
    This prevents accidentally releasing another worker's lock.

    Returns:
        True if lock released, False otherwise
    """
    if not is_redis_available() or not _LockIdManager.has_lock_id():
        return True

    redis = get_redis()
    if not redis:
        return True

    try:
        worker_lock_id = _LockIdManager.get_lock_id()

        # Lua script: Only delete if lock value matches our lock_id
        # This ensures we only release our own lock
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        result = redis.eval(lua_script, 1, CACHE_LOADER_LOCK_KEY, worker_lock_id)

        if result:
            logger.debug("[CacheLoader] Lock released (id=%s)", worker_lock_id)
            return True
        else:
            # Check current holder for logging
            current_holder = redis.get(CACHE_LOADER_LOCK_KEY)
            logger.debug(
                "[CacheLoader] Lock not released (not held by us or already released). "
                "Current holder: %s",
                current_holder
            )
            return False

    except Exception as e:
        logger.warning("[CacheLoader] Lock release failed: %s", e)
        return False


def load_all_users_to_cache() -> Tuple[int, int]:
    """
    Load all users from database into Redis cache.

    Returns:
        Tuple of (success_count, error_count)
    """
    user_cache = get_user_cache()
    db = SessionLocal()

    try:
        users = db.query(User).all()
        total_count = len(users)

        if total_count == 0:
            logger.info("[CacheLoader] No users to load")
            return 0, 0

        logger.info("[CacheLoader] Loading %d users into cache...", total_count)

        success_count = 0
        error_count = 0

        for user in users:
            try:
                user_cache.cache_user(user)
                success_count += 1
                if success_count % 100 == 0 or success_count == total_count:
                    logger.debug(
                        "[CacheLoader] Cached user %d/%d: ID %s",
                        success_count,
                        total_count,
                        user.id
                    )
            except Exception as e:
                error_count += 1
                logger.error(
                    "[CacheLoader] Failed to cache user ID %s: %s",
                    user.id,
                    e,
                    exc_info=True
                )
                # Continue loading other users

        logger.info(
            "[CacheLoader] Loaded %d/%d users into cache",
            success_count,
            total_count
        )
        if error_count > 0:
            logger.warning("[CacheLoader] %d users failed to cache", error_count)

        return success_count, error_count

    except Exception as e:
        logger.error("[CacheLoader] Failed to load users from database: %s", e, exc_info=True)
        return 0, 0
    finally:
        db.close()


def load_all_orgs_to_cache() -> Tuple[int, int]:
    """
    Load all organizations from database into Redis cache.

    Returns:
        Tuple of (success_count, error_count)
    """
    org_cache = get_org_cache()
    db = SessionLocal()

    try:
        orgs = db.query(Organization).all()
        total_count = len(orgs)

        if total_count == 0:
            logger.info("[CacheLoader] No organizations to load")
            return 0, 0

        logger.info("[CacheLoader] Loading %d organizations into cache...", total_count)

        success_count = 0
        error_count = 0

        for org in orgs:
            try:
                org_cache.cache_org(org)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(
                    "[CacheLoader] Failed to cache org ID %s: %s",
                    org.id,
                    e,
                    exc_info=True
                )
                # Continue loading other orgs

        logger.info(
            "[CacheLoader] Loaded %d/%d organizations into cache",
            success_count,
            total_count
        )
        if error_count > 0:
            logger.warning("[CacheLoader] %d organizations failed to cache", error_count)

        return success_count, error_count

    except Exception as e:
        logger.error(
            "[CacheLoader] Failed to load organizations from database: %s",
            e,
            exc_info=True
        )
        return 0, 0
    finally:
        db.close()


def reload_cache_from_database() -> bool:
    """
    Reload all users and organizations from database into Redis cache.

    This function is called at application startup to pre-populate the cache.
    Uses Redis distributed lock to ensure only ONE worker loads the cache.
    Database-agnostic: works with PostgreSQL or any SQLAlchemy-supported database.

    Returns:
        True if reload completed successfully (even with some errors), False if critical failure
    """
    # Check if Redis is available first
    if not is_redis_available():
        logger.warning("[CacheLoader] Redis is not available - cannot load cache. Cache will be populated on-demand.")
        return False

    # Try to acquire lock - only one worker should load cache
    if not acquire_cache_loader_lock():
        # Another worker is loading cache, skip
        # Use DEBUG level since this is expected behavior in multi-worker setups
        logger.debug("[CacheLoader] Another worker is loading cache, skipping (cache will be loaded by that worker)")
        return True  # Return True since cache will be loaded by another worker

    start_time = time.time()

    logger.info("[CacheLoader] Starting cache reload from database...")

    try:
        # Load users
        user_success, user_errors = load_all_users_to_cache()

        # Load organizations
        org_success, org_errors = load_all_orgs_to_cache()

        elapsed_time = time.time() - start_time

        total_success = user_success + org_success
        total_errors = user_errors + org_errors

        if total_errors > 0:
            logger.warning("[CacheLoader] Cache reload completed with %d errors", total_errors)
        else:
            logger.info("[CacheLoader] Cache reload completed successfully")

        logger.info(
            "[CacheLoader] Cache reload completed: %d users, %d orgs in %.2fs",
            user_success,
            org_success,
            elapsed_time
        )

        # Return True if at least some data was loaded successfully
        return total_success > 0

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(
            "[CacheLoader] Cache reload failed after %.2fs: %s",
            elapsed_time,
            e,
            exc_info=True
        )
        return False
    finally:
        # Always release lock after cache loading completes (or fails)
        release_cache_loader_lock()
