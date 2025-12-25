"""
Redis Cache Loader Service
==========================

Loads all users and organizations from SQLite into Redis cache at application startup.

Features:
- Pre-populates cache for fast lookups
- Handles errors gracefully (continues loading other data)
- Logs progress and statistics
- Uses Redis distributed lock to ensure only ONE worker loads cache

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

from services.redis_user_cache import get_user_cache
from services.redis_org_cache import get_org_cache
from services.redis_client import get_redis, is_redis_available
from config.database import SessionLocal
from models.auth import User, Organization

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
_worker_lock_id: Optional[str] = None  # This worker's unique lock identifier


def _generate_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


def acquire_cache_loader_lock() -> bool:
    """
    Attempt to acquire the cache loader lock.
    
    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.
    
    Returns:
        True if lock acquired (this worker should load cache)
        False if lock held by another worker
    """
    global _worker_lock_id
    
    if not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[CacheLoader] Redis unavailable, assuming single worker mode")
        return True
    
    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode
    
    try:
        # Generate unique ID for this worker
        if _worker_lock_id is None:
            _worker_lock_id = _generate_lock_id()
        
        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            CACHE_LOADER_LOCK_KEY,
            _worker_lock_id,
            nx=True,  # Only set if not exists
            ex=CACHE_LOADER_LOCK_TTL  # TTL in seconds
        )
        
        if acquired:
            logger.debug(f"[CacheLoader] Lock acquired by this worker (id={_worker_lock_id})")
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(CACHE_LOADER_LOCK_KEY)
            logger.info(f"[CacheLoader] Another worker holds the cache loader lock (holder={holder}), skipping cache load")
            return False
            
    except Exception as e:
        logger.warning(f"[CacheLoader] Lock acquisition failed: {e}, proceeding anyway")
        return True  # On error, proceed (better to have duplicate than no cache)


def release_cache_loader_lock() -> bool:
    """
    Release the cache loader lock if held by this worker.
    
    Uses Lua script to ensure we only release our own lock.
    This prevents accidentally releasing another worker's lock.
    
    Returns:
        True if lock released, False otherwise
    """
    global _worker_lock_id
    
    if not is_redis_available() or _worker_lock_id is None:
        return True
    
    redis = get_redis()
    if not redis:
        return True
    
    try:
        # Lua script: Only delete if lock value matches our lock_id
        # This ensures we only release our own lock
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        result = redis.eval(lua_script, 1, CACHE_LOADER_LOCK_KEY, _worker_lock_id)
        
        if result:
            logger.debug(f"[CacheLoader] Lock released (id={_worker_lock_id})")
            return True
        else:
            # Check current holder for logging
            current_holder = redis.get(CACHE_LOADER_LOCK_KEY)
            logger.debug(f"[CacheLoader] Lock not released (not held by us or already released). Current holder: {current_holder}")
            return False
            
    except Exception as e:
        logger.warning(f"[CacheLoader] Lock release failed: {e}")
        return False


def load_all_users_to_cache() -> Tuple[int, int]:
    """
    Load all users from SQLite into Redis cache.
    
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
        
        logger.info(f"[CacheLoader] Loading {total_count} users into cache...")
        
        success_count = 0
        error_count = 0
        
        for i, user in enumerate(users, 1):
            try:
                user_cache.cache_user(user)
                success_count += 1
                if i % 100 == 0 or i == total_count:
                    logger.debug(f"[CacheLoader] Cached user {i}/{total_count}: ID {user.id}")
            except Exception as e:
                error_count += 1
                logger.error(f"[CacheLoader] Failed to cache user ID {user.id}: {e}", exc_info=True)
                # Continue loading other users
        
        logger.info(f"[CacheLoader] Loaded {success_count}/{total_count} users into cache")
        if error_count > 0:
            logger.warning(f"[CacheLoader] {error_count} users failed to cache")
        
        return success_count, error_count
        
    except Exception as e:
        logger.error(f"[CacheLoader] Failed to load users from database: {e}", exc_info=True)
        return 0, 0
    finally:
        db.close()


def load_all_orgs_to_cache() -> Tuple[int, int]:
    """
    Load all organizations from SQLite into Redis cache.
    
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
        
        logger.info(f"[CacheLoader] Loading {total_count} organizations into cache...")
        
        success_count = 0
        error_count = 0
        
        for i, org in enumerate(orgs, 1):
            try:
                org_cache.cache_org(org)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"[CacheLoader] Failed to cache org ID {org.id}: {e}", exc_info=True)
                # Continue loading other orgs
        
        logger.info(f"[CacheLoader] Loaded {success_count}/{total_count} organizations into cache")
        if error_count > 0:
            logger.warning(f"[CacheLoader] {error_count} organizations failed to cache")
        
        return success_count, error_count
        
    except Exception as e:
        logger.error(f"[CacheLoader] Failed to load organizations from database: {e}", exc_info=True)
        return 0, 0
    finally:
        db.close()


def reload_cache_from_sqlite() -> bool:
    """
    Reload all users and organizations from SQLite into Redis cache.
    
    This function is called at application startup to pre-populate the cache.
    Uses Redis distributed lock to ensure only ONE worker loads the cache.
    
    Returns:
        True if reload completed successfully (even with some errors), False if critical failure
    """
    # Try to acquire lock - only one worker should load cache
    if not acquire_cache_loader_lock():
        # Another worker is loading cache, skip
        return True  # Return True since cache will be loaded by another worker
    
    start_time = time.time()
    
    logger.info("[CacheLoader] Starting cache reload from SQLite...")
    
    try:
        # Load users
        user_success, user_errors = load_all_users_to_cache()
        
        # Load organizations
        org_success, org_errors = load_all_orgs_to_cache()
        
        elapsed_time = time.time() - start_time
        
        total_success = user_success + org_success
        total_errors = user_errors + org_errors
        
        if total_errors > 0:
            logger.warning(f"[CacheLoader] Cache reload completed with {total_errors} errors")
        else:
            logger.info(f"[CacheLoader] Cache reload completed successfully")
        
        logger.info(
            f"[CacheLoader] Cache reload completed: {user_success} users, {org_success} orgs "
            f"in {elapsed_time:.2f}s"
        )
        
        # Return True if at least some data was loaded successfully
        return total_success > 0
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[CacheLoader] Cache reload failed after {elapsed_time:.2f}s: {e}", exc_info=True)
        return False
    finally:
        # Always release lock after cache loading completes (or fails)
        release_cache_loader_lock()


