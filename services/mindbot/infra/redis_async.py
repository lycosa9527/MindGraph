"""Async Redis helpers historically used by MindBot.

This module is now a **thin compatibility shim** around the shared async
client at :mod:`services.redis.redis_async_client`.  All MindBot call sites
keep their existing imports while the actual connection pool, RESP3
negotiation, keepalive and retry policy are managed centrally so cache,
session, rate-limit and bot subsystems share one pool with one set of
operational knobs.

Key design principle: ``redis_setnx_ttl`` returns ``Optional[bool]``
(True/False/None) so callers can distinguish "key already existed" (False)
from "Redis error" (None).  This prevents silent message drops when Redis is
temporarily unreachable.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Optional, cast

import redis.asyncio as aioredis

from services.redis.redis_async_client import (
    close_async_redis as _shared_close_async_redis,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


def _get_client() -> aioredis.Redis:
    """Return the shared process-wide async Redis client.

    Kept as a module-private helper so existing call sites do not need to
    change; new code should import ``get_async_redis`` from
    :mod:`services.redis.redis_async_client` directly.
    """

    return get_async_redis()


async def redis_get(key: str) -> Optional[str]:
    """Return the string value for ``key``, or ``None`` on miss or error."""
    try:
        return await _get_client().get(key)
    except Exception as exc:
        logger.warning("[MindBot] redis_get error key=%s: %s", key, exc)
        return None


async def redis_set_ttl(key: str, value: str, ttl: int) -> bool:
    """SET key value EX ttl. Returns True on success."""
    try:
        result = await _get_client().set(key, value, ex=ttl)
        return bool(result)
    except Exception as exc:
        logger.warning("[MindBot] redis_set_ttl error key=%s: %s", key, exc)
        return False


async def redis_setnx_ttl(key: str, value: str, ttl: int) -> Optional[bool]:
    """
    SET key value NX EX ttl.

    Returns:
    - ``True``  — this caller won the race (key was set).
    - ``False`` — key already existed (another process set it first).
    - ``None``  — Redis error; caller should **not** treat this as a duplicate.

    The three-valued return is intentional: conflating a Redis error with an
    existing key would silently drop operations (e.g. message dedup) when Redis
    is temporarily unreachable.
    """
    try:
        result = await _get_client().set(key, value, ex=ttl, nx=True)
        return bool(result)
    except Exception as exc:
        logger.warning("[MindBot] redis_setnx_ttl error key=%s: %s", key, exc)
        return None


async def redis_delete(key: str) -> None:
    """DEL key. Silently swallows errors."""
    try:
        await _get_client().delete(key)
    except Exception as exc:
        logger.warning("[MindBot] redis_delete error key=%s: %s", key, exc)


async def redis_expire(key: str, ttl: int) -> None:
    """EXPIRE key ttl. Silently swallows errors."""
    try:
        await _get_client().expire(key, ttl)
    except Exception as exc:
        logger.warning("[MindBot] redis_expire error key=%s: %s", key, exc)


async def redis_bind(key: str, value: str, ttl: int) -> None:
    """
    Bind ``key`` to ``value`` if it is not already set, then refresh the TTL.

    Sends ``SET NX EX`` and ``EXPIRE`` in a single pipeline (1 RTT) so that:
    - New keys are created atomically with a TTL.
    - Existing keys (first-writer wins) have their TTL extended without
      overwriting the stored value.

    Silently swallows connection errors so the caller degrades gracefully.
    """
    try:
        client = _get_client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.set(key, value, ex=ttl, nx=True)
            pipe.expire(key, ttl)
            await pipe.execute()
    except Exception as exc:
        logger.warning("[MindBot] redis_bind error key=%s: %s", key, exc)


async def redis_incr_with_ttl(key: str, ttl: int) -> Optional[int]:
    """
    Atomic INCR + EXPIRE via a pipeline (no transaction needed).

    Returns the new counter value, or ``None`` on error.
    The TTL is refreshed on every increment so the window slides with activity.
    """
    try:
        client = _get_client()
        async with client.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
        return int(results[0]) if results else None
    except Exception as exc:
        logger.warning("[MindBot] redis_incr_with_ttl error key=%s: %s", key, exc)
        return None


async def redis_incr_fixed_window(key: str, ttl: int) -> Optional[int]:
    """
    Fixed-window counter: INCR + SET TTL only when the key is new.

    Unlike ``redis_incr_with_ttl``, the TTL is **not** refreshed on every
    increment.  The counter expires after ``ttl`` seconds from the first
    increment, ensuring a true fixed window regardless of activity volume.

    Uses a Lua script executed atomically on the Redis server.
    """
    lua = "local v = redis.call('INCR', KEYS[1]) if v == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end return v"
    try:
        client = _get_client()
        result = await client.execute_command("EVAL", lua, 1, key, str(ttl))
        if result is None:
            return None
        return int(result)
    except Exception as exc:
        logger.warning("[MindBot] redis_incr_fixed_window error key=%s: %s", key, exc)
        return None


async def redis_ping() -> bool:
    """Return True if the async Redis client responds to PING, False on error."""
    try:
        result = await cast(Awaitable[bool], _get_client().ping())
        return bool(result)
    except Exception as exc:
        logger.warning("[MindBot] redis_ping failed: %s", exc)
        return False


async def close_async_redis() -> None:
    """Close the shared async Redis pool — see :mod:`services.redis.redis_async_client`."""

    await _shared_close_async_redis()
