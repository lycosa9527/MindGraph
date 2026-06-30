"""
CrowdSec Console blocklist merge (Raw IP List integration).

Fetches plaintext IPs from the integration endpoint and SADDs into the shared Redis
blacklist set used with AbuseIPDB. See:
https://docs.crowdsec.net/u/integrations/rawiplist/

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
from redis.exceptions import RedisError

from services.infrastructure.security import ip_reputation_env_flags, ip_reputation_env_snapshot
from services.infrastructure.security.ip_reputation_blacklist_redis import (
    KEY_BLACKLIST,
    clear_ip_reputation_sismember_cache,
    parse_baseline_file_lines,
    parse_retry_after_seconds,
    pipeline_sadd_chunks_async,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

KEY_CROWDSEC_META = "crowdsec:blocklist:meta"


class _LastCrowdsecNetworkMerge:
    """Holds last successful network merge payload for COS publisher upload."""

    __slots__ = ("body", "count")

    def __init__(self) -> None:
        """init."""
        self.body: str = ""
        self.count: int = 0


_last_crowdsec_network_merge = _LastCrowdsecNetworkMerge()


def take_last_crowdsec_network_merge_payload() -> Optional[tuple[str, int]]:
    """Return and clear last network merge body for COS publish (publisher only)."""
    if not _last_crowdsec_network_merge.body:
        return None
    payload = (_last_crowdsec_network_merge.body, _last_crowdsec_network_merge.count)
    _last_crowdsec_network_merge.body = ""
    _last_crowdsec_network_merge.count = 0
    return payload


_DEFAULT_CROWDSEC_INTEGRATION_API_BASE = "https://admin.api.crowdsec.net/v1/integrations"


def _mindgraph_root() -> Path:
    """Mindgraph root."""
    return Path(__file__).resolve().parent.parent.parent.parent


_env_bool = ip_reputation_env_flags.env_bool
_env_int = ip_reputation_env_flags.env_int
crowdsec_blocklist_credentials_configured = ip_reputation_env_flags.crowdsec_blocklist_credentials_configured
crowdsec_blocklist_endpoint_configured = ip_reputation_env_flags.crowdsec_blocklist_endpoint_configured
crowdsec_blocklist_master_enabled = ip_reputation_env_flags.crowdsec_blocklist_master_enabled
crowdsec_blocklist_sync_enabled = ip_reputation_env_flags.crowdsec_blocklist_sync_enabled
crowdsec_blocklist_lookup_enabled = ip_reputation_env_flags.crowdsec_blocklist_lookup_enabled


def get_crowdsec_sync_interval_seconds() -> int:
    """
    Minimum seconds between CrowdSec Raw IP List pulls (tier / documentation).

    The in-process scheduler runs on BACKUP_HOUR (see abuseipdb_scheduler), not on this
    value. Default and minimum 86400; community tiers are often limited to ~1 pull / 24h.
    """
    return max(86400, _env_int("CROWDSEC_BLOCKLIST_SYNC_INTERVAL_SECONDS", 86400))


def get_crowdsec_min_interval_seconds() -> int:
    """Skip network fetch if last successful merge was more recent than this."""
    return max(60, _env_int("CROWDSEC_BLOCKLIST_MIN_INTERVAL_SECONDS", 82800))


def crowdsec_baseline_file_enabled() -> bool:
    """Merge shipped baseline from data/crowdsec/blocklist_baseline.txt into Redis."""
    return _env_bool("CROWDSEC_BASELINE_ENABLED", True)


def crowdsec_baseline_blacklist_path() -> Path:
    """Crowdsec baseline blacklist path."""
    override = os.getenv("CROWDSEC_BASELINE_FILE", "").strip()
    if override:
        path = Path(override)
        if path.is_absolute():
            return path
        return _mindgraph_root() / path
    return _mindgraph_root() / "data" / "crowdsec" / "blocklist_baseline.txt"


async def apply_crowdsec_baseline_from_file_async() -> int:
    """SADD baseline IPs from data/crowdsec/blocklist_baseline.txt into shared blacklist.

    Same pattern as :func:`abuseipdb_service.apply_blacklist_baseline_from_file_async`:
    call at startup and after each AbuseIPDB replace sync.  Filesystem read is
    offloaded with ``asyncio.to_thread``; all Redis work uses the async client.
    """
    if not crowdsec_baseline_file_enabled():
        return 0
    if not crowdsec_blocklist_master_enabled():
        return 0
    if not is_redis_available():
        return 0

    path = crowdsec_baseline_blacklist_path()
    if not path.is_file():
        logger.debug("[CrowdSec] baseline file not found: %s", path)
        return 0

    try:
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    except OSError as exc:
        logger.warning("[CrowdSec] could not read baseline file %s: %s", path, exc)
        return 0

    ips = parse_baseline_file_lines(text)
    if not ips:
        logger.debug("[CrowdSec] baseline file has no valid IPs: %s", path)
        return 0

    redis = get_async_redis()
    if not redis:
        return 0

    batch = list(ips)
    chunk_size = 2000
    try:
        added_total = await pipeline_sadd_chunks_async(redis, KEY_BLACKLIST, batch, chunk_size)
    except (OSError, RedisError) as exc:
        logger.warning("[CrowdSec] baseline SADD failed: %s", exc)
        return 0

    logger.info(
        "[CrowdSec] merged %s baseline IPs from %s (new members this round: %s)",
        len(ips),
        path,
        added_total,
    )
    return len(ips)


def _crowdsec_integration_api_base() -> str:
    """
    Prefix for .../integrations/{id}/content when using CROWDSEC_BLOCKLIST_INTEGRATION_ID.

    Override CROWDSEC_BLOCKLIST_API_BASE in .env for non-default Console API hosts.
    """
    raw = os.getenv("CROWDSEC_BLOCKLIST_API_BASE", "").strip().rstrip("/")
    if raw:
        return raw
    return _DEFAULT_CROWDSEC_INTEGRATION_API_BASE


def build_crowdsec_blocklist_content_url() -> Optional[str]:
    """Resolve Console Raw IP List URL from CROWDSEC_BLOCKLIST_URL or integration id."""
    full = os.getenv("CROWDSEC_BLOCKLIST_URL", "").strip()
    if full:
        return full
    integration_id = os.getenv("CROWDSEC_BLOCKLIST_INTEGRATION_ID", "").strip()
    if not integration_id:
        return None
    safe = quote(integration_id, safe="")
    return f"{_crowdsec_integration_api_base()}/{safe}/content"


def _basic_auth() -> Tuple[str, str]:
    """Basic auth."""
    user = os.getenv("CROWDSEC_BLOCKLIST_USERNAME", "").strip()
    password = os.getenv("CROWDSEC_BLOCKLIST_PASSWORD", "").strip()
    return user, password


async def _get_last_merge_unix_async() -> Optional[float]:
    """Get last merge unix async."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(KEY_CROWDSEC_META)
        if not raw:
            return None
        data = json.loads(raw)
        ts = data.get("last_merge_unix")
        if isinstance(ts, (int, float)):
            return float(ts)
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.debug("[CrowdSec] could not read meta: %s", exc)
    return None


