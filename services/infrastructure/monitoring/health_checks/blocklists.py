"""AbuseIPDB and CrowdSec blocklist dates for health probes.

The public ``/health`` route reads the date already stored in Redis and never
waits on COS. The published snapshot is refreshed in the background (and on
``/health/all``) so a slow object store cannot fail a load-balancer probe.
A stale database is reported with ``newest: false`` and does not change the
HTTP status: the in-process health monitor sends SMS for degraded checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from services.infrastructure.security.ip_reputation_env_flags import (
    abuseipdb_blacklist_sync_enabled,
    crowdsec_blocklist_sync_enabled,
)
from services.infrastructure.sync.abuseipdb_cos_sync import (
    get_abuseipdb_cos_status,
    read_abuseipdb_cos_meta,
)
from services.infrastructure.sync.cos_sync_env import cos_sync_role
from services.infrastructure.sync.crowdsec_cos_sync import (
    get_crowdsec_cos_status,
    read_crowdsec_cos_meta,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_COS_CACHE_TTL_SECONDS = 60.0
_COS_BACKOFF_SECONDS = 15.0
_COS_FETCH_TIMEOUT_SECONDS = 2.5
# Publisher writes the local date, then the COS date a moment later. Sync is daily.
_NEWEST_SKEW_SECONDS = 120.0


class _CosMetaCache:
    """Last published COS dates. Local Redis dates are always read live."""

    __slots__ = ("abuseipdb", "crowdsec", "expires_at", "lock", "task")

    def __init__(self) -> None:
        self.abuseipdb: Optional[Dict[str, Any]] = None
        self.crowdsec: Optional[Dict[str, Any]] = None
        self.expires_at: float = 0.0
        self.lock = asyncio.Lock()
        self.task: Optional[asyncio.Task[None]] = None


_cos_cache = _CosMetaCache()


def _iso_date(meta: Optional[Dict[str, Any]]) -> Optional[str]:
    """Database date is the snapshot timestamp, the same field compared for freshness."""
    if not meta:
        return None
    stamp = meta.get("last_merge_unix")
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        return datetime.fromtimestamp(float(stamp), tz=timezone.utc).isoformat()
    return None


def _count(meta: Optional[Dict[str, Any]]) -> Optional[int]:
    if not meta:
        return None
    count = meta.get("count")
    if isinstance(count, int) and not isinstance(count, bool):
        return count
    return None


def _as_meta(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    return None


def blocklist_is_current(
    local_meta: Optional[Dict[str, Any]],
    cos_meta: Optional[Dict[str, Any]],
) -> Optional[bool]:
    """True when the loaded snapshot is at least as new as the published one."""
    if cos_meta is None:
        return None
    local_ts = local_meta.get("last_merge_unix") if local_meta else None
    cos_ts = cos_meta.get("last_merge_unix")
    if not isinstance(local_ts, (int, float)) or isinstance(local_ts, bool):
        return False
    if not isinstance(cos_ts, (int, float)) or isinstance(cos_ts, bool):
        return None
    return float(local_ts) + _NEWEST_SKEW_SECONDS >= float(cos_ts)


def describe_blocklist_feed(
    status: Dict[str, Any],
    *,
    compare: bool,
    enabled: bool,
) -> Dict[str, Any]:
    """Shape one blocklist's loaded date against the published COS date."""
    local = _as_meta(status.get("local_meta"))
    cos = _as_meta(status.get("cos_meta"))
    version = _iso_date(local)
    cos_version = _iso_date(cos)
    expected = bool(enabled or version or cos_version)
    newest: Optional[bool] = None
    if compare and expected:
        newest = blocklist_is_current(local, cos)
    return {
        "version": version,
        "count": _count(local),
        "cos_version": cos_version,
        "newest": newest,
        "expected": expected,
    }


def blocklist_health_status(abuseipdb: Dict[str, Any], crowdsec: Dict[str, Any]) -> str:
    """Report dates without turning a stale blocklist into a server outage."""
    expected = [feed for feed in (abuseipdb, crowdsec) if feed.get("expected")]
    if not expected:
        return "skipped"
    return "healthy"


def _empty_feed() -> Dict[str, Any]:
    return {
        "version": None,
        "count": None,
        "cos_version": None,
        "newest": None,
        "expected": False,
    }


def _public_feed(feed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": feed.get("version"),
        "count": feed.get("count"),
        "cos_version": feed.get("cos_version"),
        "newest": feed.get("newest"),
    }


def _cache_is_fresh() -> bool:
    return time.monotonic() < _cos_cache.expires_at


