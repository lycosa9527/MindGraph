"""
Redis Client Service
====================

Centralized Redis connection management for MindGraph.

Redis is REQUIRED. MindGraph uses PostgreSQL + Redis architecture:
- PostgreSQL: Persistent data (users, organizations, token history)
- Redis: Ephemeral data (captcha, rate limiting, sessions, buffers)

Configuration via environment variables:
- REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)

If Redis connection fails, the application will NOT start.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import time
import logging
from typing import Optional, Any, Dict, List, Callable, TypeVar

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment, misc]

from functools import wraps

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar('T')


class _RedisState:
    """Manages Redis connection state to avoid global variables."""
    _available = False
    _client: Optional[Any] = None

    @classmethod
    def set_client(cls, client: Any) -> None:
        """Set the Redis client."""
        cls._client = client
        cls._available = True

    @classmethod
    def clear_client(cls) -> None:
        """Clear the Redis client."""
        cls._client = None
        cls._available = False

    @classmethod
    def get_client(cls) -> Optional[Any]:
        """Get the Redis client."""
        return cls._client

    @classmethod
    def is_available(cls) -> bool:
        """Check if Redis is available."""
        return cls._available

# Error message width
_ERROR_WIDTH = 70

# Retry configuration
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 0.1  # seconds


def _with_retry(operation_name: str, default_return: Any = None):
    """
    Decorator for Redis operations with retry logic.

    Retries on transient connection/timeout errors with exponential backoff.
    Only retries on redis.ConnectionError and redis.TimeoutError.

    Args:
        operation_name: Name for logging (e.g., "SET", "GET")
        default_return: Value to return after all retries fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if redis is None:
                return default_return

            last_error = None
            for attempt in range(_RETRY_MAX_ATTEMPTS):
                try:
                    return func(*args, **kwargs)
                except (redis.ConnectionError, redis.TimeoutError) as e:  # type: ignore[attr-defined]
                    last_error = e
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        time.sleep(delay)
                        logger.debug(
                            "[Redis] %s retry %d/%d after %.1fs",
                            operation_name,
                            attempt + 1,
                            _RETRY_MAX_ATTEMPTS,
                            delay
                        )
                except Exception as e:
                    # Non-retryable error (data type mismatch, etc.)
                    logger.warning("[Redis] %s failed: %s", operation_name, e)
                    return default_return

            # All retries exhausted
            logger.warning(
                "[Redis] %s failed after %d retries: %s",
                operation_name,
                _RETRY_MAX_ATTEMPTS,
                last_error
            )
            return default_return
        return wrapper
    return decorator


def _log_redis_error(title: str, details: List[str]) -> None:
    """
    Log a Redis error with clean, professional formatting.

    Args:
        title: Error title (e.g., "REDIS CONNECTION FAILED")
        details: List of detail lines to display
    """
    separator = "=" * _ERROR_WIDTH

    lines = [
        "",
        separator,
        title.center(_ERROR_WIDTH),
        separator,
        "",
    ]
    lines.extend(details)
    lines.extend(["", separator, ""])

    error_msg = "\n".join(lines)
    logger.critical(error_msg)


class RedisConnectionError(Exception):
    """Raised when Redis connection fails during operation."""


class RedisStartupError(Exception):
    """
    Raised when Redis connection fails during startup.

    This is a controlled startup failure - the error message has already
    been logged with instructions. Catching this exception should exit
    cleanly without logging additional tracebacks.
    """


def _get_redis_config() -> Dict[str, Any]:
    """Get Redis configuration from environment."""
    return {
        'url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '50')),
        'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
        'socket_connect_timeout': int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
        'retry_on_timeout': os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true',
    }


