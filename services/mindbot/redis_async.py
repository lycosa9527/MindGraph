"""Native async Redis client for MindBot hot-path operations.

Uses ``redis.asyncio`` (ships with redis-py >= 4.2, already in requirements.txt)
so every Redis call is a genuine coroutine — no thread-pool hops via
``asyncio.to_thread``.  All functions return sensible defaults (None / False)
on connection errors so the rest of the pipeline degrades gracefully when Redis
is temporarily unreachable.

Intended callers: callback.py, conv_gate.py, oauth.py, metrics.py.
Not a replacement for the global ``RedisOperations`` sync client used elsewhere
in the application — only the MindBot hot path is migrated here.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_client: Optional[aioredis.Redis] = None


def _get_client() -> aioredis.Redis:
    """
    Return (and lazily create) the process-wide async Redis client.

    ``redis.asyncio.from_url`` creates a connection pool; the first actual
    network connection is established on the first command, not here.
    """
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _client = aioredis.from_url(
            url,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True,
        )
    return _client


async def redis_get(key: str) -> Optional[str]:
    """Return the string value for ``key``, or ``None`` on miss or error."""
    try:
        return await _get_client().get(key)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_get error key=%s: %s", key, exc)
        return None


async def redis_set_ttl(key: str, value: str, ttl: int) -> bool:
    """SET key value EX ttl. Returns True on success."""
    try:
        result = await _get_client().set(key, value, ex=ttl)
        return bool(result)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_set_ttl error key=%s: %s", key, exc)
        return False


async def redis_setnx_ttl(key: str, value: str, ttl: int) -> bool:
    """
    SET key value NX EX ttl.

    Returns ``True`` if this caller won the race (key was set), ``False`` if the
    key already existed (another process set it first).
    """
    try:
        result = await _get_client().set(key, value, ex=ttl, nx=True)
        return bool(result)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_setnx_ttl error key=%s: %s", key, exc)
        return False


async def redis_delete(key: str) -> None:
    """DEL key. Silently swallows errors."""
    try:
        await _get_client().delete(key)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_delete error key=%s: %s", key, exc)


async def redis_expire(key: str, ttl: int) -> None:
    """EXPIRE key ttl. Silently swallows errors."""
    try:
        await _get_client().expire(key, ttl)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_expire error key=%s: %s", key, exc)


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
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_incr_with_ttl error key=%s: %s", key, exc)
        return None


async def close_async_redis() -> None:
    """Close the connection pool — call once during application shutdown."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[MindBot] redis_async close error: %s", exc)
        _client = None
