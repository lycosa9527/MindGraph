"""
Shared async Redis client (``redis.asyncio``) for the whole application.
=======================================================================

This module is the single source of truth for the **process-wide async
Redis connection pool**.  Historically each subsystem (mindbot, web routes,
session) either used the synchronous client wrapped in ``asyncio.to_thread``
or maintained its own ad-hoc async pool — both approaches add latency,
duplicate retry/timeout configuration and waste connections.

What this module provides
-------------------------
* ``get_async_redis()`` — lazily create and return the shared
  :class:`redis.asyncio.Redis` instance.  Safe to call from any event-loop
  coroutine; first call wins (no asyncio.Lock needed because creation is
  synchronous within a single tick).
* ``close_async_redis()`` — graceful shutdown hook.
* ``async_ping()`` — health-check helper used by readiness probes.

Wire features (RESP3, keepalive, health-check)
----------------------------------------------
We opt in to **RESP3** so newer Redis features (server-side push, client
tracking, hash-field expiration return shapes) work without manual hex
parsing later.  We also enable TCP keepalive and a short pool health check
interval so dead connections (load balancer idle resets, NAT timeouts) are
detected before the next user request fails.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
from typing import Awaitable, Optional, cast

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry as AsyncRetry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)


# Pool size arithmetic for online collab at 500 editors / 4 workers:
#   Each active editor during a hot update path issues roughly:
#     1 pipeline (live_spec merge + INCR seq + ck_key ops)   ~3 cmds in 1 RTT
#     1 editors HSET/HEXPIRE per node_editing              ~2 cmds in 1 RTT
#     1 ZADD idle score touch                               ~1 cmd in 1 RTT
#   = ~6 RTTs/update × 500 editors × 5 updates/s / 4 workers
#   ≈ 1875 concurrent ops/s/worker → at 5 ms/cmd → ~10 connections steady-state
#   Burst/join-storm headroom at 200 ms tail latency: ~40 connections.
#   Add pub/sub connection, idle monitor, flush tasks and HTTP handlers:
#   256 is the recommended minimum for 500-editor rooms; 512 for peak safety.
_DEFAULT_MAX_CONNECTIONS = 256
_DEFAULT_HEALTH_CHECK_INTERVAL = 30  # seconds
_DEFAULT_SOCKET_TIMEOUT = 5.0
_DEFAULT_SOCKET_CONNECT_TIMEOUT = 5.0


def _enable_resp3_default() -> bool:
    """RESP3 is on unless explicitly disabled.

    Redis 7+ servers all speak RESP3; older servers gracefully downgrade
    during the HELLO handshake.  We give operators an opt-out for the
    rare case where a managed proxy strips the new framing.
    """

    return os.getenv("REDIS_RESP3", "true").strip().lower() in {"1", "true", "yes", "on"}


def _enable_keepalive_default() -> bool:
    """TCP keepalive is on by default; disable on platforms where it is unsafe."""

    return os.getenv("REDIS_TCP_KEEPALIVE", "true").strip().lower() in {"1", "true", "yes", "on"}


def _build_keepalive_options() -> dict[int, int]:
    """Return per-platform TCP keepalive socket options.

    Defaults are intentionally aggressive (idle 60s / interval 10s / 6 probes)
    because Redis sits behind cloud load balancers that often kill silent TCP
    flows after 90 seconds.  All three knobs are tunable via env vars.
    """

    idle = env_int("REDIS_TCP_KEEPIDLE", 60)
    interval = env_int("REDIS_TCP_KEEPINTVL", 10)
    count = env_int("REDIS_TCP_KEEPCNT", 6)

    options: dict[int, int] = {}
    # Linux exposes the full triplet; macOS exposes TCP_KEEPALIVE for idle.
    if sys.platform.startswith("linux"):
        if hasattr(socket, "TCP_KEEPIDLE"):
            options[socket.TCP_KEEPIDLE] = idle
        if hasattr(socket, "TCP_KEEPINTVL"):
            options[socket.TCP_KEEPINTVL] = interval
        if hasattr(socket, "TCP_KEEPCNT"):
            options[socket.TCP_KEEPCNT] = count
    elif sys.platform == "darwin" and hasattr(socket, "TCP_KEEPALIVE"):
        options[socket.TCP_KEEPALIVE] = idle
    # Windows uses SIO_KEEPALIVE_VALS via setsockopt with SO_KEEPALIVE; the
    # redis-py async client only sets SO_KEEPALIVE so the OS-level defaults
    # apply on Windows.
    return options


class _AsyncRedisState:
    """Encapsulates module-level state to keep ``global`` out of call sites."""

    client: Optional[aioredis.Redis] = None


def _build_async_client() -> aioredis.Redis:
    """Construct the singleton async Redis pool.

    ``redis.asyncio.from_url`` allocates the pool object eagerly but does not
    open any sockets until the first command, so this is cheap.
    """

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_conn = max(1, env_int("REDIS_ASYNC_MAX_CONNECTIONS", _DEFAULT_MAX_CONNECTIONS))
    health_check = max(1, env_int("REDIS_HEALTH_CHECK_INTERVAL", _DEFAULT_HEALTH_CHECK_INTERVAL))
    socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", str(_DEFAULT_SOCKET_TIMEOUT)))
    connect_timeout = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", str(_DEFAULT_SOCKET_CONNECT_TIMEOUT)))

    retry = AsyncRetry(ExponentialBackoff(cap=1.0, base=0.05), retries=2)

    socket_keepalive = _enable_keepalive_default()
    keepalive_options = _build_keepalive_options() if socket_keepalive else {}

    kwargs: dict = {
        "decode_responses": True,
        "max_connections": max_conn,
        "socket_timeout": socket_timeout,
        "socket_connect_timeout": connect_timeout,
        "retry_on_timeout": True,
        "retry": retry,
        "retry_on_error": [RedisConnectionError, RedisTimeoutError],
        "health_check_interval": health_check,
        "socket_keepalive": socket_keepalive,
    }
    if keepalive_options:
        kwargs["socket_keepalive_options"] = keepalive_options
    if _enable_resp3_default():
        kwargs["protocol"] = 3

    client = aioredis.from_url(url, **kwargs)
    logger.info(
        "[RedisAsync] Pool ready (url=%s, max_conn=%d, RESP%d, health=%ds, keepalive=%s)",
        url,
        max_conn,
        kwargs.get("protocol", 2),
        health_check,
        socket_keepalive,
    )
    return client


def get_async_redis() -> aioredis.Redis:
    """Return the process-wide async Redis client, creating it on first call.

    Must be called from the event loop (not from worker threads).  See the
    ``redis.asyncio`` docs for thread-safety constraints.
    """

    if _AsyncRedisState.client is None:
        _AsyncRedisState.client = _build_async_client()
    return _AsyncRedisState.client


async def async_ping(timeout: float = 1.0) -> bool:
    """Return ``True`` when the async pool can round-trip a PING within ``timeout``.

    Used by the readiness probe and the ``compare_and_delete`` fallback path
    so we never block startup on a partially-available Redis.
    """

    client = get_async_redis()
    try:
        return bool(await asyncio.wait_for(cast(Awaitable[bool], client.ping()), timeout=timeout))
    except (asyncio.TimeoutError, RedisConnectionError, RedisTimeoutError) as exc:
        logger.warning("[RedisAsync] ping failed: %s", exc)
        return False
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[RedisAsync] unexpected ping error: %s", exc)
        return False


async def close_async_redis() -> None:
    """Close the connection pool — call once during application shutdown."""

    client = _AsyncRedisState.client
    if client is None:
        return
    try:
        await client.aclose()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[RedisAsync] close error: %s", exc)
    finally:
        _AsyncRedisState.client = None
