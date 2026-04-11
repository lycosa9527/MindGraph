"""
AbuseIPDB integration: IP reputation check, reporting, and blacklist sync.

Uses AbuseIPDB API v2 (https://docs.abuseipdb.com/).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from redis.exceptions import RedisError

from services.infrastructure.security.abuseipdb_blacklist_parse import (
    parse_abuseipdb_blacklist_plaintext,
)
from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

ABUSEIPDB_API_BASE = "https://api.abuseipdb.com/api/v2"

KEY_BLACKLIST = "abuseipdb:blacklist:ips"
KEY_BLACKLIST_META = "abuseipdb:blacklist:meta"
KEY_CHECK_PREFIX = "abuseipdb:check:"
KEY_REPORT_DEDUPE_PREFIX = "abuseipdb:report:dedupe:"

CATEGORY_BRUTE_FORCE = 18

_SISMEMBER_CACHE: Dict[str, Tuple[float, bool]] = {}
_SISMEMBER_CACHE_LOCK = threading.Lock()
_SISMEMBER_CACHE_MAX_ENTRIES = 8192
_SISMEMBER_CACHE_TTL_SNAPSHOT: Optional[int] = None


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


def abuseipdb_master_enabled() -> bool:
    """True when AbuseIPDB features may run (requires API key)."""
    return _env_bool("ABUSEIPDB_ENABLED", False) and bool(os.getenv("ABUSEIPDB_API_KEY", "").strip())


def abuseipdb_check_enabled() -> bool:
    """GET /check per IP (quota). Default off: use daily blacklist sync + Redis only."""
    return abuseipdb_master_enabled() and _env_bool("ABUSEIPDB_CHECK_ENABLED", False)


def abuseipdb_blacklist_lookup_enabled() -> bool:
    return abuseipdb_master_enabled() and _env_bool("ABUSEIPDB_BLACKLIST_LOOKUP_ENABLED", True)


def abuseipdb_report_enabled() -> bool:
    return abuseipdb_master_enabled() and _env_bool("ABUSEIPDB_REPORT_ENABLED", True)


def abuseipdb_blacklist_sync_enabled() -> bool:
    return abuseipdb_master_enabled() and _env_bool("ABUSEIPDB_BLACKLIST_SYNC_ENABLED", True)


def get_check_min_score() -> int:
    return max(0, min(100, _env_int("ABUSEIPDB_CHECK_MIN_SCORE", 80)))


def get_check_cache_ttl_seconds() -> int:
    return max(60, _env_int("ABUSEIPDB_CHECK_CACHE_TTL_SECONDS", 86400))


def get_blacklist_confidence_minimum() -> int:
    return max(25, min(100, _env_int("ABUSEIPDB_BLACKLIST_CONFIDENCE_MINIMUM", 75)))


def warm_sismember_cache_ttl_snapshot() -> None:
    """
    Read IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS once after Redis init.

    Matches env snapshot timing so TTL is not re-parsed from os.environ on every request.
    """
    global _SISMEMBER_CACHE_TTL_SNAPSHOT
    _SISMEMBER_CACHE_TTL_SNAPSHOT = max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0))


def invalidate_sismember_cache_ttl_snapshot() -> None:
    """Clear TTL snapshot (e.g. pytest); next get reads os.environ again."""
    global _SISMEMBER_CACHE_TTL_SNAPSHOT
    _SISMEMBER_CACHE_TTL_SNAPSHOT = None


def get_ip_reputation_sismember_cache_ttl_seconds() -> int:
    """In-process cache TTL for blacklist SISMEMBER; 0 disables caching."""
    if _SISMEMBER_CACHE_TTL_SNAPSHOT is not None:
        return _SISMEMBER_CACHE_TTL_SNAPSHOT
    return max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0))


def clear_ip_reputation_sismember_cache() -> None:
    """Invalidate SISMEMBER cache after blacklist mutations (sync, merge, startup)."""
    with _SISMEMBER_CACHE_LOCK:
        _SISMEMBER_CACHE.clear()


def _canonical_ip_for_blacklist_lookup(ip: str) -> str:
    """Normalize IP for Redis SISMEMBER and cache key (match stored set members)."""
    raw = (ip or "").split("%")[0].strip()
    if not raw or raw == "unknown":
        return raw
    try:
        parsed = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return str(parsed.ipv4_mapped)
    return str(parsed)


def _sismember_cache_get(ip: str) -> Optional[bool]:
    ttl = get_ip_reputation_sismember_cache_ttl_seconds()
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


def _sismember_cache_set(ip: str, value: bool) -> None:
    ttl = get_ip_reputation_sismember_cache_ttl_seconds()
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
    """
    Chunked SADD into key using a single pipelined execute (one round trip for all chunks).

    Returns the sum of each SADD's added count (same as sequential SADD).
    """
    if not batch:
        return 0
    pipe = redis_client.pipeline(transaction=False)
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i : i + chunk_size]
        pipe.sadd(key, *chunk)
    results = pipe.execute()
    return sum(int(x) for x in results)


def get_blacklist_limit() -> int:
    """
    Max IPs per blacklist request. AbuseIPDB caps by plan (10k / 100k / 500k).
    Default 10000 matches Free/Standard; set ABUSEIPDB_BLACKLIST_LIMIT higher on paid tiers.
    """
    return max(1, min(500_000, _env_int("ABUSEIPDB_BLACKLIST_LIMIT", 10_000)))


# At most one scheduled pull per day unless ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL=true.
_BLACKLIST_SYNC_MIN_INTERVAL_SECONDS = 86400


def get_blacklist_sync_interval_seconds() -> int:
    """
    Seconds between blacklist sync attempts (scheduler).

    Default 86400 (once per day). Without relax, clamped to at least 86400s.
    Set ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL=true for higher API tiers
    that allow more frequent blacklist calls (minimum 3600s then).
    """
    raw = _env_int("ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS", 86400)
    if _env_bool("ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL", False):
        return max(3600, raw)
    return max(_BLACKLIST_SYNC_MIN_INTERVAL_SECONDS, raw)


def parse_retry_after_seconds(response: httpx.Response) -> Optional[int]:
    """Parse Retry-After header (seconds) if present."""
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def log_rate_limit_429(response: httpx.Response, endpoint: str) -> None:
    """Log AbuseIPDB 429 with optional rate-limit headers."""
    retry_after = parse_retry_after_seconds(response)
    limit_hdr = response.headers.get("X-RateLimit-Limit")
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset_hdr = response.headers.get("X-RateLimit-Reset")
    logger.warning(
        "[AbuseIPDB] %s HTTP 429 (rate limited) retry_after=%s X-RateLimit-Limit=%s "
        "X-RateLimit-Remaining=%s X-RateLimit-Reset=%s",
        endpoint,
        retry_after,
        limit_hdr,
        remaining,
        reset_hdr,
    )


def get_report_dedupe_ttl_seconds() -> int:
    return max(3600, _env_int("ABUSEIPDB_REPORT_DEDUPE_TTL_SECONDS", 86400))


def get_api_key() -> str:
    return os.getenv("ABUSEIPDB_API_KEY", "").strip()


def abuseipdb_baseline_file_enabled() -> bool:
    """Merge shipped / downloaded baseline IPs from data/abuseipdb/blacklist_baseline.txt into Redis."""
    return _env_bool("ABUSEIPDB_BASELINE_ENABLED", True)


def _mindgraph_root() -> Path:
    """Repository root (directory containing data/, services/)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def baseline_blacklist_path() -> Path:
    """Path to baseline file (env ABUSEIPDB_BASELINE_FILE or default under data/abuseipdb/)."""
    override = os.getenv("ABUSEIPDB_BASELINE_FILE", "").strip()
    if override:
        path = Path(override)
        if path.is_absolute():
            return path
        return _mindgraph_root() / path
    return _mindgraph_root() / "data" / "abuseipdb" / "blacklist_baseline.txt"


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