def init_redis_sync() -> bool:
    """
    Initialize Redis connection (synchronous version for startup).

    Redis is REQUIRED. Application will exit if connection fails.

    Returns:
        True if Redis is available.

    Raises:
        SystemExit: Application will exit if Redis is unavailable.
    """
    config = _get_redis_config()
    redis_url = config['url']

    logger.info("[Redis] Connecting to %s...", redis_url)

    if redis is None:
        _log_redis_error(
            title="REDIS PACKAGE NOT INSTALLED",
            details=[
                "The 'redis' package is required but not installed.",
                "",
                "To fix, run:",
                "  pip install redis>=5.0.0",
            ]
        )
        raise RedisStartupError("Redis package not installed") from None

    try:
        redis_client = redis.from_url(  # type: ignore[attr-defined]
            redis_url,
            encoding='utf-8',
            decode_responses=True,
            max_connections=config['max_connections'],
            socket_timeout=config['socket_timeout'],
            socket_connect_timeout=config['socket_connect_timeout'],
            retry_on_timeout=config['retry_on_timeout'],
        )

        # Test connection
        redis_client.ping()

        # Get server info
        info = redis_client.info("server")
        redis_version = info.get("redis_version", "unknown")

        _RedisState.set_client(redis_client)
        logger.info("[Redis] Connected successfully (version: %s)", redis_version)
        return True

    except Exception as exc:
        _log_redis_error(
            title="REDIS CONNECTION FAILED",
            details=[
                f"Failed to connect to Redis at: {redis_url}",
                f"Error: {exc}",
                "",
                "MindGraph requires Redis. Please ensure Redis is running:",
                "",
                "  Ubuntu:  sudo apt install redis-server",
                "           sudo systemctl start redis-server",
                "",
                "  macOS:   brew install redis && brew services start redis",
                "",
                "Then set REDIS_URL in your .env file (default: redis://localhost:6379/0)",
            ]
        )
        raise RedisStartupError(f"Failed to connect to Redis: {exc}") from exc


def close_redis_sync():
    """Close Redis connection gracefully (synchronous)."""
    redis_client = _RedisState.get_client()
    if redis_client:
        try:
            redis_client.close()
            logger.info("[Redis] Connection closed")
        except Exception as e:
            logger.warning("[Redis] Error closing connection: %s", e)

    _RedisState.clear_client()


def is_redis_available() -> bool:
    """Check if Redis is available. Always True after successful init."""
    return _RedisState.is_available()


def get_redis():
    """
    Get Redis client instance.

    Returns:
        Redis client (never None after init_redis_sync succeeds)
    """
    return _RedisState.get_client()


def get_redis_mode() -> str:
    """Get current Redis mode. Always 'external' (Redis required)."""
    return 'external'


