"""
Redis durability and eviction-policy health checks for the collab module.

The collab write-back pattern (live_spec in Redis, debounced to PostgreSQL)
relies on two Redis configuration properties:

1. AOF persistence (appendonly yes, appendfsync everysec): caps crash loss to
   ~1 s instead of the RDB snapshot interval (default 3600 s) which would lose
   every edit since the last snapshot.
2. Eviction policy starting with ``volatile-*``: live_spec keys all carry TTL,
   so under ``volatile-*`` they are only evicted as a last resort. Under
   ``allkeys-*`` the authoritative live spec can be evicted mid-session,
   silently dropping up to 10 s of in-flight edits.

Elevated to P0 because the entire write-back design depends on these
guarantees. Failures here never raise — they only warn so the application
still starts (for non-collab workloads) while ops is alerted.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from redis.exceptions import RedisError

from services.infrastructure.monitoring.critical_alert import CriticalAlertService

logger = logging.getLogger(__name__)

_MIN_REDIS_VERSION_COLLAB: Tuple[int, int, int] = (8, 0, 0)
_RECOMMENDED_APPENDONLY = "yes"
_RECOMMENDED_APPENDFSYNC = "everysec"
_SAFE_EVICTION_PREFIXES = ("volatile-", "noeviction")


_CONFIG_KEYS = ("appendonly", "appendfsync", "maxmemory-policy")


def _decode(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


def _parse_redis_version_tuple(version_str: str) -> Tuple[int, int, int]:
    """Parse ``redis_version`` from ``INFO server`` into a 3-tuple for comparison."""
    text = (version_str or "").strip()
    parts = text.split(".")
    nums: list[int] = []
    for part in parts[:3]:
        chunk = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(chunk) if chunk else 0)
    while len(nums) < 3:
        nums.append(0)
    return int(nums[0]), int(nums[1]), int(nums[2])


def _collab_disabled_env() -> bool:
    return os.getenv("COLLAB_DISABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


async def check_online_collab_redis_version(redis: Any) -> None:
    """
    Require Redis >= 8.0 when online collab is not explicitly disabled.

    Live workshop specs use RedisJSON (``JSON.*``) on the core key; Redis 8+
    is the supported floor. When ``COLLAB_DISABLED=1``, a sub-8 server only
    logs a warning.
    """
    if not redis:
        return
    try:
        info = await redis.info("server")
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.warning("[WorkshopRedisHealth] INFO server failed: %s", exc)
        return
    raw_ver = info.get("redis_version")
    if raw_ver is None:
        raw_ver = info.get(b"redis_version")
    version_str = _decode(raw_ver) if raw_ver is not None else ""
    parsed = _parse_redis_version_tuple(version_str)
    if parsed >= _MIN_REDIS_VERSION_COLLAB:
        logger.info(
            "[WorkshopRedisHealth] Redis version OK: %s (collab needs >= 8.0.0)",
            version_str,
        )
        return
    msg = (
        f"Redis {version_str!r} is below 8.0.0; online collab requires Redis 8+ "
        "(RedisJSON). Upgrade Redis or set COLLAB_DISABLED=1."
    )
    if _collab_disabled_env():
        logger.warning(
            "[WorkshopRedisHealth] %s — continuing because COLLAB_DISABLED=1",
            msg,
        )
        return
    try:
        CriticalAlertService.send_startup_failure_alert_sync(
            component="Redis",
            error_message=msg,
            details=(
                "Upgrade the Redis server to 8.0.0 or newer, or set "
                "COLLAB_DISABLED=1 to start without workshop collab."
            ),
        )
    except Exception as alert_error:  # pylint: disable=broad-except
        logger.error("Failed to send startup failure alert: %s", alert_error)
    logger.error("Application startup failed. %s", msg)
    os._exit(1)  # pylint: disable=protected-access


def _extract(raw: Any, key: str) -> Optional[str]:
    """Pull the value for *key* from a CONFIG GET response (dict or list)."""
    if not raw:
        return None
    if isinstance(raw, dict):
        for k, v in raw.items():
            if _decode(k) == key:
                return _decode(v)
        first = next(iter(raw.values()), None)
        return _decode(first) if first is not None else None
    if isinstance(raw, list) and len(raw) >= 2:
        return _decode(raw[1])
    return None


async def _config_get_pipelined(redis: Any) -> tuple:
    """
    Fetch all three CONFIG GET values in a single pipeline round-trip.

    Returns (appendonly, appendfsync, maxmemory_policy) strings or None on
    individual failures.
    """
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for key in _CONFIG_KEYS:
                pipe.config_get(key)
            results = await pipe.execute()
        return (
            _extract(results[0], "appendonly"),
            _extract(results[1], "appendfsync"),
            _extract(results[2], "maxmemory-policy"),
        )
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug("[WorkshopRedisHealth] pipelined CONFIG GET failed: %s", exc)
        return (None, None, None)


async def check_online_collab_redis_durability(redis: Any) -> Dict[str, Any]:
    """
    Emit warnings when Redis persistence/eviction settings jeopardise collab.

    Returns a report dict with keys ``appendonly``, ``appendfsync``,
    ``maxmemory_policy``, ``issues`` (list of human-readable problems).
    """
    report: Dict[str, Any] = {
        "appendonly": None,
        "appendfsync": None,
        "maxmemory_policy": None,
        "issues": [],
    }
    if not redis:
        report["issues"].append("redis_client_unavailable")
        logger.warning(
            "[WorkshopRedisHealth] Redis client unavailable; skipping durability check",
        )
        return report

    appendonly, appendfsync, policy = await _config_get_pipelined(redis)
    report["appendonly"] = appendonly
    report["appendfsync"] = appendfsync
    report["maxmemory_policy"] = policy

    if appendonly is not None and appendonly.lower() != _RECOMMENDED_APPENDONLY:
        issue = (
            f"Redis appendonly={appendonly!r} (expected {_RECOMMENDED_APPENDONLY!r}). "
            "Collab write-back can lose all edits since the last RDB snapshot on crash. "
            "Enable AOF in redis.conf or cloud provider config."
        )
        report["issues"].append(issue)
        logger.warning("[WorkshopRedisHealth] %s", issue)

    if (
        appendfsync is not None
        and appendfsync.lower() not in {_RECOMMENDED_APPENDFSYNC, "always"}
    ):
        issue = (
            f"Redis appendfsync={appendfsync!r} (expected "
            f"{_RECOMMENDED_APPENDFSYNC!r} or 'always'). Worst-case edit loss may "
            "exceed the 10s DB flush debounce window."
        )
        report["issues"].append(issue)
        logger.warning("[WorkshopRedisHealth] %s", issue)

    if policy is not None:
        policy_lower = policy.lower()
        safe = any(
            policy_lower.startswith(prefix) for prefix in _SAFE_EVICTION_PREFIXES
        )
        if not safe:
            issue = (
                f"Redis maxmemory-policy={policy!r} can evict TTL'd keys. "
                "Live collab specs are TTL-bearing and may be silently evicted "
                "mid-session under memory pressure, dropping up to 10s of "
                "in-flight edits. Switch to a volatile-* policy."
            )
            report["issues"].append(issue)
            logger.warning("[WorkshopRedisHealth] %s", issue)

    if not report["issues"]:
        logger.info(
            "[WorkshopRedisHealth] Redis durability OK: appendonly=%s "
            "appendfsync=%s maxmemory-policy=%s",
            appendonly, appendfsync, policy,
        )
    return report
