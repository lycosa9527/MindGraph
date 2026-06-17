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
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from redis.exceptions import RedisError

from services.infrastructure.security import ip_reputation_env_flags, ip_reputation_env_snapshot
from services.infrastructure.security import ip_reputation_blacklist_redis as _bl_redis
from services.infrastructure.security.abuseipdb_blacklist_parse import (
    parse_abuseipdb_blacklist_plaintext,
)
from services.infrastructure.security.blocklist_crowdsec_merge_hook import (
    merge_crowdsec_after_abuseipdb_sync,
)
from services.infrastructure.security.ip_reputation_blacklist_redis import (
    KEY_BLACKLIST,
    parse_baseline_file_lines,
    parse_retry_after_seconds,
    pipeline_sadd_chunks_async,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

clear_ip_reputation_sismember_cache = _bl_redis.clear_ip_reputation_sismember_cache

logger = logging.getLogger(__name__)

_DEFAULT_ABUSEIPDB_API_BASE = "https://api.abuseipdb.com/api/v2"

KEY_BLACKLIST_META = "abuseipdb:blacklist:meta"
KEY_CHECK_PREFIX = "abuseipdb:check:"
KEY_REPORT_DEDUPE_PREFIX = "abuseipdb:report:dedupe:"

CATEGORY_BRUTE_FORCE = 18


def get_abuseipdb_api_base() -> str:
    """
    Base URL for AbuseIPDB API v2 (check, report, blacklist).

    Set ABUSEIPDB_API_BASE in .env if you use a proxy or non-default host; default is
    the official api.abuseipdb.com endpoint. Authentication is always via ABUSEIPDB_API_KEY.
    """
    raw = os.getenv("ABUSEIPDB_API_BASE", "").strip()
    if not raw:
        return _DEFAULT_ABUSEIPDB_API_BASE
    return raw.rstrip("/")


_env_bool = ip_reputation_env_flags.env_bool
_env_int = ip_reputation_env_flags.env_int
abuseipdb_master_enabled = ip_reputation_env_flags.abuseipdb_master_enabled
abuseipdb_check_enabled = ip_reputation_env_flags.abuseipdb_check_enabled
abuseipdb_blacklist_lookup_enabled = ip_reputation_env_flags.abuseipdb_blacklist_lookup_enabled
abuseipdb_report_enabled = ip_reputation_env_flags.abuseipdb_report_enabled
abuseipdb_blacklist_sync_enabled = ip_reputation_env_flags.abuseipdb_blacklist_sync_enabled
get_check_min_score = ip_reputation_env_flags.get_check_min_score


def get_check_cache_ttl_seconds() -> int:
    """Get check cache ttl seconds."""
    return max(60, _env_int("ABUSEIPDB_CHECK_CACHE_TTL_SECONDS", 86400))


def get_blacklist_confidence_minimum() -> int:
    """Get blacklist confidence minimum."""
    return max(25, min(100, _env_int("ABUSEIPDB_BLACKLIST_CONFIDENCE_MINIMUM", 75)))


def warm_sismember_cache_ttl_snapshot() -> None:
    """
    Read IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS once after Redis init.

    Matches env snapshot timing so TTL is not re-parsed from os.environ on every request.
    """
    _bl_redis.warm_sismember_cache_ttl_snapshot(max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0)))


def invalidate_sismember_cache_ttl_snapshot() -> None:
    """Clear TTL snapshot (e.g. pytest); next get reads os.environ again."""
    _bl_redis.invalidate_sismember_cache_ttl_snapshot()


def get_ip_reputation_sismember_cache_ttl_seconds() -> int:
    """In-process cache TTL for blacklist SISMEMBER; 0 disables caching."""
    return _bl_redis.get_ip_reputation_sismember_cache_ttl_seconds(
        max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0))
    )


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
    """Sismember cache get."""
    return _bl_redis.sismember_cache_get(ip, max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0)))


