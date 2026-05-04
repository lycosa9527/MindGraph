"""
Opt-in Redis 8 (and 8+ module) helpers for the workshop module.

Each helper:
  - Is activated only when its env flag is set.
  - Swallows ``RedisError`` / module-missing errors and returns a sentinel so
    callers can keep working on vanilla Redis.
  - Caches ``unsupported`` state per-process so later calls skip the wire
    round-trip entirely.

Env flags:
  COLLAB_REDIS_BLOOM_CODES     — Bloom filter workshop-code pre-check
  COLLAB_REDIS_TIMESERIES      — TS.ADD counters for ws metrics
  COLLAB_REDIS_TDIGEST         — TDIGEST streaming latency quantiles
  COLLAB_REDIS_TOPK            — TopK hot-room / hot-user tracking

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env flag helpers
# ---------------------------------------------------------------------------

def _flag_on(name: str) -> bool:
    return os.getenv(name, "0") not in ("0", "false", "False", "")


def bloom_codes_enabled() -> bool:
    return _flag_on("COLLAB_REDIS_BLOOM_CODES")


def timeseries_enabled() -> bool:
    return _flag_on("COLLAB_REDIS_TIMESERIES")


def tdigest_enabled() -> bool:
    return _flag_on("COLLAB_REDIS_TDIGEST")


def topk_enabled() -> bool:
    return _flag_on("COLLAB_REDIS_TOPK")


def client_tracking_enabled() -> bool:
    """True when ``COLLAB_REDIS_CLIENT_TRACKING=1`` opts in to server-assisted caching."""
    return _flag_on("COLLAB_REDIS_CLIENT_TRACKING")


# ---------------------------------------------------------------------------
# CLIENT TRACKING: server-assisted client-side caching invalidation
# ---------------------------------------------------------------------------

class _ClientTrackingState:
    """Tracks whether CLIENT TRACKING was successfully enabled on the connection."""

    supported: Optional[bool] = None


async def enable_client_tracking(redis: Any) -> bool:
    """
    Send ``CLIENT TRACKING on BCAST PREFIX workshop:`` to the Redis server so
    it pushes key-invalidation messages when watched workshop keys change.

    This is only useful when the application explicitly caches the values of
    those keys in-process (e.g., room visibility string).  Callers that do not
    maintain an explicit local cache should skip this.

    Returns True when the server acknowledged; False otherwise.  Caches the
    result so repeated calls are no-ops.
    """
    if not client_tracking_enabled():
        return False
    if _ClientTrackingState.supported is not None:
        return bool(_ClientTrackingState.supported)
    if not redis:
        return False
    try:
        await redis.execute_command(
            "CLIENT", "TRACKING", "on", "BCAST",
            "PREFIX", "workshop:",
            "NOLOOP",
        )
        _ClientTrackingState.supported = True
        logger.info("[Redis8] CLIENT TRACKING enabled (PREFIX workshop:, BCAST, NOLOOP)")
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "unknown command" in msg or "not supported" in msg:
            logger.info("[Redis8] CLIENT TRACKING unsupported: %s", exc)
        else:
            logger.debug("[Redis8] CLIENT TRACKING failed: %s", exc)
        _ClientTrackingState.supported = False
        return False


# ---------------------------------------------------------------------------
# Bloom filter: workshop-code collision pre-check
# ---------------------------------------------------------------------------

_BLOOM_CODES_KEY = "workshop:bloom:codes"
_BLOOM_CODES_CAPACITY = 1_000_000
_BLOOM_CODES_ERROR_RATE = 0.001


class _BloomState:
    """Module-private state wrapper (pylint treats module globals as constants)."""

    supported: Optional[bool] = None
    reserved: bool = False


async def _ensure_bloom_codes_reserved(redis: Any) -> bool:
    """``BF.RESERVE`` idempotently; cached so we issue the reserve once per process."""
    if _BloomState.supported is False:
        return False
    if _BloomState.reserved:
        return True
    try:
        await redis.execute_command(
            "BF.RESERVE",
            _BLOOM_CODES_KEY,
            _BLOOM_CODES_ERROR_RATE,
            _BLOOM_CODES_CAPACITY,
        )
        _BloomState.supported = True
        _BloomState.reserved = True
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "item exists" in msg or "already exists" in msg:
            _BloomState.supported = True
            _BloomState.reserved = True
            return True
        if "unknown command" in msg or "module" in msg:
            _BloomState.supported = False
            logger.info(
                "[Redis8] Bloom filter unavailable (BF.RESERVE failed: %s) — "
                "bloom pre-check disabled",
                exc,
            )
            return False
        logger.debug("[Redis8] BF.RESERVE error: %s", exc)
        return False


async def bloom_may_contain_online_collab_code(code: str) -> Optional[bool]:
    """
    ``BF.EXISTS`` returns ``True`` when the code is *probably* taken (small FP
    chance), ``False`` when it's definitely free, and ``None`` when Redis or
    the Bloom module is unavailable and callers must fall back to SQL.
    """
    if not bloom_codes_enabled():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    if not await _ensure_bloom_codes_reserved(redis):
        return None
    try:
        result = await redis.execute_command("BF.EXISTS", _BLOOM_CODES_KEY, code)
        if result is None:
            return None
        return bool(int(result))
    except RedisError as exc:
        logger.debug("[Redis8] BF.EXISTS failed code=%s: %s", code, exc)
        return None


async def bloom_add_online_collab_code(code: str) -> None:
    """Best-effort ``BF.ADD`` after a successful SQL insert."""
    if not bloom_codes_enabled():
        return
    redis = get_async_redis()
    if not redis:
        return
    if not await _ensure_bloom_codes_reserved(redis):
        return
    try:
        await redis.execute_command("BF.ADD", _BLOOM_CODES_KEY, code)
    except RedisError as exc:
        logger.debug("[Redis8] BF.ADD failed code=%s: %s", code, exc)


# ---------------------------------------------------------------------------
# TimeSeries: cross-worker-aggregated counters for ws_metrics
# ---------------------------------------------------------------------------

class _TSState:
    """Module-private state wrapper for TimeSeries support/key cache."""

    supported: Optional[bool] = None
    created: set[str] = set()


async def _ensure_ts_created(redis: Any, key: str, labels: dict[str, str]) -> bool:
    """``TS.CREATE`` once per key per process (idempotent)."""
    if _TSState.supported is False:
        return False
    if key in _TSState.created:
        return True
    try:
        cmd = ["TS.CREATE", key, "RETENTION", "604800000", "DUPLICATE_POLICY", "SUM"]
        if labels:
            cmd.append("LABELS")
            for k, v in labels.items():
                cmd.extend([k, v])
        await redis.execute_command(*cmd)
        _TSState.supported = True
        _TSState.created.add(key)
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "already exists" in msg:
            _TSState.supported = True
            _TSState.created.add(key)
            return True
        if "unknown command" in msg or "module" in msg:
            _TSState.supported = False
            logger.info(
                "[Redis8] TimeSeries module unavailable (%s) — "
                "TS counters disabled", exc,
            )
            return False
        logger.debug("[Redis8] TS.CREATE error key=%s: %s", key, exc)
        return False


async def ts_record_counter(metric: str, value: float = 1.0) -> None:
    """``TS.ADD workshop:ts:{metric} * <value>`` with best-effort semantics."""
    if not timeseries_enabled():
        return
    redis = get_async_redis()
    if not redis:
        return
    key = f"workshop:ts:{metric}"
    if not await _ensure_ts_created(redis, key, {"metric": metric}):
        return
    try:
        await redis.execute_command("TS.ADD", key, "*", float(value))
    except RedisError as exc:
        logger.debug("[Redis8] TS.ADD failed metric=%s: %s", metric, exc)


# ---------------------------------------------------------------------------
# TDIGEST: streaming latency quantiles
# ---------------------------------------------------------------------------

_TDIGEST_COMPRESSION = 100


class _TDigestState:
    """Module-private state wrapper for TDIGEST support/key cache."""

    supported: Optional[bool] = None
    created: set[str] = set()


async def _ensure_tdigest_created(redis: Any, key: str) -> bool:
    """``TDIGEST.CREATE`` once per key per process."""
    if _TDigestState.supported is False:
        return False
    if key in _TDigestState.created:
        return True
    try:
        await redis.execute_command(
            "TDIGEST.CREATE", key, "COMPRESSION", _TDIGEST_COMPRESSION,
        )
        _TDigestState.supported = True
        _TDigestState.created.add(key)
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "already exists" in msg or "key already" in msg:
            _TDigestState.supported = True
            _TDigestState.created.add(key)
            return True
        if "unknown command" in msg or "module" in msg:
            _TDigestState.supported = False
            logger.info(
                "[Redis8] TDIGEST module unavailable (%s) — "
                "latency quantiles disabled", exc,
            )
            return False
        logger.debug("[Redis8] TDIGEST.CREATE error key=%s: %s", key, exc)
        return False


async def tdigest_record_latency(category: str, millis: float) -> None:
    """Record one latency sample into ``workshop:tdigest:{category}`` (ms)."""
    if not tdigest_enabled() or millis < 0:
        return
    redis = get_async_redis()
    if not redis:
        return
    key = f"workshop:tdigest:{category}"
    if not await _ensure_tdigest_created(redis, key):
        return
    try:
        await redis.execute_command("TDIGEST.ADD", key, float(millis))
    except RedisError as exc:
        logger.debug("[Redis8] TDIGEST.ADD failed category=%s: %s", category, exc)


async def tdigest_quantiles(category: str) -> Optional[dict[str, float]]:
    """Return ``{"p50": ..., "p95": ..., "p99": ...}`` when TDIGEST is available."""
    if not tdigest_enabled():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    key = f"workshop:tdigest:{category}"
    if not await _ensure_tdigest_created(redis, key):
        return None
    try:
        result = await redis.execute_command(
            "TDIGEST.QUANTILE", key, "0.5", "0.95", "0.99",
        )
    except RedisError as exc:
        logger.debug(
            "[Redis8] TDIGEST.QUANTILE failed category=%s: %s", category, exc,
        )
        return None
    if result is None:
        return None
    try:
        p50, p95, p99 = [float(v) for v in result]
    except (TypeError, ValueError, IndexError):
        return None
    return {"p50": p50, "p95": p95, "p99": p99}


# ---------------------------------------------------------------------------
# TopK: hottest rooms / most active users
# ---------------------------------------------------------------------------

_TOPK_ROOMS_KEY = "workshop:topk:rooms"
_TOPK_USERS_KEY = "workshop:topk:users"
_TOPK_K = 50
_TOPK_WIDTH = 2000
_TOPK_DEPTH = 7
_TOPK_DECAY = 0.9


class _TopKState:
    """Module-private state wrapper for TopK support/key cache."""

    supported: Optional[bool] = None
    reserved: set[str] = set()


async def _ensure_topk_reserved(redis: Any, key: str) -> bool:
    if _TopKState.supported is False:
        return False
    if key in _TopKState.reserved:
        return True
    try:
        await redis.execute_command(
            "TOPK.RESERVE", key, _TOPK_K, _TOPK_WIDTH, _TOPK_DEPTH, _TOPK_DECAY,
        )
        _TopKState.supported = True
        _TopKState.reserved.add(key)
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "item exists" in msg or "already" in msg:
            _TopKState.supported = True
            _TopKState.reserved.add(key)
            return True
        if "unknown command" in msg or "module" in msg:
            _TopKState.supported = False
            logger.info(
                "[Redis8] TopK module unavailable (%s) — hot-room tracking disabled",
                exc,
            )
            return False
        logger.debug("[Redis8] TOPK.RESERVE error key=%s: %s", key, exc)
        return False


async def topk_record_room_activity(code: str) -> None:
    """Register one activity sample for room ``code``."""
    if not topk_enabled() or not code:
        return
    redis = get_async_redis()
    if not redis:
        return
    if not await _ensure_topk_reserved(redis, _TOPK_ROOMS_KEY):
        return
    try:
        await redis.execute_command("TOPK.ADD", _TOPK_ROOMS_KEY, code)
    except RedisError as exc:
        logger.debug("[Redis8] TOPK.ADD room failed code=%s: %s", code, exc)


async def topk_record_user_activity(user_id: int) -> None:
    """Register one activity sample for ``user_id``."""
    if not topk_enabled() or user_id is None:
        return
    redis = get_async_redis()
    if not redis:
        return
    if not await _ensure_topk_reserved(redis, _TOPK_USERS_KEY):
        return
    try:
        await redis.execute_command(
            "TOPK.ADD", _TOPK_USERS_KEY, f"user:{int(user_id)}",
        )
    except RedisError as exc:
        logger.debug(
            "[Redis8] TOPK.ADD user failed user_id=%s: %s", user_id, exc,
        )


async def zadd_gt_score(
    redis: Any,
    key: str,
    score: float,
    member: str,
    ttl_sec: int,
) -> None:
    """
    Atomically update a sorted set member's score only when the new score is
    greater than the existing one (Redis 3.0.2+ ``ZADD key GT``).

    Use-case: participant last-activity timestamp in a ZSET — prevents older
    writes from overwriting a newer timestamp, eliminating the need for
    per-field read-before-write logic.

    Falls back to plain ``ZADD`` (no GT guard) on older Redis.
    """
    try:
        await redis.execute_command("ZADD", key, "GT", score, member)
        if ttl_sec > 0:
            await redis.expire(key, ttl_sec, gt=True)
    except RedisError:
        try:
            await redis.zadd(key, {member: score})
            if ttl_sec > 0:
                await redis.expire(key, ttl_sec, gt=True)
        except RedisError as exc:
            logger.debug("[Redis8] zadd_gt_score fallback failed key=%s: %s", key, exc)


async def topk_list_rooms() -> Optional[list[str]]:
    """``TOPK.LIST`` the hot rooms; ``None`` when Redis/module unavailable."""
    if not topk_enabled():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    if not await _ensure_topk_reserved(redis, _TOPK_ROOMS_KEY):
        return None
    try:
        raw = await redis.execute_command("TOPK.LIST", _TOPK_ROOMS_KEY)
    except RedisError as exc:
        logger.debug("[Redis8] TOPK.LIST rooms failed: %s", exc)
        return None
    out: list[str] = []
    for item in raw or []:
        if isinstance(item, bytes):
            out.append(item.decode("utf-8", errors="replace"))
        elif item is not None:
            out.append(str(item))
    return out
