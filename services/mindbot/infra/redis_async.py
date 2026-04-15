"""Native async Redis client for MindBot hot-path operations.

Uses ``redis.asyncio`` (ships with redis-py >= 4.2, already in requirements.txt)
so every Redis call is a genuine coroutine — no thread-pool hops via
``asyncio.to_thread``.

Key design principle: ``redis_setnx_ttl`` returns ``Optional[bool]`` (True/False/None)
so callers can distinguish "key already existed" (False) from "Redis error" (None).
This prevents silent message drops when Redis is temporarily unreachable.

Intended callers: callback.py, conv_gate.py, oauth.py, metrics.py.

Pool sizing
----------
``MINDBOT_REDIS_MAX_CONNECTIONS`` (default 100) should be at least as large as
the peak number of concurrent MindBot handlers that touch Redis simultaneously.
With ``MINDBOT_MAX_CONCURRENT`` (default 64) coroutines potentially each making
one Redis call, the default pool of 100 provides headroom for bursts without
saturating the pool and introducing wait time.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_client: Optional[aioredis.Redis] = None

_DEFAULT_MAX_CONNECTIONS = 100


def _get_client() -> aioredis.Redis:
    """
    Return (and lazily create) the process-wide async Redis client.

    ``redis.asyncio.from_url`` creates a connection pool; the first actual
    network connection is established on the first command, not here.
    """
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        max_conn = int(os.getenv("MINDBOT_REDIS_MAX_CONNECTIONS", str(_DEFAULT_MAX_CONNECTIONS)))
        _client = aioredis.from_url(
            url,
            decode_responses=True,
            max_connections=max_conn,
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
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[MindBot] redis_setnx_ttl error key=%s: %s", key, exc)
        return None


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
    except Exception as exc:  # pylint: disable=broad-except
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
