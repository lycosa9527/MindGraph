"""
Redis Rate Limiter
==================

High-performance rate limiting using Redis sliding window algorithm.
Shared across all workers for accurate rate limiting.

Features:
- Sliding window algorithm (accurate, no burst exploitation)
- Atomic operations (no race conditions)
- Shared across all workers (accurate counting)
- Automatic expiry (no cleanup needed)
- Graceful fallback to in-memory

Key Schema:
- rate:{category}:{identifier} -> sorted set {timestamp: score}

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import time
import logging
from typing import Tuple, Dict, List, Optional
from collections import defaultdict

from services.redis.redis_client import is_redis_available, get_redis

logger = logging.getLogger(__name__)

# Key prefix
RATE_PREFIX = "rate:"


class RedisRateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Uses Redis sorted sets for O(log N) operations with automatic expiry.
    Falls back to per-worker in-memory storage if Redis is unavailable.

    Thread-safe: All operations are atomic Redis commands.
    """

    def __init__(self):
        # In-memory fallback for when Redis is disabled
        self._memory_store: Dict[str, List[float]] = defaultdict(list)

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def check_and_record(
        self,
        category: str,
        identifier: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[bool, int, str]:
        """
        Check rate limit and record attempt atomically.

        Uses sliding window: counts all attempts in the last window_seconds.

        Args:
            category: Rate limit category (login, captcha, ip, etc.)
            identifier: Unique identifier (phone, IP, session, etc.)
            max_attempts: Maximum attempts allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, attempt_count, error_message)
        """
        if self._use_redis():
            return self._redis_check_and_record(
                category, identifier, max_attempts, window_seconds
            )
        else:
            return self._memory_check_and_record(
                category, identifier, max_attempts, window_seconds
            )

    def _redis_check_and_record(
        self,
        category: str,
        identifier: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[bool, int, str]:
        """Check rate limit using Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_check_and_record(
                category, identifier, max_attempts, window_seconds
            )

        try:
            key = f"{RATE_PREFIX}{category}:{identifier}"
            now = time.time()
            window_start = now - window_seconds

            # Atomic pipeline: cleanup old entries, add current, count, set expiry
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
            pipe.zadd(key, {str(now): now})              # Add current attempt
            pipe.zcard(key)                               # Count entries
            pipe.expire(key, window_seconds)              # Set expiry
            results = pipe.execute()

            count = results[2]

            if count > max_attempts:
                # Calculate wait time
                oldest = redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    wait_seconds = int(oldest[0][1] + window_seconds - now) + 1
                    minutes = (wait_seconds // 60) + 1
                    error_msg = (
                        f"Too many attempts ({count} in {window_seconds//60} minutes). "
                        f"Please try again in {minutes} minute{'s' if minutes > 1 else ''}."
                    )
                else:
                    error_msg = "Too many attempts. Please try again later."

                logger.warning(
                    "[RateLimiter] Limit exceeded: %s:%s (%s/%s)",
                    category, identifier, count, max_attempts
                )
                return False, count, error_msg

            return True, count, ""

        except Exception as e:
            logger.error("[RateLimiter] Redis error: %s", e)
            return self._memory_check_and_record(
                category, identifier, max_attempts, window_seconds
            )

    def _memory_check_and_record(
        self,
        category: str,
        identifier: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[bool, int, str]:
        """Check rate limit using in-memory storage (fallback)."""
        key = f"{category}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries and add current
        self._memory_store[key] = [t for t in self._memory_store[key] if t > window_start]
        self._memory_store[key].append(now)

        count = len(self._memory_store[key])

        if count > max_attempts:
            oldest = min(self._memory_store[key])
            wait_seconds = int(oldest + window_seconds - now) + 1
            minutes = (wait_seconds // 60) + 1
            error_msg = (
                f"Too many attempts ({count} in {window_seconds//60} minutes). "
                f"Please try again in {minutes} minute{'s' if minutes > 1 else ''}."
            )
            logger.warning(
                "[RateLimiter] (memory) Limit exceeded: %s (%s/%s)",
                key, count, max_attempts
            )
            return False, count, error_msg

        return True, count, ""

    def clear(self, category: str, identifier: str) -> bool:
        """
        Clear rate limit for identifier (e.g., on successful login).

        Args:
            category: Rate limit category
            identifier: Unique identifier

        Returns:
            True if cleared, False on error
        """
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    key = f"{RATE_PREFIX}{category}:{identifier}"
                    redis.delete(key)
                    return True
                except Exception as e:
                    logger.error("[RateLimiter] Redis clear error: %s", e)

        # Fallback to memory
        key = f"{category}:{identifier}"
        if key in self._memory_store:
            del self._memory_store[key]
        return True

    def get_remaining(
        self,
        category: str,
        identifier: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[int, int]:
        """
        Get remaining attempts and time until reset.

        Args:
            category: Rate limit category
            identifier: Unique identifier
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (remaining_attempts, seconds_until_reset)
        """
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    key = f"{RATE_PREFIX}{category}:{identifier}"
                    now = time.time()
                    window_start = now - window_seconds

                    # Clean and count
                    pipe = redis.pipeline()
                    pipe.zremrangebyscore(key, 0, window_start)
                    pipe.zcard(key)
                    pipe.zrange(key, 0, 0, withscores=True)
                    results = pipe.execute()

                    count = results[1] or 0
                    remaining = max(0, max_attempts - count)

                    reset_seconds = 0
                    if count > 0 and results[2]:
                        oldest_time = results[2][0][1]
                        reset_seconds = int(oldest_time + window_seconds - now)

                    return remaining, max(0, reset_seconds)

                except Exception as e:
                    logger.error("[RateLimiter] Redis error: %s", e)

        # Fallback to memory
        key = f"{category}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        self._memory_store[key] = [t for t in self._memory_store.get(key, []) if t > window_start]
        count = len(self._memory_store[key])
        remaining = max(0, max_attempts - count)

        reset_seconds = 0
        if self._memory_store[key]:
            oldest = min(self._memory_store[key])
            reset_seconds = int(oldest + window_seconds - now)

        return remaining, max(0, reset_seconds)


# Singleton instance holder
class _RateLimiterHolder:
    """Holder for singleton rate limiter instance."""
    _instance: Optional[RedisRateLimiter] = None

    @classmethod
    def get_instance(cls) -> RedisRateLimiter:
        """Get or create singleton rate limiter instance."""
        if cls._instance is None:
            cls._instance = RedisRateLimiter()
        return cls._instance


def get_rate_limiter() -> RedisRateLimiter:
    """Get or create global rate limiter instance."""
    return _RateLimiterHolder.get_instance()


# ============================================================================
# Convenience Functions (for backwards compatibility with utils/auth.py)
# ============================================================================

# Default configuration
DEFAULT_MAX_LOGIN_ATTEMPTS = 10
DEFAULT_MAX_CAPTCHA_ATTEMPTS = 30
DEFAULT_WINDOW_MINUTES = 15


def check_login_rate_limit(phone: str) -> Tuple[bool, str]:
    """Check login rate limit for phone number."""
    limiter = get_rate_limiter()
    allowed, _, error = limiter.check_and_record(
        "login", phone, DEFAULT_MAX_LOGIN_ATTEMPTS, DEFAULT_WINDOW_MINUTES * 60
    )
    return allowed, error


def check_ip_rate_limit(ip: str) -> Tuple[bool, str]:
    """Check login rate limit for IP address."""
    limiter = get_rate_limiter()
    # IP limit is 2x phone limit
    allowed, _, error = limiter.check_and_record(
        "ip", ip, DEFAULT_MAX_LOGIN_ATTEMPTS * 2, DEFAULT_WINDOW_MINUTES * 60
    )
    return allowed, error


def check_captcha_rate_limit(identifier: str) -> Tuple[bool, str]:
    """Check captcha verification rate limit."""
    limiter = get_rate_limiter()
    allowed, _, error = limiter.check_and_record(
        "captcha", identifier, DEFAULT_MAX_CAPTCHA_ATTEMPTS, DEFAULT_WINDOW_MINUTES * 60
    )
    return allowed, error


def clear_login_attempts(phone: str):
    """Clear login attempts on successful login."""
    limiter = get_rate_limiter()
    limiter.clear("login", phone)


def clear_ip_attempts(ip: str):
    """Clear IP attempts on successful login."""
    limiter = get_rate_limiter()
    limiter.clear("ip", ip)


def clear_captcha_attempts(identifier: str):
    """Clear captcha attempts on successful verification."""
    limiter = get_rate_limiter()
    limiter.clear("captcha", identifier)


def get_login_attempts_remaining(phone: str) -> int:
    """
    Get remaining login attempts for a phone number.

    Returns:
        Number of attempts remaining before rate limit hit
    """
    limiter = get_rate_limiter()
    remaining, _ = limiter.get_remaining(
        "login", phone, DEFAULT_MAX_LOGIN_ATTEMPTS, DEFAULT_WINDOW_MINUTES * 60
    )
    return remaining


def get_attempt_count(category: str, identifier: str, max_attempts: int, window_minutes: int) -> int:
    """
    Get current attempt count for an identifier.

    Returns:
        Number of attempts made in the current window
    """
    limiter = get_rate_limiter()
    remaining, _ = limiter.get_remaining(
        category, identifier, max_attempts, window_minutes * 60
    )
    return max_attempts - remaining