def _sismember_cache_set(ip: str, value: bool) -> None:
    """Sismember cache set."""
    _bl_redis.sismember_cache_set(ip, value, max(0, _env_int("IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS", 0)))


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
    Minimum seconds between AbuseIPDB GET /blacklist pulls (API usage / tier hints).

    The in-process scheduler runs on BACKUP_HOUR (see abuseipdb_scheduler), not on this
    interval. Default 86400 (once per day). Without relax, clamped to at least 86400s.
    Set ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL=true for higher API tiers
    that allow more frequent blacklist calls (minimum 3600s then).
    """
    raw = _env_int("ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS", 86400)
    if _env_bool("ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL", False):
        return max(3600, raw)
    return max(_BLACKLIST_SYNC_MIN_INTERVAL_SECONDS, raw)


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
    """Get report dedupe ttl seconds."""
    return max(3600, _env_int("ABUSEIPDB_REPORT_DEDUPE_TTL_SECONDS", 86400))


def get_api_key() -> str:
    """Get api key."""
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


async def apply_blacklist_baseline_from_file_async() -> int:
    """SADD baseline IPs into Redis KEY_BLACKLIST (merge; idempotent).

    Call at startup and after remote blacklist sync so an API replace does not
    drop baseline IPs.  Filesystem read is offloaded with ``asyncio.to_thread``
    because it remains blocking I/O.  All Redis work uses the shared async
    client.

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
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    except OSError as exc:
        logger.warning("[AbuseIPDB] could not read baseline file %s: %s", path, exc)
        return 0

    ips = parse_baseline_file_lines(text)
    if not ips:
        logger.debug("[AbuseIPDB] baseline file has no valid IPs: %s", path)
        return 0

    redis = get_async_redis()
    if not redis:
        return 0

    batch = list(ips)
    chunk_size = 2000
    try:
        added_total = await pipeline_sadd_chunks_async(redis, KEY_BLACKLIST, batch, chunk_size)
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
    """Client headers."""
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


async def is_ip_in_blacklist_set_async(ip: str) -> bool:
    """Async: Redis SISMEMBER for shared blacklist (AbuseIPDB, CrowdSec, baseline).

    Hot path — called from FastAPI middleware on every request that passes the
    IP-reputation gate.  Uses the shared async client so the event loop never
    blocks on a synchronous Redis round-trip.
    """
    if not is_redis_available():
        return False

    if not ip_reputation_env_snapshot.blacklist_lookup_active():
        return False
    lookup_ip = _canonical_ip_for_blacklist_lookup(ip)
    cached = _sismember_cache_get(lookup_ip)
    if cached is not None:
        return cached
    redis = get_async_redis()
    if not redis:
        return False
    try:
        result = bool(await redis.sismember(KEY_BLACKLIST, lookup_ip))
    except (OSError, RedisError) as exc:
        logger.debug("[AbuseIPDB] blacklist lookup failed (fail open): %s", exc)
        return False
    _sismember_cache_set(lookup_ip, result)
    return result


async def _get_cached_check_score_async(ip: str) -> Optional[int]:
    """Get cached check score async."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    key = f"{KEY_CHECK_PREFIX}{ip}"
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        score = data.get("score")
        if isinstance(score, int):
            return score
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("[AbuseIPDB] check cache read failed: %s", exc)
    return None


async def _set_cached_check_score_async(ip: str, score: int, ttl: int) -> None:
    """Set cached check score async."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    key = f"{KEY_CHECK_PREFIX}{ip}"
    try:
        await redis.setex(key, ttl, json.dumps({"score": score}))
    except OSError as exc:
        logger.debug("[AbuseIPDB] check cache write failed: %s", exc)


