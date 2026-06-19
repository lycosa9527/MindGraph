"""Shared Redis INFO helpers for health and admin performance snapshots."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_REDIS_INFO_TTL_S = 5.0
_redis_info_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_redis_info_lock = asyncio.Lock()


async def cached_redis_info(redis_client: Any, section: str) -> Dict[str, Any]:
    """Per-process TTL cache around Redis ``INFO``."""
    now = time.monotonic()
    cached = _redis_info_cache.get(section)
    if cached is not None and (now - cached[0]) < _REDIS_INFO_TTL_S:
        return cached[1]

    async with _redis_info_lock:
        cached = _redis_info_cache.get(section)
        if cached is not None and (time.monotonic() - cached[0]) < _REDIS_INFO_TTL_S:
            return cached[1]
        try:
            data = await redis_client.info(section)
        except REDIS_ERRORS as exc:
            logger.debug("Redis INFO(%s) fetch failed: %s", section, exc)
            data = {}
        _redis_info_cache[section] = (time.monotonic(), data or {})
        return _redis_info_cache[section][1]


async def fetch_redis_memory_stats(redis_client: Any) -> Dict[str, Any]:
    """Fetch memory stats from Redis INFO memory section."""
    mem_info = await cached_redis_info(redis_client, "memory")
    if not mem_info:
        return {}
    return {
        "used_memory_human": mem_info.get("used_memory_human", "unknown"),
        "used_memory_peak_human": mem_info.get("used_memory_peak_human", "unknown"),
        "mem_fragmentation_ratio": mem_info.get("mem_fragmentation_ratio", None),
    }