async def _refresh_cos_meta() -> None:
    """Fetch both published dates. Failures keep the previous snapshot."""
    async with _cos_cache.lock:
        if _cache_is_fresh():
            return
        try:
            abuse_meta, crowd_meta = await asyncio.wait_for(
                asyncio.gather(
                    asyncio.to_thread(read_abuseipdb_cos_meta),
                    asyncio.to_thread(read_crowdsec_cos_meta),
                ),
                timeout=_COS_FETCH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning("Blocklist COS date read timed out")
            _cos_cache.expires_at = time.monotonic() + _COS_BACKOFF_SECONDS
            return
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("Blocklist COS date read failed: %s", exc)
            _cos_cache.expires_at = time.monotonic() + _COS_BACKOFF_SECONDS
            return
        _cos_cache.abuseipdb = _as_meta(abuse_meta)
        _cos_cache.crowdsec = _as_meta(crowd_meta)
        _cos_cache.expires_at = time.monotonic() + _COS_CACHE_TTL_SECONDS


def _schedule_cos_refresh() -> None:
    if cos_sync_role() == "off" or _cache_is_fresh():
        return
    task = _cos_cache.task
    if task is not None and not task.done():
        return
    try:
        _cos_cache.task = asyncio.create_task(_refresh_cos_meta())
    except RuntimeError as exc:
        logger.debug("Blocklist COS date refresh was not scheduled: %s", exc)


async def _published_metas(*, wait: bool) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if cos_sync_role() == "off":
        return None, None
    if _cache_is_fresh():
        return _cos_cache.abuseipdb, _cos_cache.crowdsec
    if wait:
        await _refresh_cos_meta()
        return _cos_cache.abuseipdb, _cos_cache.crowdsec
    _schedule_cos_refresh()
    return _cos_cache.abuseipdb, _cos_cache.crowdsec


async def _local_statuses() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    abuse_status, crowd_status = await asyncio.gather(
        get_abuseipdb_cos_status(include_cos=False),
        get_crowdsec_cos_status(include_cos=False),
    )
    return abuse_status, crowd_status


async def blocklist_versions_snapshot(*, wait_for_cos: bool) -> Dict[str, Any]:
    """Local dates from Redis, published dates from a short-lived COS cache."""
    try:
        local_pair, cos_pair = await asyncio.gather(
            _local_statuses(),
            _published_metas(wait=wait_for_cos),
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("Blocklist date health check failed: %s", exc)
        empty = _empty_feed()
        return {
            "abuseipdb": empty,
            "crowdsec": empty,
            "status": "skipped",
        }

    compare = cos_sync_role() != "off"
    abuse_local, crowd_local = local_pair
    cos_abuse, cos_crowd = cos_pair
    abuseipdb = describe_blocklist_feed(
        {
            "local_meta": abuse_local.get("local_meta"),
            "cos_meta": cos_abuse,
        },
        compare=compare,
        enabled=abuseipdb_blacklist_sync_enabled(),
    )
    crowdsec = describe_blocklist_feed(
        {
            "local_meta": crowd_local.get("local_meta"),
            "cos_meta": cos_crowd,
        },
        compare=compare,
        enabled=crowdsec_blocklist_sync_enabled(),
    )
    return {
        "abuseipdb": abuseipdb,
        "crowdsec": crowdsec,
        "status": blocklist_health_status(abuseipdb, crowdsec),
    }


async def blocklist_versions_for_health() -> Dict[str, Any]:
    """Public /health view. Returns the Redis date immediately."""
    snapshot = await blocklist_versions_snapshot(wait_for_cos=False)
    abuse = snapshot.get("abuseipdb")
    crowd = snapshot.get("crowdsec")
    return {
        "abuseipdb": _public_feed(abuse if isinstance(abuse, dict) else _empty_feed()),
        "crowdsec": _public_feed(crowd if isinstance(crowd, dict) else _empty_feed()),
    }


async def check_blocklists_health() -> Dict[str, Any]:
    """Authenticated /health/all view. May wait briefly for the published date."""
    snapshot = await blocklist_versions_snapshot(wait_for_cos=True)
    abuse = snapshot.get("abuseipdb")
    crowd = snapshot.get("crowdsec")
    status = snapshot.get("status")
    if status not in ("healthy", "skipped"):
        status = "skipped"
    return {
        "status": status,
        "abuseipdb": _public_feed(abuse if isinstance(abuse, dict) else _empty_feed()),
        "crowdsec": _public_feed(crowd if isinstance(crowd, dict) else _empty_feed()),
    }