def apply_blacklist_baseline_from_file() -> int:
    """
    SADD baseline IPs into Redis KEY_BLACKLIST (merge; idempotent).

    Call at startup and after remote blacklist sync so API replace does not drop baseline IPs.

    Returns:
        Number of lines parsed with at least one SADD round executed (best-effort).
    """
    if not abuseipdb_baseline_file_enabled():
        return 0
    if not abuseipdb_master_enabled():
        return 0
    if not is_redis_available():
        return 0

    path = baseline_blacklist_path()
    if not path.is_file():
        logger.debug("[AbuseIPDB] baseline file not found: %s", path)
        return 0

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("[AbuseIPDB] could not read baseline file %s: %s", path, exc)
        return 0

    ips = parse_baseline_file_lines(text)
    if not ips:
        logger.debug("[AbuseIPDB] baseline file has no valid IPs: %s", path)
        return 0

    r = get_redis()
    if not r:
        return 0

    batch = list(ips)
    chunk_size = 2000
    try:
        added_total = pipeline_sadd_chunks(r, KEY_BLACKLIST, batch, chunk_size)
    except (OSError, RedisError) as exc:
        logger.warning("[AbuseIPDB] baseline SADD failed: %s", exc)
        return 0

    logger.info(
        "[AbuseIPDB] merged %s baseline IPs from %s (new members this round: %s)",
        len(ips),
        path,
        added_total,
    )
    return len(ips)


