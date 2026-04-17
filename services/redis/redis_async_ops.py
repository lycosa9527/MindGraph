"""
Async high-level Redis operations (mirror of :class:`RedisOperations`).
=====================================================================

The synchronous :class:`services.redis.redis_client.RedisOperations` class is
the canonical wrapper for "use Redis from anywhere with sane defaults".
``AsyncRedisOps`` exposes the same surface area but built on top of the
shared async client (:mod:`services.redis.redis_async_client`) so that
FastAPI handlers, MindBot pipeline steps and Celery `asyncio.run` adapters
can all stop wrapping Redis calls in :func:`asyncio.to_thread`.

Goals
-----
* Identical method names / return types / failure semantics to
  ``RedisOperations``, so migrating callers is a mechanical
  ``RedisOps.foo(...)`` → ``await AsyncRedisOps.foo(...)`` change.
* Same retry-on-transient policy with exponential backoff.
* No global state of its own — everything routes through
  :func:`services.redis.redis_async_client.get_async_redis`.

Compare-and-delete uses Redis 8.4+ ``DELEX`` when available (capability
flag is read from the sync ``_RedisCapabilities``, populated at startup);
otherwise it falls back to a single-RTT Lua script.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import warnings
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, cast

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError as RedisResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from services.redis.redis_async_client import get_async_redis
from services.redis.redis_circuit_breaker import (
    get_breaker as _get_breaker,
    is_breaker_enabled as _breaker_enabled,
)

logger = logging.getLogger(__name__)


T = TypeVar("T")


_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 0.05  # seconds; tighter than sync because await is cheap


def _is_redis_available() -> bool:
    """Lazy resolver for sync availability flag (avoids import cycle).

    Returns True when the sync-side ``_RedisState`` has not been initialised
    yet so first-touch async callers (e.g. lifespan startup) are not blocked.
    """
    try:
        from services.redis.redis_client import is_redis_available as _check
    except Exception:  # pylint: disable=broad-except
        return True
    try:
        return bool(_check())
    except Exception:  # pylint: disable=broad-except
        return True


def _with_async_retry(operation_name: str, default_return: Any = None):
    """Async equivalent of :func:`services.redis.redis_client._with_retry`.

    Retries only on transient connection / timeout errors so logic bugs
    (wrong type, missing key) surface immediately.

    Short-circuits with ``default_return`` when the shared :class:`_RedisState`
    flag reports Redis unavailable (G3).  This eliminates ~350 ms of
    pointless exponential backoff per call when Redis is known to be down,
    and matches the fail-fast behaviour callers already see on the sync side.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not _is_redis_available():
                return default_return

            # G8: per-process breaker — short-circuits when Redis is wedged
            # so the async event loop does not pay 3x retries per request.
            breaker = _get_breaker() if _breaker_enabled() else None
            if breaker is not None and not breaker.allow_request():
                return default_return

            last_error: Optional[Exception] = None
            for attempt in range(_RETRY_MAX_ATTEMPTS):
                try:
                    result = await func(*args, **kwargs)
                    if breaker is not None:
                        breaker.record_success()
                    return result
                except (RedisConnectionError, RedisTimeoutError) as exc:
                    last_error = exc
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        delay = _RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(delay)
                        logger.debug(
                            "[RedisAsync] %s retry %d/%d after %.2fs",
                            operation_name,
                            attempt + 1,
                            _RETRY_MAX_ATTEMPTS,
                            delay,
                        )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("[RedisAsync] %s failed: %s", operation_name, exc)
                    return default_return

            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "[RedisAsync] %s failed after %d retries: %s",
                operation_name,
                _RETRY_MAX_ATTEMPTS,
                last_error,
            )
            return default_return

        return wrapper

    return decorator


def _client() -> aioredis.Redis:
    """Resolve the shared async client lazily on every call.

    Re-resolving each time keeps the wrapper resilient to ``close_async_redis``
    being invoked between operations (e.g. during graceful shutdown drain).
    """

    return get_async_redis()


