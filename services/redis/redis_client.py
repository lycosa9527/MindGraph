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

import inspect
import logging
import os
import time
import warnings
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

import redis
from redis import asyncio as redis_async
from redis.exceptions import ConnectionError as RedisPyConnectionError
from redis.exceptions import ResponseError as RedisPyResponseError
from redis.exceptions import TimeoutError as RedisPyTimeoutError

from services.infrastructure.utils.launch_commands import (
    error_footer_launch_reference,
    lines_redis_connection_failed,
)
from services.redis.redis_circuit_breaker import get_breaker as _get_breaker
from services.redis.redis_circuit_breaker import is_breaker_enabled as _breaker_enabled
from services.redis.redis_connection_options import redis_connection_options
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar("T")


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
            # G8: short-circuit when the per-process breaker is OPEN so a
            # downed Redis cannot multiply tail latency by the worker count.
            breaker = _get_breaker() if _breaker_enabled() else None
            if breaker is not None and not breaker.allow_request():
                return default_return

            last_error = None
            for attempt in range(_RETRY_MAX_ATTEMPTS):
                try:
                    result = func(*args, **kwargs)
                    if breaker is not None:
                        breaker.record_success()
                    return result
                except (RedisPyConnectionError, RedisPyTimeoutError) as e:
                    last_error = e
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        delay = _RETRY_BASE_DELAY * (2**attempt)
                        time.sleep(delay)
                        logger.debug(
                            "[Redis] %s retry %d/%d after %.1fs",
                            operation_name,
                            attempt + 1,
                            _RETRY_MAX_ATTEMPTS,
                            delay,
                        )
                except REDIS_ERRORS as e:
                    # Non-retryable error (data type mismatch, etc.)
                    logger.warning("[Redis] %s failed: %s", operation_name, e)
                    return default_return

            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "[Redis] %s failed after %d retries: %s",
                operation_name,
                _RETRY_MAX_ATTEMPTS,
                last_error,
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
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
        "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
        "socket_connect_timeout": int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
        "retry_on_timeout": os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true",
    }