def _client_headers() -> Dict[str, str]:
    return {
        "Key": get_api_key(),
        "Accept": "application/json",
    }


def client_ip_is_skipped_for_abuseipdb(ip: str) -> bool:
    """Skip loopback and private ranges (no external reputation)."""
    if not ip or ip == "unknown":
        return True
    try:
        parsed = ipaddress.ip_address(ip.split("%")[0].strip())
    except ValueError:
        return True
    return bool(parsed.is_loopback or parsed.is_private or parsed.is_link_local or parsed.is_reserved)


def is_ip_in_blacklist_set(ip: str) -> bool:
    """Sync: Redis SISMEMBER for shared blacklist (AbuseIPDB, CrowdSec, baseline)."""
    if not is_redis_available():
        return False
    from services.infrastructure.security import ip_reputation_env_snapshot

    if not ip_reputation_env_snapshot.blacklist_lookup_active():
        return False
    lookup_ip = _canonical_ip_for_blacklist_lookup(ip)
    cached = _sismember_cache_get(lookup_ip)
    if cached is not None:
        return cached
    client = get_redis()
    if not client:
        return False
    try:
        result = bool(client.sismember(KEY_BLACKLIST, lookup_ip))
    except (OSError, RedisError) as exc:
        logger.debug("[AbuseIPDB] blacklist lookup failed (fail open): %s", exc)
        return False
    _sismember_cache_set(lookup_ip, result)
    return result


def _get_cached_check_score(ip: str) -> Optional[int]:
    if not is_redis_available():
        return None
    r = get_redis()
    if not r:
        return None
    key = f"{KEY_CHECK_PREFIX}{ip}"
    try:
        raw = r.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        score = data.get("score")
        if isinstance(score, int):
            return score
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("[AbuseIPDB] check cache read failed: %s", exc)
    return None


def _set_cached_check_score(ip: str, score: int, ttl: int) -> None:
    if not is_redis_available():
        return
    r = get_redis()
    if not r:
        return
    key = f"{KEY_CHECK_PREFIX}{ip}"
    try:
        r.setex(key, ttl, json.dumps({"score": score}))
    except OSError as exc:
        logger.debug("[AbuseIPDB] check cache write failed: %s", exc)