async def fetch_check_score(ip: str) -> Optional[int]:
    """Return abuseConfidenceScore for IP, or None on error / missing."""
    params = {"ipAddress": ip, "maxAgeInDays": 90}
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get(
                f"{get_abuseipdb_api_base()}/check",
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
    cached = await _get_cached_check_score_async(ip)
    if cached is not None:
        return cached, "cache"

    score = await fetch_check_score(ip)
    if score is not None:
        await _set_cached_check_score_async(ip, score, ttl)
        return score, "live"
    return None, "unavailable"


async def check_ip_score_cached(ip: str) -> Optional[int]:
    """Return cached or live check score; None if unavailable."""
    score, _ = await check_ip_score_cached_with_provenance(ip)
    return score


async def log_shared_blacklist_redis_size_async(context: str) -> None:
    """Async: SCARD for the shared blacklist set (AbuseIPDB + CrowdSec + baselines)."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        size = await redis.scard(KEY_BLACKLIST)
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
                f"{get_abuseipdb_api_base()}/report",
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
                f"{get_abuseipdb_api_base()}/report",
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


async def try_acquire_report_dedupe_async(ip: str) -> bool:
    """Return True if this IP may report now (dedupe key set with NX)."""
    if not is_redis_available():
        return True
    redis = get_async_redis()
    if not redis:
        return True
    key = f"{KEY_REPORT_DEDUPE_PREFIX}{ip}"
    ttl = get_report_dedupe_ttl_seconds()
    try:
        acquired = await redis.set(key, "1", nx=True, ex=ttl)
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
    if not await try_acquire_report_dedupe_async(ip):
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


async def _store_blacklist_ips_async(ips: Set[str]) -> bool:
    """Async: replace Redis SET contents with ips (atomic via tmp key + RENAME)."""
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    batch: List[str] = list(ips)
    if not batch:
        try:
            await redis.delete(KEY_BLACKLIST)
        except OSError as exc:
            logger.error("[AbuseIPDB] failed to clear blacklist key: %s", exc)
            return False
        return True

    tmp_key = f"{KEY_BLACKLIST}:tmp:{uuid.uuid4().hex}"
    try:
        chunk_size = 2000
        async with redis.pipeline(transaction=False) as pipe:
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                pipe.sadd(tmp_key, *chunk)
            await pipe.execute()
        await redis.rename(tmp_key, KEY_BLACKLIST)
    except (OSError, RedisError) as exc:
        try:
            await redis.delete(tmp_key)
        except OSError:
            pass
        logger.error("[AbuseIPDB] failed to store blacklist in Redis: %s", exc)
        return False
    return True


async def sync_blacklist_to_redis(force_crowdsec_merge: bool = False) -> Dict[str, Any]:
    """GET /blacklist and replace Redis SET KEY_BLACKLIST.

    When force_crowdsec_merge is True, CrowdSec network merge ignores the min-interval skip
    (used for the daily scheduled run aligned with BACKUP_HOUR).
    """
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
                f"{get_abuseipdb_api_base()}/blacklist",
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
        logger.warning(
            "[Blocklist] AbuseIPDB blacklist response was not a plain-text IP list: %s",
            err_detail[:200],
        )
        return result

    if not await _store_blacklist_ips_async(ips):
        result["error"] = "redis_store_failed"
        logger.warning(
            "[Blocklist] AbuseIPDB blacklist download OK but Redis store failed (see earlier [AbuseIPDB] error)",
        )
        return result

    meta = json.dumps(
        {
            "count": len(ips),
            "confidenceMinimum": get_blacklist_confidence_minimum(),
            "limit": get_blacklist_limit(),
        }
    )
    async_r = get_async_redis()
    if async_r:
        try:
            await async_r.set(KEY_BLACKLIST_META, meta)
        except OSError as exc:
            logger.debug("[AbuseIPDB] could not write blacklist meta: %s", exc)

    result["ok"] = True
    result["count"] = len(ips)
    logger.info("[AbuseIPDB] blacklist sync stored %s IPs in Redis", len(ips))

    baseline_merged = await apply_blacklist_baseline_from_file_async()
    if baseline_merged:
        result["baseline_merged"] = baseline_merged

    crowdsec_out = await merge_crowdsec_after_abuseipdb_sync(force=force_crowdsec_merge)
    if crowdsec_out.get("ok"):
        result["crowdsec"] = {
            "count": crowdsec_out.get("count"),
            "skipped": crowdsec_out.get("skipped", False),
        }
    else:
        cs_err = crowdsec_out.get("error")
        if cs_err and cs_err != "disabled":
            result["crowdsec_failed"] = cs_err
            logger.warning(
                "[Blocklist] CrowdSec network merge failed after AbuseIPDB IPs were stored: %s",
                cs_err,
            )

    if result.get("ok"):
        clear_ip_reputation_sismember_cache()
        await log_shared_blacklist_redis_size_async("after AbuseIPDB sync and CrowdSec merge")

    return result
