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

from services.redis import keys as _keys
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

# Lock configuration sourced from central registry.
DEFAULT_LOCK_TTL = _keys.TTL_LOCK_DEFAULT
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
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
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
        self.lock_key = _keys.LOCK.format(resource=resource)
        self.ttl = ttl
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.lock_id: Optional[str] = None
        self._acquired = False

    async def acquire(self) -> bool:
        """Attempt to acquire the lock via the shared async Redis pool.

        Returns:
            True if lock acquired, False if max retries exhausted.
        """
        if not is_redis_available():
            logger.warning(
                "[DistributedLock] Redis unavailable, assuming single worker mode for %s",
                self.resource,
            )
            return True  # Fail-open: single-worker fallback when Redis is gone.

        redis = get_async_redis()
        if self.lock_id is None:
            self.lock_id = _generate_lock_id()

        for attempt in range(self.max_retries):
            try:
                acquired = await redis.set(
                    self.lock_key,
                    self.lock_id,
                    nx=True,
                    ex=self.ttl,
                )

                if acquired:
                    self._acquired = True
                    logger.debug(
                        "[DistributedLock] Lock acquired for %s (id=%s)",
                        self.resource,
                        self.lock_id,
                    )
                    return True

                holder = await redis.get(self.lock_key)
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2**attempt)
                    logger.debug(
                        "[DistributedLock] Lock held for %s (holder=%s, attempt %s/%s), retrying after %.2fs",
                        self.resource,
                        holder,
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.warning(
                    "[DistributedLock] Failed to acquire lock for %s after %s attempts (holder=%s)",
                    self.resource,
                    self.max_retries,
                    holder,
                )
                return False

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[DistributedLock] Lock acquisition error for %s: %s",
                    self.resource,
                    exc,
                )
                return True  # Fail-open as before to avoid wedging callers.

        return False

    async def release(self) -> bool:
        """Release the lock if held by this process (atomic compare-and-delete)."""
        if not self._acquired or not self.lock_id:
            return False

        if not is_redis_available():
            return False

        try:
            result = await AsyncRedisOps.compare_and_delete(self.lock_key, self.lock_id)
            if result:
                self._acquired = False
                logger.debug(
                    "[DistributedLock] Lock released for %s (id=%s)",
                    self.resource,
                    self.lock_id,
                )
                return True

            current_holder = await get_async_redis().get(self.lock_key)
            logger.warning(
                "[DistributedLock] Lock not released (not held by us or already released): %s. Current holder: %s",
                self.resource,
                current_holder,
            )
            return False

        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[DistributedLock] Lock release error for %s: %s", self.resource, exc)
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


STARTUP_SMS_NOTIFICATION_LOCK_KEY = _keys.LOCK_STARTUP_SMS
STARTUP_SMS_NOTIFICATION_LOCK_TTL = _keys.TTL_LOCK_STARTUP


async def acquire_startup_sms_notification_lock() -> Optional[str]:
    """
    Acquire exclusive right to send startup SMS for this process group.

    Uvicorn does not set UVICORN_WORKER_ID; all workers default to the same id,
    so each would otherwise send duplicate SMS. Uses Redis SET NX (see also
    backup scheduler lock pattern).

    Returns:
        Lock token to pass to release_startup_sms_notification_lock, or None
        if another worker holds the lock or coordination failed (prefer no SMS
        over duplicate SMS when Redis errors).
    """
    if not is_redis_available():
        return None

    redis = get_async_redis()
    lock_id = _generate_lock_id()
    try:
        acquired = await redis.set(
            STARTUP_SMS_NOTIFICATION_LOCK_KEY,
            lock_id,
            nx=True,
            ex=STARTUP_SMS_NOTIFICATION_LOCK_TTL,
        )
        if acquired:
            return lock_id
        holder = await redis.get(STARTUP_SMS_NOTIFICATION_LOCK_KEY)
        logger.debug(
            "[LIFESPAN] Startup SMS skipped — lock held by another worker (%s)",
            holder,
        )
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "[LIFESPAN] Startup SMS lock acquisition failed (skipping send): %s",
            exc,
        )
        return None


async def release_startup_sms_notification_lock(lock_id: str) -> None:
    """Release startup SMS lock so a quick restart can notify again."""
    if not lock_id:
        return
    if not is_redis_available():
        return
    try:
        await AsyncRedisOps.compare_and_delete(STARTUP_SMS_NOTIFICATION_LOCK_KEY, lock_id)
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug(
            "[LIFESPAN] Startup SMS lock release (non-critical): %s",
            exc,
        )


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
        retry_base_delay=DEFAULT_RETRY_BASE_DELAY,
    )

    async with lock:
        yield lock