async def fetch_check_score(ip: str) -> Optional[int]:
    """Return abuseConfidenceScore for IP, or None on error / missing."""
    params = {"ipAddress": ip, "maxAgeInDays": 90}
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get(
                f"{ABUSEIPDB_API_BASE}/check",
                headers=_client_headers(),
                params=params,
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[AbuseIPDB] check request failed for %s: %s", ip, exc)
        return None

    if response.status_code == 429:
        log_rate_limit_429(response, "GET /check")
        return None

    if response.status_code != 200:
        logger.warning(
            "[AbuseIPDB] check HTTP %s for %s: %s",
            response.status_code,
            ip,
            (response.text or "")[:200],
        )
        return None

    try:
        payload: Dict[str, Any] = response.json()
    except json.JSONDecodeError:
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    raw_score = data.get("abuseConfidenceScore")
    if isinstance(raw_score, int):
        return raw_score
    return None


async def check_ip_score_cached_with_provenance(
    ip: str,
) -> Tuple[Optional[int], str]:
    """
    Return cached or live AbuseIPDB abuseConfidenceScore.

    Second value: 'cache' | 'live' | 'unavailable' (API error, 429, or no score).
    """
    ttl = get_check_cache_ttl_seconds()
    cached = _get_cached_check_score(ip)
    if cached is not None:
        return cached, "cache"

    score = await fetch_check_score(ip)
    if score is not None:
        _set_cached_check_score(ip, score, ttl)
        return score, "live"
    return None, "unavailable"


async def check_ip_score_cached(ip: str) -> Optional[int]:
    """Return cached or live check score; None if unavailable."""
    score, _ = await check_ip_score_cached_with_provenance(ip)
    return score


def log_shared_blacklist_redis_size(context: str) -> None:
    """Log SCARD for the shared blacklist set (AbuseIPDB + CrowdSec + baselines)."""
    if not is_redis_available():
        return
    client = get_redis()
    if not client:
        return
    try:
        size = client.scard(KEY_BLACKLIST)
    except (OSError, RedisError) as exc:
        logger.debug("[IP reputation] blacklist size unreadable (%s): %s", context, exc)
        return
    logger.info(
        "[IP reputation] Shared Redis blacklist size=%s (%s)",
        size,
        context,
    )


async def report_ip_abuse(ip: str, categories: str, comment: str) -> bool:
    """POST /report. Returns True on success."""
    form = {
        "ip": ip,
        "categories": categories,
        "comment": comment[:1024],
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            response = await http_client.post(
                f"{ABUSEIPDB_API_BASE}/report",
                headers=_client_headers(),
                data=form,
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[AbuseIPDB] report failed for %s: %s", ip, exc)
        return False

    if response.status_code == 429:
        log_rate_limit_429(response, "POST /report")
        return False

    if response.status_code != 200:
        logger.warning(
            "[AbuseIPDB] report HTTP %s for %s: %s",
            response.status_code,
            ip,
            (response.text or "")[:300],
        )
        return False

    return True


def report_ip_abuse_sync(ip: str, categories: str, comment: str, api_key: str) -> bool:
    """Synchronous report for Fail2ban CLI (no app .env required on ban path)."""
    form = {
        "ip": ip,
        "categories": categories,
        "comment": comment[:1024],
    }
    headers = {"Key": api_key.strip(), "Accept": "application/json"}
    try:
        with httpx.Client(timeout=25.0) as http_client:
            response = http_client.post(
                f"{ABUSEIPDB_API_BASE}/report",
                headers=headers,
                data=form,
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[AbuseIPDB] sync report failed for %s: %s", ip, exc)
        return False

    if response.status_code == 429:
        log_rate_limit_429(response, "POST /report")
        return False

    if response.status_code != 200:
        logger.warning(
            "[AbuseIPDB] sync report HTTP %s for %s",
            response.status_code,
            ip,
        )
        return False
    return True


def try_acquire_report_dedupe(ip: str) -> bool:
    """Return True if this IP may report now (dedupe key set with NX)."""
    if not is_redis_available():
        return True
    r = get_redis()
    if not r:
        return True
    key = f"{KEY_REPORT_DEDUPE_PREFIX}{ip}"
    ttl = get_report_dedupe_ttl_seconds()
    try:
        acquired = r.set(key, "1", nx=True, ex=ttl)
        return bool(acquired)
    except OSError as exc:
        logger.debug("[AbuseIPDB] report dedupe failed (allow report): %s", exc)
        return True


async def report_lockout_background(ip: str) -> None:
    """Fire-and-forget body: report brute-force after account lockout."""
    if not abuseipdb_report_enabled():
        return
    if client_ip_is_skipped_for_abuseipdb(ip):
        return
    if not try_acquire_report_dedupe(ip):
        return

    comment = "MindGraph: account lockout after repeated failed login attempts"
    ok = await report_ip_abuse(
        ip,
        str(CATEGORY_BRUTE_FORCE),
        comment,
    )
    if ok:
        logger.info("[AbuseIPDB] reported lockout for IP %s", ip)
    else:
        logger.debug("[AbuseIPDB] lockout report not accepted for IP %s", ip)


def schedule_abuseipdb_report_on_lockout(client_ip: Optional[str]) -> None:
    """Schedule background report when account becomes locked (non-blocking)."""
    if not client_ip or not abuseipdb_report_enabled():
        return
    if client_ip_is_skipped_for_abuseipdb(client_ip):
        return

    async def _run() -> None:
        await report_lockout_background(client_ip)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        logger.debug("[AbuseIPDB] no running loop; skip lockout report scheduling")


def _store_blacklist_ips(ips: Set[str]) -> bool:
    """Replace Redis SET contents with ips."""
    if not is_redis_available():
        return False
    r = get_redis()
    if not r:
        return False
    batch: List[str] = list(ips)
    if not batch:
        try:
            r.delete(KEY_BLACKLIST)
        except OSError as exc:
            logger.error("[AbuseIPDB] failed to clear blacklist key: %s", exc)
            return False
        return True

    tmp_key = f"{KEY_BLACKLIST}:tmp:{uuid.uuid4().hex}"
    try:
        chunk_size = 2000
        pipe = r.pipeline(transaction=False)
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i : i + chunk_size]
            pipe.sadd(tmp_key, *chunk)
        pipe.execute()
        r.rename(tmp_key, KEY_BLACKLIST)
    except (OSError, RedisError) as exc:
        try:
            r.delete(tmp_key)
        except OSError:
            pass
        logger.error("[AbuseIPDB] failed to store blacklist in Redis: %s", exc)
        return False
    return True


async def sync_blacklist_to_redis() -> Dict[str, Any]:
    """GET /blacklist and replace Redis SET KEY_BLACKLIST."""
    result: Dict[str, Any] = {
        "ok": False,
        "count": 0,
        "error": None,
        "rate_limited": False,
        "retry_after_seconds": None,
    }

    if not abuseipdb_blacklist_sync_enabled():
        result["error"] = "disabled"
        return result

    params = {
        "confidenceMinimum": get_blacklist_confidence_minimum(),
        "limit": get_blacklist_limit(),
    }

    blacklist_headers = {
        "Key": get_api_key(),
        "Accept": "text/plain",
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as http_client:
            response = await http_client.get(
                f"{ABUSEIPDB_API_BASE}/blacklist",
                headers=blacklist_headers,
                params=params,
            )
    except (httpx.HTTPError, OSError) as exc:
        result["error"] = str(exc)
        logger.warning("[AbuseIPDB] blacklist download failed: %s", exc)
        return result

    if response.status_code == 429:
        log_rate_limit_429(response, "GET /blacklist")
        retry_after = parse_retry_after_seconds(response) or 3600
        result["error"] = "rate_limited"
        result["rate_limited"] = True
        result["retry_after_seconds"] = retry_after
        return result

    if response.status_code != 200:
        err = (response.text or "")[:500]
        result["error"] = f"HTTP {response.status_code}: {err}"
        logger.warning(
            "[AbuseIPDB] blacklist HTTP %s (subscription may be required): %s",
            response.status_code,
            err[:200],
        )
        return result

    body = response.text or ""
    ips = parse_abuseipdb_blacklist_plaintext(body)
    if not ips and body.strip().startswith("{"):
        try:
            payload_err: Dict[str, Any] = response.json()
        except json.JSONDecodeError:
            payload_err = {}
        err_detail = str(payload_err)[:300]
        result["error"] = f"unexpected body: {err_detail}"
        return result

    if not _store_blacklist_ips(ips):
        result["error"] = "redis_store_failed"
        return result

    meta = json.dumps(
        {
            "count": len(ips),
            "confidenceMinimum": get_blacklist_confidence_minimum(),
            "limit": get_blacklist_limit(),
        }
    )
    r = get_redis()
    if r:
        try:
            r.set(KEY_BLACKLIST_META, meta)
        except OSError as exc:
            logger.debug("[AbuseIPDB] could not write blacklist meta: %s", exc)

    result["ok"] = True
    result["count"] = len(ips)
    logger.info("[AbuseIPDB] blacklist sync stored %s IPs in Redis", len(ips))

    baseline_merged = apply_blacklist_baseline_from_file()
    if baseline_merged:
        result["baseline_merged"] = baseline_merged

    from services.infrastructure.security import crowdsec_blocklist_service

    crowdsec_out = await crowdsec_blocklist_service.merge_crowdsec_blocklist_from_network()
    if crowdsec_out.get("ok"):
        result["crowdsec"] = {
            "count": crowdsec_out.get("count"),
            "skipped": crowdsec_out.get("skipped", False),
        }

    crowdsec_baseline = crowdsec_blocklist_service.apply_crowdsec_baseline_from_file()
    if crowdsec_baseline:
        result["crowdsec_baseline_merged"] = crowdsec_baseline

    if result.get("ok"):
        clear_ip_reputation_sismember_cache()
        log_shared_blacklist_redis_size("after AbuseIPDB sync and CrowdSec merge")

    return result