class RedisOperations:
    """
    High-level Redis operations with error handling and retry logic.

    Thread-safe: Uses synchronous Redis client.
    Retry: Transient connection/timeout errors are retried with exponential backoff.
    """

    @staticmethod
    @_with_retry("SET", default_return=False)
    def set_with_ttl(key: str, value: str, ttl_seconds: int) -> bool:
        """Set a key with TTL. Returns True on success."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.setex(key, ttl_seconds, value)
        return True

    @staticmethod
    @_with_retry("GET", default_return=None)
    def get(key: str) -> Optional[str]:
        """Get a key value. Returns None if not found or on error."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return None
        return redis_client.get(key)

    @staticmethod
    @_with_retry("DELETE", default_return=False)
    def delete(key: str) -> bool:
        """Delete a key. Returns True on success."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.delete(key)
        return True

    @staticmethod
    @_with_retry("GET+DELETE", default_return=None)
    def get_and_delete(key: str) -> Optional[str]:
        """Atomically get and delete a key using pipeline."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            logger.debug("[Redis] get_and_delete: Redis unavailable for key: %s", key)
            return None
        try:
            pipe = redis_client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            results = pipe.execute()
            # results[0] is the GET result (None if key doesn't exist, string if exists)
            # results[1] is the DELETE result (number of keys deleted)
            return results[0] if results else None
        except Exception as e:
            logger.warning("[Redis] get_and_delete failed for key %s: %s", key, e)
            return None

    @staticmethod
    @_with_retry("INCR", default_return=None)
    def increment(key: str, ttl_seconds: Optional[int] = None) -> Optional[int]:
        """Increment a counter. Optionally set TTL on first increment."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return None
        pipe = redis_client.pipeline()
        pipe.incr(key)
        if ttl_seconds:
            pipe.expire(key, ttl_seconds, nx=True)
        results = pipe.execute()
        return results[0]

    @staticmethod
    @_with_retry("INCRBYFLOAT", default_return=None)
    def increment_float(key: str, amount: float, ttl_seconds: Optional[int] = None) -> Optional[float]:
        """Increment a float counter by amount. Optionally set TTL on first increment."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return None
        pipe = redis_client.pipeline()
        pipe.incrbyfloat(key, amount)
        if ttl_seconds:
            pipe.expire(key, ttl_seconds, nx=True)
        results = pipe.execute()
        return results[0]

    @staticmethod
    @_with_retry("TTL", default_return=-2)
    def get_ttl(key: str) -> int:
        """Get remaining TTL of a key. Returns -1 if no TTL, -2 if key doesn't exist."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return -2
        return redis_client.ttl(key)

    @staticmethod
    @_with_retry("EXPIRE", default_return=False)
    def set_ttl(key: str, ttl_seconds: int) -> bool:
        """Set TTL on existing key."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.expire(key, ttl_seconds)
        return True

    @staticmethod
    @_with_retry("EXISTS", default_return=False)
    def exists(key: str) -> bool:
        """Check if key exists."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        return redis_client.exists(key) > 0

    # ========================================================================
    # List Operations (for buffers, queues)
    # ========================================================================

    @staticmethod
    @_with_retry("RPUSH", default_return=False)
    def list_push(key: str, value: str) -> bool:
        """Push value to end of list (RPUSH)."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.rpush(key, value)
        return True

    @staticmethod
    @_with_retry("LRANGE+LTRIM", default_return=[])
    def list_pop_many(key: str, count: int) -> List[str]:
        """Atomically pop up to count items from start of list."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return []
        pipe = redis_client.pipeline()
        pipe.lrange(key, 0, count - 1)
        pipe.ltrim(key, count, -1)
        results = pipe.execute()
        return results[0] or []

    @staticmethod
    @_with_retry("LLEN", default_return=0)
    def list_length(key: str) -> int:
        """Get list length."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return 0
        return redis_client.llen(key) or 0

    @staticmethod
    @_with_retry("LRANGE", default_return=[])
    def list_range(key: str, start: int, end: int) -> List[str]:
        """Get list elements from start to end index."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return []
        return redis_client.lrange(key, start, end) or []

    # ========================================================================
    # Sorted Set Operations (for rate limiting with sliding window)
    # ========================================================================

    @staticmethod
    @_with_retry("ZADD", default_return=False)
    def sorted_set_add(key: str, member: str, score: float) -> bool:
        """Add member to sorted set with score."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.zadd(key, {member: score})
        return True

    @staticmethod
    @_with_retry("ZCOUNT", default_return=0)
    def sorted_set_count_in_range(
        key: str,
        min_score: float,
        max_score: float
    ) -> int:
        """Count members in sorted set within score range."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return 0
        return redis_client.zcount(key, min_score, max_score) or 0

    @staticmethod
    @_with_retry("ZREMRANGEBYSCORE", default_return=0)
    def sorted_set_remove_by_score(
        key: str,
        min_score: float,
        max_score: float
    ) -> int:
        """Remove members from sorted set by score range."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return 0
        return redis_client.zremrangebyscore(key, min_score, max_score) or 0

    # ========================================================================
    # Hash Operations (for complex objects)
    # ========================================================================

    @staticmethod
    @_with_retry("HSET", default_return=False)
    def hash_set(key: str, mapping: Dict[str, str]) -> bool:
        """Set multiple hash fields."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        redis_client.hset(key, mapping=mapping)
        return True

    @staticmethod
    @_with_retry("HGETALL", default_return={})
    def hash_get_all(key: str) -> Dict[str, str]:
        """Get all hash fields."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return {}
        return redis_client.hgetall(key) or {}

    @staticmethod
    @_with_retry("HDEL", default_return=0)
    def hash_delete(key: str, *fields: str) -> int:
        """Delete hash fields."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return 0
        return redis_client.hdel(key, *fields) or 0

    # ========================================================================
    # Utility Operations
    # ========================================================================

    @staticmethod
    def keys_by_pattern(pattern: str, count: int = 100) -> List[str]:
        """
        Get keys matching pattern using SCAN (safe for production).

        Uses SCAN instead of KEYS for O(1) per call instead of O(N).
        Limits results to prevent memory issues.
        """
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return []
        try:
            keys = []
            cursor = 0
            while len(keys) < count:
                cursor, batch = redis_client.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            return keys[:count]
        except Exception as e:
            logger.warning("[Redis] SCAN failed for %s: %s", pattern[:20], e)
            return []

    @staticmethod
    @_with_retry("PING", default_return=False)
    def ping() -> bool:
        """Test Redis connection."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False
        return redis_client.ping()

    @staticmethod
    def info(section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis server info."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return {}
        try:
            return redis_client.info(section) if section else redis_client.info()
        except Exception as e:
            logger.warning("[Redis] INFO failed: %s", e)
            return {}


# Convenience alias
RedisOps = RedisOperations  # PascalCase alias for Pylint compliance
