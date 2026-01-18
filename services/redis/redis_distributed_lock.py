"""
Redis Distributed Lock Service
==============================

Reusable distributed lock service for preventing race conditions.
Uses Redis SETNX with TTL for atomic lock acquisition.

Features:
- Context manager pattern (`async with lock:`)
- Auto-release on timeout or exception
- Exponential backoff retry if lock is held
- Thread-safe and process-safe (works across multiple workers)

Key Schema:
- lock:{resource} -> String with lock holder ID (TTL: lock duration)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import uuid
import logging
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from services.redis.redis_client import is_redis_available, get_redis

logger = logging.getLogger(__name__)

# Lock configuration
DEFAULT_LOCK_TTL = 10  # seconds - enough for registration, auto-releases on crash
DEFAULT_MAX_RETRIES = 5  # Increased from 3 to match commit_user_with_retry retries
DEFAULT_RETRY_BASE_DELAY = 0.1  # seconds


def _generate_lock_id() -> str:
    """Generate unique lock ID for this process: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


class DistributedLock:
    """
    Redis-based distributed lock.

    Prevents race conditions when multiple processes/workers need exclusive access
    to a resource (e.g., phone number during registration).

    Usage:
        async with phone_registration_lock(phone):
            # Check phone uniqueness
            # Create user
            # Lock automatically released on exit
    """

    def __init__(
        self,
        resource: str,
        ttl: int = DEFAULT_LOCK_TTL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    ):
        """
        Initialize distributed lock.

        Args:
            resource: Resource identifier (e.g., phone number)
            ttl: Lock TTL in seconds (auto-releases after this time)
            max_retries: Maximum retry attempts if lock is held
            retry_base_delay: Base delay for exponential backoff (seconds)
        """
        self.resource = resource
        self.lock_key = f"lock:{resource}"
        self.ttl = ttl
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.lock_id: Optional[str] = None
        self._acquired = False

    async def acquire(self) -> bool:
        """
        Attempt to acquire the lock.

        Returns:
            True if lock acquired, False if max retries exhausted
        """
        if not is_redis_available():
            logger.warning(
                "[DistributedLock] Redis unavailable, assuming single worker mode for %s",
                self.resource
            )
            return True  # Fallback: assume single worker if Redis unavailable

        redis = get_redis()
        if not redis:
            logger.warning(
                "[DistributedLock] Redis client unavailable, assuming single worker mode for %s",
                self.resource
            )
            return True

        # Generate unique lock ID for this process
        if self.lock_id is None:
            self.lock_id = _generate_lock_id()

        for attempt in range(self.max_retries):
            try:
                # Attempt atomic lock acquisition: SETNX with TTL
                # Returns True only if key did not exist (lock acquired)
                # Use asyncio.to_thread() to avoid blocking event loop (Redis client is synchronous)
                acquired = await asyncio.to_thread(
                    redis.set,
                    self.lock_key,
                    self.lock_id,
                    nx=True,  # Only set if not exists
                    ex=self.ttl  # TTL in seconds
                )

                if acquired:
                    self._acquired = True
                    logger.debug(
                        "[DistributedLock] Lock acquired for %s (id=%s)",
                        self.resource,
                        self.lock_id
                    )
                    return True
                else:
                    # Lock held by another process - check who
                    holder = await asyncio.to_thread(redis.get, self.lock_key)
                    if attempt < self.max_retries - 1:
                        # Retry with exponential backoff
                        delay = self.retry_base_delay * (2 ** attempt)
                        logger.debug(
                            "[DistributedLock] Lock held for %s "
                            "(holder=%s, attempt %s/%s), "
                            "retrying after %.2fs",
                            self.resource,
                            holder,
                            attempt + 1,
                            self.max_retries,
                            delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # All retries exhausted
                        logger.warning(
                            "[DistributedLock] Failed to acquire lock for %s "
                            "after %s attempts (holder=%s)",
                            self.resource,
                            self.max_retries,
                            holder
                        )
                        return False

            except Exception as e:
                logger.warning(
                    "[DistributedLock] Lock acquisition error for %s: %s",
                    self.resource,
                    e
                )
                # On error, assume single worker mode (fail open)
                return True

        return False

    async def release(self) -> bool:
        """
        Release the lock if held by this process.

        Uses Lua script to ensure we only release our own lock.
        This prevents accidentally releasing another process's lock.

        Returns:
            True if lock released, False otherwise
        """
        if not self._acquired or not self.lock_id:
            return False

        if not is_redis_available():
            return False

        redis = get_redis()
        if not redis:
            return False

        try:
            # Lua script: Only delete if lock value matches our lock_id
            # This ensures we only release our own lock
            # Use asyncio.to_thread() to avoid blocking event loop (Redis client is synchronous)
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """

            result = await asyncio.to_thread(redis.eval, lua_script, 1, self.lock_key, self.lock_id)

            if result:
                self._acquired = False
                logger.debug(
                    "[DistributedLock] Lock released for %s (id=%s)",
                    self.resource,
                    self.lock_id
                )
                return True
            else:
                # Check current holder for logging
                current_holder = await asyncio.to_thread(redis.get, self.lock_key)
                logger.warning(
                    "[DistributedLock] Lock not released (not held by us or already released): %s. "
                    "Current holder: %s",
                    self.resource,
                    current_holder
                )
                return False

        except Exception as e:
            logger.warning(
                "[DistributedLock] Lock release error for %s: %s",
                self.resource,
                e
            )
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Failed to acquire distributed lock for {self.resource}")
        return self

    async def __aexit__(self, exc_type, _exc_val, _exc_tb):
        """Async context manager exit - always release lock."""
        await self.release()
        return False  # Don't suppress exceptions


@asynccontextmanager
async def phone_registration_lock(phone: str):
    """
    Context manager for phone registration lock.

    Prevents race conditions when two users register with same phone simultaneously.

    Usage:
        async with phone_registration_lock(phone):
            # Check phone uniqueness
            # Create user
            # Lock automatically released on exit

    Args:
        phone: Phone number to lock

    Raises:
        RuntimeError: If lock cannot be acquired after retries
    """
    lock = DistributedLock(
        resource=f"register:phone:{phone}",
        ttl=DEFAULT_LOCK_TTL,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_base_delay=DEFAULT_RETRY_BASE_DELAY
    )

    async with lock:
        yield lock