async def _set_last_merge_meta_async(count: int) -> None:
    """Set last merge meta async."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    payload = json.dumps({"last_merge_unix": time.time(), "count": count})
    try:
        await redis.set(KEY_CROWDSEC_META, payload)
    except OSError as exc:
        logger.debug("[CrowdSec] could not write meta: %s", exc)


async def _should_skip_due_to_min_interval_async() -> bool:
    """Should skip due to min interval async."""
    last = await _get_last_merge_unix_async()
    if last is None:
        return False
    elapsed = time.time() - last
    return elapsed < float(get_crowdsec_min_interval_seconds())


async def _sadd_ips_chunked_async(ips: set[str]) -> int:
    """Sadd ips chunked async."""
    if not is_redis_available() or not ips:
        return 0
    redis = get_async_redis()
    if not redis:
        return 0
    batch = list(ips)
    chunk_size = 2000
    return await pipeline_sadd_chunks_async(redis, KEY_BLACKLIST, batch, chunk_size)


async def merge_crowdsec_blocklist_from_network(force: bool = False) -> Dict[str, Any]:
    """
    GET Raw IP List content and SADD into shared KEY_BLACKLIST.

    Unless force is True, respects CROWDSEC_BLOCKLIST_MIN_INTERVAL_SECONDS to avoid 429
    on community tiers. When force is True, the min-interval skip is not applied (daily
    scheduled run aligned with BACKUP_HOUR).
    """
    result: Dict[str, Any] = {
        "ok": False,
        "count": 0,
        "skipped": False,
        "error": None,
        "rate_limited": False,
        "retry_after_seconds": None,
    }

    if not crowdsec_blocklist_sync_enabled():
        result["error"] = "disabled"
        return result

    if not force and await _should_skip_due_to_min_interval_async():
        result["skipped"] = True
        result["ok"] = True
        return result

    url = build_crowdsec_blocklist_content_url()
    if not url:
        result["error"] = "missing_url"
        return result

    user, password = _basic_auth()
    try:
        async with httpx.AsyncClient(timeout=300.0) as http_client:
            response = await http_client.get(
                url,
                auth=(user, password),
                headers={"Accept": "text/plain"},
            )
    except (httpx.HTTPError, OSError) as exc:
        result["error"] = str(exc)
        logger.warning("[CrowdSec] blocklist download failed: %s", exc)
        return result

    if response.status_code == 429:
        retry_after = parse_retry_after_seconds(response) or 3600
        result["error"] = "rate_limited"
        result["rate_limited"] = True
        result["retry_after_seconds"] = retry_after
        logger.warning(
            "[CrowdSec] HTTP 429 (rate limited) retry_after=%s",
            retry_after,
        )
        return result

    if response.status_code != 200:
        err = (response.text or "")[:500]
        result["error"] = f"HTTP {response.status_code}: {err}"
        logger.warning("[CrowdSec] blocklist HTTP %s: %s", response.status_code, err[:200])
        return result

    body = response.text or ""
    ips = parse_baseline_file_lines(body)
    if not ips:
        logger.warning("[CrowdSec] blocklist response contained no valid IPs")
        result["error"] = "empty_or_invalid"
        return result

    try:
        added = await _sadd_ips_chunked_async(ips)
    except (OSError, RedisError) as exc:
        result["error"] = str(exc)
        logger.warning("[CrowdSec] blocklist Redis SADD failed: %s", exc)
        return result

    await _set_last_merge_meta_async(len(ips))
    result["ok"] = True
    result["count"] = len(ips)
    _last_crowdsec_network_merge.body = body
    _last_crowdsec_network_merge.count = len(ips)
    logger.info(
        "[CrowdSec] merged %s IPs into blacklist (new members this round: %s)",
        len(ips),
        added,
    )
    clear_ip_reputation_sismember_cache()
    return result


def ip_reputation_blacklist_lookup_active() -> bool:
    """True if middleware should consult the shared Redis blacklist set."""
    return ip_reputation_env_snapshot.blacklist_lookup_active()