def _parse_redis_version(version_str: str) -> tuple:
    """Parse Redis version string into a comparable tuple, e.g. '8.6.0' → (8, 6, 0)."""
    try:
        return tuple(int(p) for p in version_str.split(".")[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _redis_py_supports_xadd_idmpauto() -> bool:
    """True if the asyncio client accepts ``idmpauto=`` on ``xadd`` (XADD / IDMPAUTO).

    Only the asyncio ``Redis`` signature matters: the token buffer uses
    :func:`services.redis.redis_async_client.get_async_redis`, and upstream
    redis-py binds the same ``StreamCommands.xadd`` to sync and async clients,
    so checking three classes is redundant and can confuse readers.
    """
    try:
        sig = inspect.signature(redis_async.Redis.xadd)
    except (ImportError, TypeError, ValueError, AttributeError):
        return False
    return "idmpauto" in sig.parameters


class _RedisCapabilities:
    """Cache of feature detection results computed once per process at startup.

    Keeping detection here avoids hot-path try/except trees that would mask
    real connection errors. Each capability defaults to ``False`` until
    ``init_redis_sync`` calls :func:`_apply_redis_startup_config`.
    """

    version: tuple = (0, 0, 0)
    delex: bool = False  # Redis 8.4+ DELEX command for compare-and-delete
    idmpauto: bool = False  # Redis 8.6+ XADD IDMPAUTO (redis-py idmpauto= + id=*)


def _env_truthy(name: str, default: str = "true") -> bool:
    """Return True when an environment variable is set to a truthy value."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _apply_redis_aof_config(redis_client: Any) -> None:
    """
    Enable AOF persistence via CONFIG SET when permitted.

    Collab live_spec write-back relies on appendonly=yes (appendfsync everysec).
    Unlike io-threads, appendonly can usually be toggled at runtime without a
    Redis restart. Managed providers may block CONFIG; in that case ops must set
    AOF in the provider console or redis.conf.
    """
    if not _env_truthy("REDIS_AOF_ENABLED", "true"):
        logger.debug("[Redis] AOF startup tuning disabled (REDIS_AOF_ENABLED=false)")
        return

    appendfsync = os.getenv("REDIS_APPENDFSYNC", "everysec").strip().lower()
    if appendfsync not in ("everysec", "always", "no"):
        appendfsync = "everysec"

    for cfg_key, cfg_val in (("appendonly", "yes"), ("appendfsync", appendfsync)):
        try:
            current = redis_client.config_get(cfg_key) or {}
            current_val = str(current.get(cfg_key, "")).lower()
            if current_val == cfg_val.lower():
                logger.debug("[Redis] %s already '%s'", cfg_key, cfg_val)
                continue
            redis_client.config_set(cfg_key, cfg_val)
            logger.info("[Redis] %s set to '%s'", cfg_key, cfg_val)
        except REDIS_ERRORS as exc:
            logger.warning(
                "[Redis] Could not set %s=%s (%s). Collab edits may be lost on crash until AOF is enabled.",
                cfg_key,
                cfg_val,
                exc,
            )

    if _env_truthy("REDIS_CONFIG_REWRITE", "false"):
        try:
            redis_client.config_rewrite()
            logger.info("[Redis] CONFIG REWRITE saved runtime settings to redis.conf")
        except REDIS_ERRORS as exc:
            logger.info(
                "[Redis] CONFIG REWRITE skipped (%s). "
                "AOF remains active until Redis restarts; edit redis.conf to persist.",
                exc,
            )


def _apply_redis_startup_config(redis_client: Any, redis_version: str) -> None:
    """
    Apply runtime CONFIG SET options based on detected Redis version.

    Guarded per-version so the app starts cleanly on older Redis instances.
    All options are overridable via environment variables.
    """
    version_tuple = _parse_redis_version(redis_version)
    _RedisCapabilities.version = version_tuple
    _RedisCapabilities.delex = version_tuple >= (8, 4, 0)
    client_idmp = _redis_py_supports_xadd_idmpauto()
    if version_tuple >= (8, 6, 0) and not client_idmp:
        _log_redis_error(
            title="REDIS 8.6+ REQUIRES A CURRENT REDIS-PY (redis) PACKAGE",
            details=[
                "The Redis server is 8.6 or newer; MindGraph uses XADD with IDMPAUTO",
                "for the token-usage stream, which requires a redis (redis-py) build",
                "that exposes the idmpauto= parameter on the asyncio client xadd().",
                "",
                "To fix, upgrade the Python package, then restart the app:",
                "  pip install -U redis",
                "",
                *error_footer_launch_reference(),
            ],
        )
        raise RedisStartupError("redis-py does not support XADD idmpauto=; required for Redis 8.6+") from None
    _RedisCapabilities.idmpauto = version_tuple >= (8, 6, 0) and client_idmp

    if version_tuple >= (8, 6, 0):
        policy = os.getenv("REDIS_EVICTION_POLICY", "volatile-lru")
        try:
            redis_client.config_set("maxmemory-policy", policy)
            logger.info("[Redis] Eviction policy set to '%s'", policy)
        except REDIS_ERRORS as exc:
            logger.warning("[Redis] Could not set eviction policy: %s", exc)

        try:
            redis_client.config_set("key-memory-histograms", "yes")
            logger.info("[Redis] key-memory-histograms enabled")
        except REDIS_ERRORS as exc:
            logger.info(
                "[Redis] key-memory-histograms not applied at runtime (%s). "
                "Optional in Redis 8.6+; often blocked unless set in redis.conf "
                "or when CONFIG is restricted — safe to ignore.",
                exc,
            )
    else:
        logger.debug(
            "[Redis] Version %s < 8.6 — skipping volatile-lru and key-memory-histograms",
            redis_version,
        )

    # Generic Redis 7+ tuning: these options are safe across the supported
    # range and reduce tail latency under load. Each setting is best-effort —
    # managed Redis providers often disable CONFIG SET for some keys.
    if version_tuple >= (7, 0, 0):
        cpu_count = os.cpu_count() or 1
        io_threads = max(1, min(8, cpu_count - 1))
        runtime_settings: Dict[str, str] = {
            "lazyfree-lazy-eviction": "yes",
            "lazyfree-lazy-expire": "yes",
            "lazyfree-lazy-server-del": "yes",
            "lazyfree-lazy-user-del": "yes",
            "lazyfree-lazy-user-flush": "yes",
            "io-threads": str(io_threads),
            "io-threads-do-reads": "yes",
            "activedefrag": "yes",
            "latency-monitor-threshold": "100",
            "slowlog-log-slower-than": "10000",
            "slowlog-max-len": "256",
        }
        for cfg_key, cfg_val in runtime_settings.items():
            try:
                redis_client.config_set(cfg_key, cfg_val)
            except REDIS_ERRORS as exc:
                logger.debug(
                    "[Redis] CONFIG SET %s=%s skipped (%s)",
                    cfg_key,
                    cfg_val,
                    exc,
                )
        logger.info(
            "[Redis] Applied runtime tuning: io-threads=%d, lazyfree=*, activedefrag, latency-monitor-threshold=100ms",
            io_threads,
        )

    _apply_redis_aof_config(redis_client)


def redis_delex_enabled() -> bool:
    """Return whether Redis 8.4+ DELEX compare-and-delete is enabled for this process."""
    return bool(_RedisCapabilities.delex)


def set_redis_delex_enabled(enabled: bool) -> None:
    """Disable DELEX at runtime when the server rejects the command."""
    _RedisCapabilities.delex = enabled


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
    redis_url = config["url"]

    logger.info("[Redis] Connecting to %s...", redis_url)

    try:
        redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=config["max_connections"],
            socket_timeout=config["socket_timeout"],
            socket_connect_timeout=config["socket_connect_timeout"],
            retry_on_timeout=config["retry_on_timeout"],
            **redis_connection_options(),
        )

        # Test connection
        redis_client.ping()

        # Get server info
        info = redis_client.info("server")
        redis_version = info.get("redis_version", "unknown")

        _RedisState.set_client(redis_client)
        logger.info("[Redis] Connected successfully (version: %s)", redis_version)

        _apply_redis_startup_config(redis_client, redis_version)
        return True

    except REDIS_ERRORS as exc:
        _log_redis_error(
            title="REDIS CONNECTION FAILED",
            details=lines_redis_connection_failed(redis_url, str(exc)),
        )
        raise RedisStartupError(f"Failed to connect to Redis: {exc}") from exc


def close_redis_sync():
    """Close Redis connection gracefully (synchronous)."""
    redis_client = _RedisState.get_client()
    if redis_client:
        try:
            redis_client.close()
            logger.info("[Redis] Connection closed")
        except REDIS_ERRORS as e:
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
    return "external"


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
    @_with_retry("SET", default_return=True)
    def set_with_ttl_if_not_exists(key: str, value: str, ttl_seconds: int) -> bool:
        """
        SET key NX EX — atomic create-if-absent.

        Returns True if this call created the key (first claimant).
        Returns False if the key already existed (typical duplicate).
        If Redis is unavailable or all retries fail, returns True (fail open: still process).
        """
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return True
        result = redis_client.set(key, value, ex=ttl_seconds, nx=True)
        return bool(result)

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
    @_with_retry("GETDEL", default_return=None)
    def get_and_delete(key: str) -> Optional[str]:
        """Atomically get and delete a key (GETDEL on Redis >= 6.2, else GET+DEL)."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            logger.debug("[Redis] get_and_delete: Redis unavailable for key: %s", key)
            return None
        try:
            return redis_client.getdel(key)
        except RedisPyResponseError as exc:
            if "GETDEL" not in str(exc).upper():
                logger.warning("[Redis] get_and_delete failed for key %s: %s", key, exc)
                return None
            pipe = redis_client.pipeline(transaction=True)
            pipe.get(key)
            pipe.delete(key)
            results = pipe.execute()
            return results[0]
        except REDIS_ERRORS as exc:
            logger.warning("[Redis] get_and_delete failed for key %s: %s", key, exc)
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
    def sorted_set_count_in_range(key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set within score range."""
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return 0
        return redis_client.zcount(key, min_score, max_score) or 0

    @staticmethod
    @_with_retry("ZREMRANGEBYSCORE", default_return=0)
    def sorted_set_remove_by_score(key: str, min_score: float, max_score: float) -> int:
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
    # Atomic Operations
    # ========================================================================

    @staticmethod
    def compare_and_delete(key: str, expected_value: str) -> bool:
        """Atomically delete ``key`` only when its value equals ``expected_value``.

        Uses DELEX on Redis >= 8.4 (capability detected once at startup),
        otherwise an equivalent single-round-trip Lua script. Behaviour is
        identical across versions; the per-call try/except for DELEX has
        been removed so connection errors surface immediately.

        Returns True if the key was deleted, False if value did not match or
        the key did not exist.
        """
        redis_client = _RedisState.get_client()
        if not _RedisState.is_available() or not redis_client:
            return False

        if _RedisCapabilities.delex:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    return bool(redis_client.delex(key, expected_value))
            except (RedisPyConnectionError, RedisPyTimeoutError) as exc:
                logger.warning(
                    "[Redis] compare_and_delete connection error for %s: %s",
                    key[:20],
                    exc,
                )
                return False
            except RedisPyResponseError as exc:
                # Capability marker was wrong (very rare) — disable for the
                # rest of the process and fall through to the Lua path.
                logger.warning(
                    "[Redis] DELEX rejected by server (%s); disabling for this process",
                    exc,
                )
                _RedisCapabilities.delex = False

        try:
            result = redis_client.eval(
                "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                1,
                key,
                expected_value,
            )
            return bool(result)
        except REDIS_ERRORS as exc:
            logger.warning("[Redis] compare_and_delete failed for %s: %s", key[:20], exc)
            return False

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
        except REDIS_ERRORS as e:
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
        except REDIS_ERRORS as e:
            logger.warning("[Redis] INFO failed: %s", e)
            return {}


# Convenience alias
RedisOps = RedisOperations  # PascalCase alias for Pylint compliance
