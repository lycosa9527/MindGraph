"""Shared Redis blacklist helpers for AbuseIPDB and CrowdSec (import leaf).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

logger = logging.getLogger(__name__)

KEY_BLACKLIST = "abuseipdb:blacklist:ips"

_SISMEMBER_CACHE: Dict[str, Tuple[float, bool]] = {}
_SISMEMBER_CACHE_LOCK = threading.Lock()
_SISMEMBER_CACHE_MAX_ENTRIES = 8192


class _SismemberCacheTtlState:
    """Process-lifetime SISMEMBER cache TTL snapshot holder."""

    value: Optional[int] = None


def clear_ip_reputation_sismember_cache() -> None:
    """Invalidate SISMEMBER cache after blacklist mutations (sync, merge, startup)."""
    with _SISMEMBER_CACHE_LOCK:
        _SISMEMBER_CACHE.clear()


def warm_sismember_cache_ttl_snapshot(ttl_seconds: int) -> None:
    """Store TTL snapshot after Redis init."""
    _SismemberCacheTtlState.value = max(0, ttl_seconds)


def invalidate_sismember_cache_ttl_snapshot() -> None:
    """Clear TTL snapshot (e.g. pytest)."""
    _SismemberCacheTtlState.value = None


def get_ip_reputation_sismember_cache_ttl_seconds(default_ttl: int) -> int:
    """In-process cache TTL for blacklist SISMEMBER; 0 disables caching."""
    if _SismemberCacheTtlState.value is not None:
        return _SismemberCacheTtlState.value
    return max(0, default_ttl)


def sismember_cache_get(ip: str, default_ttl: int) -> Optional[bool]:
    """Sismember cache get."""
    ttl = get_ip_reputation_sismember_cache_ttl_seconds(default_ttl)
    if ttl <= 0:
        return None
    now = time.monotonic()
    with _SISMEMBER_CACHE_LOCK:
        entry = _SISMEMBER_CACHE.get(ip)
        if entry is None:
            return None
        expires_at, value = entry
        if now >= expires_at:
            del _SISMEMBER_CACHE[ip]
            return None
        return value


def sismember_cache_set(ip: str, value: bool, default_ttl: int) -> None:
    """Sismember cache set."""
    ttl = get_ip_reputation_sismember_cache_ttl_seconds(default_ttl)
    if ttl <= 0:
        return
    expires_at = time.monotonic() + float(ttl)
    with _SISMEMBER_CACHE_LOCK:
        if len(_SISMEMBER_CACHE) >= _SISMEMBER_CACHE_MAX_ENTRIES:
            _SISMEMBER_CACHE.clear()
        _SISMEMBER_CACHE[ip] = (expires_at, value)


def pipeline_sadd_chunks(
    redis_client: Any,
    key: str,
    batch: List[str],
    chunk_size: int,
) -> int:
    """SADD batch in chunks via pipeline; return total added count."""
    if not batch:
        return 0
    pipe = redis_client.pipeline(transaction=False)
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i : i + chunk_size]
        pipe.sadd(key, *chunk)
    results = pipe.execute()
    return sum(int(x) for x in results)


async def pipeline_sadd_chunks_async(
    redis_client: Any,
    key: str,
    batch: List[str],
    chunk_size: int,
) -> int:
    """Async sibling of :func:`pipeline_sadd_chunks` for the asyncio Redis client."""
    if not batch:
        return 0
    async with redis_client.pipeline(transaction=False) as pipe:
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i : i + chunk_size]
            pipe.sadd(key, *chunk)
        results = await pipe.execute()
    return sum(int(x) for x in results)


def parse_retry_after_seconds(response: httpx.Response) -> Optional[int]:
    """Parse Retry-After header (seconds) if present."""
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def parse_baseline_file_lines(text: str) -> Set[str]:
    """Parse one IP per line; skip empty lines and # comments; validate IPv4/IPv6."""
    out: Set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        addr = line.split("%")[0].strip()
        try:
            ipaddress.ip_address(addr)
        except ValueError:
            continue
        out.add(addr)
    return out
