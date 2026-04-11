"""
CrowdSec Console blocklist merge (Raw IP List integration).

Fetches plaintext IPs from the integration endpoint and SADDs into the shared Redis
blacklist set used with AbuseIPDB. See:
https://docs.crowdsec.net/u/integrations/rawiplist/
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
from redis.exceptions import RedisError

from services.infrastructure.security import abuseipdb_service
from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

KEY_CROWDSEC_META = "crowdsec:blocklist:meta"

_DEFAULT_CROWDSEC_INTEGRATION_API_BASE = (
    "https://admin.api.crowdsec.net/v1/integrations"
)


def _mindgraph_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").lower().strip()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def crowdsec_blocklist_credentials_configured() -> bool:
    """True when username and password are set (Console integration credentials)."""
    user = os.getenv("CROWDSEC_BLOCKLIST_USERNAME", "").strip()
    password = os.getenv("CROWDSEC_BLOCKLIST_PASSWORD", "").strip()
    return bool(user and password)


def crowdsec_blocklist_endpoint_configured() -> bool:
    """True when URL or integration id is set."""
    url = os.getenv("CROWDSEC_BLOCKLIST_URL", "").strip()
    if url:
        return True
    integration_id = os.getenv("CROWDSEC_BLOCKLIST_INTEGRATION_ID", "").strip()
    return bool(integration_id)


def crowdsec_blocklist_master_enabled() -> bool:
    """True when CrowdSec blocklist merge may run (operator opted in and configured)."""
    if not _env_bool("CROWDSEC_BLOCKLIST_ENABLED", False):
        return False
    if not crowdsec_blocklist_credentials_configured():
        return False
    return crowdsec_blocklist_endpoint_configured()


def crowdsec_blocklist_sync_enabled() -> bool:
    return crowdsec_blocklist_master_enabled() and _env_bool(
        "CROWDSEC_BLOCKLIST_SYNC_ENABLED", True
    )


def crowdsec_blocklist_lookup_enabled() -> bool:
    """Use shared Redis blacklist for blocking (CrowdSec-only or with AbuseIPDB)."""
    return crowdsec_blocklist_master_enabled() and _env_bool(
        "CROWDSEC_BLOCKLIST_LOOKUP_ENABLED", True
    )


def get_crowdsec_sync_interval_seconds() -> int:
    """
    Seconds between CrowdSec pull attempts when AbuseIPDB sync is not driving the loop.

    Default and minimum 86400 (once per day); community tiers are often limited to ~1 pull / 24h.
    """
    return max(86400, _env_int("CROWDSEC_BLOCKLIST_SYNC_INTERVAL_SECONDS", 86400))


def get_crowdsec_min_interval_seconds() -> int:
    """Skip network fetch if last successful merge was more recent than this."""
    return max(60, _env_int("CROWDSEC_BLOCKLIST_MIN_INTERVAL_SECONDS", 82800))


def crowdsec_baseline_file_enabled() -> bool:
    """Merge shipped baseline from data/crowdsec/blocklist_baseline.txt into Redis."""
    return _env_bool("CROWDSEC_BASELINE_ENABLED", True)


def crowdsec_baseline_blacklist_path() -> Path:
    override = os.getenv("CROWDSEC_BASELINE_FILE", "").strip()
    if override:
        path = Path(override)
        if path.is_absolute():
            return path
        return _mindgraph_root() / path
    return _mindgraph_root() / "data" / "crowdsec" / "blocklist_baseline.txt"


def apply_crowdsec_baseline_from_file() -> int:
    """
    SADD baseline IPs from data/crowdsec/blocklist_baseline.txt into shared blacklist.

    Same pattern as AbuseIPDB baseline: call at startup and after AbuseIPDB replace sync.
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
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("[CrowdSec] could not read baseline file %s: %s", path, exc)
        return 0

    ips = abuseipdb_service.parse_baseline_file_lines(text)
    if not ips:
        logger.debug("[CrowdSec] baseline file has no valid IPs: %s", path)
        return 0

    r = get_redis()
    if not r:
        return 0

    batch = list(ips)
    chunk_size = 2000
    try:
        added_total = abuseipdb_service.pipeline_sadd_chunks(
            r, abuseipdb_service.KEY_BLACKLIST, batch, chunk_size
        )
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
    user = os.getenv("CROWDSEC_BLOCKLIST_USERNAME", "").strip()
    password = os.getenv("CROWDSEC_BLOCKLIST_PASSWORD", "").strip()
    return user, password


def _get_last_merge_unix() -> Optional[float]:
    if not is_redis_available():
        return None
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(KEY_CROWDSEC_META)
        if not raw:
            return None
        data = json.loads(raw)
        ts = data.get("last_merge_unix")
        if isinstance(ts, (int, float)):
            return float(ts)
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.debug("[CrowdSec] could not read meta: %s", exc)
    return None


def _set_last_merge_meta(count: int) -> None:
    if not is_redis_available():
        return
    r = get_redis()
    if not r:
        return
    payload = json.dumps({"last_merge_unix": time.time(), "count": count})
    try:
        r.set(KEY_CROWDSEC_META, payload)
    except OSError as exc:
        logger.debug("[CrowdSec] could not write meta: %s", exc)


def _should_skip_due_to_min_interval() -> bool:
    last = _get_last_merge_unix()
    if last is None:
        return False
    elapsed = time.time() - last
    return elapsed < float(get_crowdsec_min_interval_seconds())


def _sadd_ips_chunked(ips: set[str]) -> int:
    if not is_redis_available() or not ips:
        return 0
    r = get_redis()
    if not r:
        return 0
    batch = list(ips)
    chunk_size = 2000
    return abuseipdb_service.pipeline_sadd_chunks(
        r, abuseipdb_service.KEY_BLACKLIST, batch, chunk_size
    )


async def merge_crowdsec_blocklist_from_network() -> Dict[str, Any]:
    """
    GET Raw IP List content and SADD into shared KEY_BLACKLIST.

    Respects CROWDSEC_BLOCKLIST_MIN_INTERVAL_SECONDS to avoid 429 on community tiers.
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

    if _should_skip_due_to_min_interval():
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
        retry_after = abuseipdb_service.parse_retry_after_seconds(response) or 3600
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
    ips = abuseipdb_service.parse_baseline_file_lines(body)
    if not ips:
        logger.warning("[CrowdSec] blocklist response contained no valid IPs")
        result["error"] = "empty_or_invalid"
        return result

    try:
        added = _sadd_ips_chunked(ips)
    except (OSError, RedisError) as exc:
        result["error"] = str(exc)
        logger.warning("[CrowdSec] blocklist Redis SADD failed: %s", exc)
        return result

    _set_last_merge_meta(len(ips))
    result["ok"] = True
    result["count"] = len(ips)
    logger.info(
        "[CrowdSec] merged %s IPs into blacklist (new members this round: %s)",
        len(ips),
        added,
    )
    abuseipdb_service.clear_ip_reputation_sismember_cache()
    return result


def ip_reputation_blacklist_lookup_active() -> bool:
    """True if middleware should consult the shared Redis blacklist set."""
    from services.infrastructure.security import ip_reputation_env_snapshot

    return ip_reputation_env_snapshot.blacklist_lookup_active()