class AsyncRedisOperations:
    """Async mirror of :class:`RedisOperations`.

    All methods are ``staticmethod`` so callers can use the same
    ``ClassName.method(...)`` style they already use for the sync API,
    just prefixed with ``await``.
    """

    # ---------- Strings / generic key ops ----------
    @staticmethod
    @_with_async_retry("SET", default_return=False)
    async def set_with_ttl(key: str, value: str, ttl_seconds: int) -> bool:
        """SET key value EX ttl. Returns True on success."""

        await _client().setex(key, ttl_seconds, value)
        return True

    @staticmethod
    @_with_async_retry("SET NX", default_return=True)
    async def set_with_ttl_if_not_exists(key: str, value: str, ttl_seconds: int) -> bool:
        """SET key NX EX — atomic create-if-absent.

        Mirrors the sync helper: returns True when this call created the key
        (first claimant), False when the key already existed.  On Redis
        unavailability returns ``True`` (fail-open) so callers do not silently
        swallow legitimate work.
        """

        result = await _client().set(key, value, ex=ttl_seconds, nx=True)
        return bool(result)

    @staticmethod
    @_with_async_retry("GET", default_return=None)
    async def get(key: str) -> Optional[str]:
        """GET key. None on miss or transient error."""

        return await _client().get(key)

    @staticmethod
    @_with_async_retry("DELETE", default_return=False)
    async def delete(key: str) -> bool:
        """DEL key."""

        await _client().delete(key)
        return True

    @staticmethod
    @_with_async_retry("GETDEL", default_return=None)
    async def get_and_delete(key: str) -> Optional[str]:
        """GETDEL key (Redis >= 6.2) — atomic get + delete in one round-trip."""

        return await _client().getdel(key)

    @staticmethod
    @_with_async_retry("INCR", default_return=None)
    async def increment(key: str, ttl_seconds: Optional[int] = None) -> Optional[int]:
        """INCR + EXPIRE NX in a single pipeline."""

        client = _client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            if ttl_seconds:
                pipe.expire(key, ttl_seconds, nx=True)
            results = await pipe.execute()
        return int(results[0]) if results else None

    @staticmethod
    @_with_async_retry("INCRBYFLOAT", default_return=None)
    async def increment_float(
        key: str,
        amount: float,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[float]:
        """INCRBYFLOAT + optional EXPIRE NX in a single pipeline."""

        client = _client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.incrbyfloat(key, amount)
            if ttl_seconds:
                pipe.expire(key, ttl_seconds, nx=True)
            results = await pipe.execute()
        return float(results[0]) if results else None

    @staticmethod
    @_with_async_retry("TTL", default_return=-2)
    async def get_ttl(key: str) -> int:
        """TTL key. ``-1`` = no TTL, ``-2`` = key missing."""

        result = await _client().ttl(key)
        return int(result) if result is not None else -2

    @staticmethod
    @_with_async_retry("EXPIRE", default_return=False)
    async def set_ttl(key: str, ttl_seconds: int) -> bool:
        """EXPIRE key ttl on an existing key."""

        await _client().expire(key, ttl_seconds)
        return True

    @staticmethod
    @_with_async_retry("EXISTS", default_return=False)
    async def exists(key: str) -> bool:
        """EXISTS key — coerced to bool."""

        result = await _client().exists(key)
        return bool(result and int(result) > 0)

    # ---------- Lists ----------
    @staticmethod
    @_with_async_retry("RPUSH", default_return=False)
    async def list_push(key: str, value: str) -> bool:
        """RPUSH key value."""

        await _client().rpush(key, value)
        return True

    @staticmethod
    @_with_async_retry("LRANGE+LTRIM", default_return=[])
    async def list_pop_many(key: str, count: int) -> List[str]:
        """Atomic LRANGE 0..count-1 + LTRIM count..-1 in one pipeline."""

        client = _client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.lrange(key, 0, count - 1)
            pipe.ltrim(key, count, -1)
            results = await pipe.execute()
        return list(results[0] or [])

    @staticmethod
    @_with_async_retry("LLEN", default_return=0)
    async def list_length(key: str) -> int:
        """LLEN key."""

        result = await _client().llen(key)
        return int(result or 0)

    @staticmethod
    @_with_async_retry("LRANGE", default_return=[])
    async def list_range(key: str, start: int, end: int) -> List[str]:
        """LRANGE key start end."""

        return list(await _client().lrange(key, start, end) or [])

    # ---------- Sorted sets ----------
    @staticmethod
    @_with_async_retry("ZADD", default_return=False)
    async def sorted_set_add(key: str, member: str, score: float) -> bool:
        """ZADD key score member."""

        await _client().zadd(key, {member: score})
        return True

    @staticmethod
    @_with_async_retry("ZCOUNT", default_return=0)
    async def sorted_set_count_in_range(
        key: str,
        min_score: float,
        max_score: float,
    ) -> int:
        """ZCOUNT key min max."""

        result = await _client().zcount(key, min_score, max_score)
        return int(result or 0)

    @staticmethod
    @_with_async_retry("ZREMRANGEBYSCORE", default_return=0)
    async def sorted_set_remove_by_score(
        key: str,
        min_score: float,
        max_score: float,
    ) -> int:
        """ZREMRANGEBYSCORE key min max."""

        result = await _client().zremrangebyscore(key, min_score, max_score)
        return int(result or 0)

    # ---------- Hashes ----------
    @staticmethod
    @_with_async_retry("HSET", default_return=False)
    async def hash_set(key: str, mapping: Dict[str, str]) -> bool:
        """HSET key field1 value1 ..."""

        await _client().hset(key, mapping=mapping)
        return True

    @staticmethod
    @_with_async_retry("HGETALL", default_return={})
    async def hash_get_all(key: str) -> Dict[str, str]:
        """HGETALL key — empty dict on miss/error."""

        return dict(await _client().hgetall(key) or {})

    @staticmethod
    @_with_async_retry("HDEL", default_return=0)
    async def hash_delete(key: str, *fields: str) -> int:
        """HDEL key field1 field2 ..."""

        result = await _client().hdel(key, *fields)
        return int(result or 0)

    # ---------- Atomic patterns ----------
    @staticmethod
    async def compare_and_delete(key: str, expected_value: str) -> bool:
        """Atomic compare-and-delete.

        Uses ``DELEX`` on Redis 8.4+ when the sync startup probe enabled it,
        otherwise a tiny Lua script (``GET == ARGV[1] then DEL else 0``).
        Both paths take exactly one network round-trip.
        """

        client = _client()
        try:
            from services.redis.redis_client import (  # noqa: WPS433
                _RedisCapabilities as _redis_capabilities,
            )
        except Exception:  # pylint: disable=broad-except
            _redis_capabilities = None

        delex_enabled = bool(_redis_capabilities and _redis_capabilities.delex)

        if delex_enabled:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    return bool(
                        await cast(
                            Awaitable[int],
                            client.execute_command("DELEX", key, expected_value),
                        )
                    )
            except (RedisConnectionError, RedisTimeoutError) as exc:
                logger.warning(
                    "[RedisAsync] compare_and_delete connection error for %s: %s",
                    key[:20],
                    exc,
                )
                return False
            except RedisResponseError as exc:
                logger.warning(
                    "[RedisAsync] DELEX rejected by server (%s); disabling for this process",
                    exc,
                )
                if _redis_capabilities is not None:
                    _redis_capabilities.delex = False
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[RedisAsync] compare_and_delete unexpected error for %s: %s",
                    key[:20],
                    exc,
                )

        try:
            result = await client.eval(
                "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                1,
                key,
                expected_value,
            )
            return bool(result)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "[RedisAsync] compare_and_delete fallback failed for %s: %s",
                key[:20],
                exc,
            )
            return False

    # ---------- Discovery / health ----------
    @staticmethod
    async def keys_by_pattern(pattern: str, count: int = 100) -> List[str]:
        """SCAN-based key discovery — never blocks the server like KEYS."""

        keys: List[str] = []
        try:
            client = _client()
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)
                if len(keys) >= count:
                    break
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[RedisAsync] SCAN failed for %s: %s", pattern[:20], exc)
        return keys[:count]

    @staticmethod
    @_with_async_retry("PING", default_return=False)
    async def ping() -> bool:
        """PING — True if Redis is reachable."""

        return bool(await cast(Awaitable[bool], _client().ping()))

    @staticmethod
    async def info(section: Optional[str] = None) -> Dict[str, Any]:
        """INFO [section] — empty dict on error to keep callers branch-free."""

        try:
            client = _client()
            return dict(await (client.info(section) if section else client.info()) or {})
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[RedisAsync] INFO failed: %s", exc)
            return {}


AsyncRedisOps = AsyncRedisOperations  # PascalCase alias mirroring sync side
