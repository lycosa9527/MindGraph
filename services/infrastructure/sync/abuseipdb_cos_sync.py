"""
AbuseIPDB blocklist COS mirror (publisher upload / consumer pull).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.infrastructure.security.abuseipdb_blacklist_parse import (
    parse_abuseipdb_blacklist_plaintext,
)
from services.infrastructure.security.abuseipdb_service import (
    KEY_BLACKLIST_META,
    apply_blacklist_baseline_from_file_async,
    get_blacklist_confidence_minimum,
    get_blacklist_limit,
    log_shared_blacklist_redis_size_async,
    replace_shared_blacklist_ips_async,
    sync_blacklist_to_redis,
    take_last_abuseipdb_network_sync_payload,
)
from services.infrastructure.security.blocklist_crowdsec_merge_hook import (
    merge_crowdsec_after_abuseipdb_sync,
)
from services.infrastructure.security.ip_reputation_blacklist_redis import (
    clear_ip_reputation_sismember_cache,
)
from services.infrastructure.sync.cos_sync_env import (
    abuseipdb_blocklist_cos_key,
    abuseipdb_meta_cos_key,
    is_cos_consumer,
    is_cos_publisher,
)
from services.infrastructure.sync.crowdsec_cos_sync import compare_crowdsec_sync_state
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)


async def _get_local_abuseipdb_meta_async() -> Optional[Dict[str, Any]]:
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(KEY_BLACKLIST_META)
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.debug("[AbuseIPDBCOS] could not read local meta: %s", exc)
    return None


async def _set_local_abuseipdb_meta_async(
    count: int,
    *,
    last_merge_unix: Optional[float] = None,
    source: str = "cos",
) -> None:
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    payload = {
        "count": count,
        "confidenceMinimum": get_blacklist_confidence_minimum(),
        "limit": get_blacklist_limit(),
        "last_merge_unix": last_merge_unix if last_merge_unix is not None else time.time(),
        "source": source,
    }
    try:
        await redis.set(KEY_BLACKLIST_META, json.dumps(payload))
    except OSError as exc:
        logger.debug("[AbuseIPDBCOS] could not write local meta: %s", exc)


async def publish_abuseipdb_blocklist_to_cos(plaintext: str, ip_count: int) -> bool:
    """Upload AbuseIPDB blocklist plaintext and meta to COS (publisher only)."""
    if not is_cos_publisher():
        return False
    if not tencent_cos_client.cos_credentials_configured():
        logger.warning("[AbuseIPDBCOS] COS not configured; skip publish")
        return False

    body_bytes = plaintext.encode("utf-8")
    meta = {
        "last_merge_unix": time.time(),
        "count": ip_count,
        "sha256": tencent_cos_client.sha256_hex(body_bytes),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "confidenceMinimum": get_blacklist_confidence_minimum(),
        "limit": get_blacklist_limit(),
    }
    block_key = abuseipdb_blocklist_cos_key()
    meta_key = abuseipdb_meta_cos_key()
    ok_body = tencent_cos_client.upload_bytes(
        body_bytes,
        block_key,
        log_prefix="[AbuseIPDBCOS]",
    )
    ok_meta = tencent_cos_client.put_json(meta_key, meta)
    if ok_body and ok_meta:
        logger.info("[AbuseIPDBCOS] Published %s IPs to COS", ip_count)
        return True
    logger.warning("[AbuseIPDBCOS] COS publish failed body=%s meta=%s", ok_body, ok_meta)
    return False


def read_abuseipdb_cos_meta() -> Optional[Dict[str, Any]]:
    """Read AbuseIPDB meta JSON from COS."""
    return tencent_cos_client.get_json(abuseipdb_meta_cos_key())


async def merge_abuseipdb_blocklist_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download AbuseIPDB blocklist from COS and replace Redis SET (consumer path)."""
    result: Dict[str, Any] = {
        "ok": False,
        "count": 0,
        "skipped": False,
        "error": None,
        "source": "cos",
    }
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    cos_meta = await asyncio.to_thread(read_abuseipdb_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    cos_ts = cos_meta.get("last_merge_unix")
    if not force and isinstance(cos_ts, (int, float)):
        local_meta = await _get_local_abuseipdb_meta_async()
        local_ts = local_meta.get("last_merge_unix") if local_meta else None
        if isinstance(local_ts, (int, float)) and float(local_ts) >= float(cos_ts):
            result["skipped"] = True
            result["ok"] = True
            return result

    block_key = abuseipdb_blocklist_cos_key()

    def _fetch_body() -> Optional[bytes]:
        return tencent_cos_client.get_object_bytes(block_key, log_prefix="[AbuseIPDBCOS]")

    raw = await asyncio.to_thread(_fetch_body)
    if raw is None:
        result["error"] = "cos_blocklist_missing"
        return result

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["error"] = "invalid_encoding"
        return result

    ips = parse_abuseipdb_blacklist_plaintext(text)
    if not ips:
        result["error"] = "empty_or_invalid"
        return result

    try:
        stored = await replace_shared_blacklist_ips_async(ips)
    except (OSError, RedisError) as exc:
        result["error"] = str(exc)
        return result
    if not stored:
        result["error"] = "redis_store_failed"
        return result

    count = len(ips)
    merge_ts = float(cos_ts) if isinstance(cos_ts, (int, float)) else time.time()
    await _set_local_abuseipdb_meta_async(count, last_merge_unix=merge_ts, source="cos")

    baseline_merged = await apply_blacklist_baseline_from_file_async()
    if baseline_merged:
        result["baseline_merged"] = baseline_merged

    clear_ip_reputation_sismember_cache()
    result["ok"] = True
    result["count"] = count
    logger.info("[AbuseIPDBCOS] replaced Redis blacklist with %s IPs from COS", count)
    return result


async def sync_blacklist_for_role(
    *,
    force: bool = False,
    force_crowdsec_merge: bool = False,
) -> Dict[str, Any]:
    """
    Route AbuseIPDB sync: COS pull (consumer) or API (publisher/off).

    Publisher also uploads the API body to COS after a successful network sync.
    CrowdSec merge runs after AbuseIPDB on both paths (role-aware CrowdSec).
    """
    if is_cos_consumer():
        result = await merge_abuseipdb_blocklist_from_cos(force=force)
        if result.get("ok") and not result.get("skipped"):
            crowdsec_out = await merge_crowdsec_after_abuseipdb_sync(
                force=force or force_crowdsec_merge,
            )
            if crowdsec_out.get("ok"):
                result["crowdsec"] = {
                    "count": crowdsec_out.get("count"),
                    "skipped": crowdsec_out.get("skipped", False),
                    "cos_published": crowdsec_out.get("cos_published"),
                }
            else:
                cs_err = crowdsec_out.get("error")
                if cs_err and cs_err != "disabled":
                    result["crowdsec_failed"] = cs_err
            await log_shared_blacklist_redis_size_async(
                "after AbuseIPDB COS sync and CrowdSec merge",
            )
        return result

    result = await sync_blacklist_to_redis(force_crowdsec_merge=force_crowdsec_merge or force)
    if is_cos_publisher():
        payload = take_last_abuseipdb_network_sync_payload()
        if payload is not None:
            body, count = payload
            published = await publish_abuseipdb_blocklist_to_cos(body, count)
            result["cos_published"] = published
            if published and result.get("error") == "redis_store_failed":
                result["ok"] = True
                result["count"] = count
                result["warning"] = "redis_store_failed_but_cos_published"
    return result


async def get_abuseipdb_cos_status() -> Dict[str, Any]:
    """Status snapshot for admin API."""
    local_meta = await _get_local_abuseipdb_meta_async()
    cos_meta = await asyncio.to_thread(read_abuseipdb_cos_meta)
    cos_ts = cos_meta.get("last_merge_unix") if cos_meta else None
    return {
        "local_meta": local_meta,
        "cos_meta": cos_meta,
        "sync_state": compare_crowdsec_sync_state(local_meta, cos_meta),
        "cos_last_merge_iso": (
            datetime.fromtimestamp(float(cos_ts), tz=timezone.utc).isoformat()
            if isinstance(cos_ts, (int, float))
            else None
        ),
    }
