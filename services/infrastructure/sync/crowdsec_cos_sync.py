"""
CrowdSec blocklist COS mirror (publisher upload / consumer pull).

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

from services.infrastructure.security.crowdsec_blocklist_service import (
    KEY_CROWDSEC_META,
    merge_crowdsec_blocklist_from_network,
    take_last_crowdsec_network_merge_payload,
    _sadd_ips_chunked_async,
    crowdsec_baseline_blacklist_path,
)
from services.infrastructure.security.ip_reputation_blacklist_redis import (
    KEY_BLACKLIST,
    clear_ip_reputation_sismember_cache,
    parse_baseline_file_lines,
)
from services.infrastructure.sync.cos_sync_env import (
    crowdsec_blocklist_cos_key,
    crowdsec_meta_cos_key,
    is_cos_consumer,
    is_cos_publisher,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)


async def _get_local_merge_meta_async() -> Optional[Dict[str, Any]]:
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
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.debug("[CrowdSecCOS] could not read local meta: %s", exc)
    return None


async def _set_local_merge_meta_async(count: int) -> None:
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    payload = json.dumps({"last_merge_unix": time.time(), "count": count})
    try:
        await redis.set(KEY_CROWDSEC_META, payload)
    except OSError as exc:
        logger.debug("[CrowdSecCOS] could not write local meta: %s", exc)


async def publish_crowdsec_blocklist_to_cos(plaintext: str, ip_count: int) -> bool:
    """Upload blocklist plaintext and meta to COS (publisher only)."""
    if not is_cos_publisher():
        return False
    if not tencent_cos_client.cos_credentials_configured():
        logger.warning("[CrowdSecCOS] COS not configured; skip publish")
        return False

    body_bytes = plaintext.encode("utf-8")
    meta = {
        "last_merge_unix": time.time(),
        "count": ip_count,
        "sha256": tencent_cos_client.sha256_hex(body_bytes),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    block_key = crowdsec_blocklist_cos_key()
    meta_key = crowdsec_meta_cos_key()
    ok_body = tencent_cos_client.upload_bytes(body_bytes, block_key, log_prefix="[CrowdSecCOS]")
    ok_meta = tencent_cos_client.put_json(meta_key, meta)
    if ok_body and ok_meta:
        logger.info("[CrowdSecCOS] Published %s IPs to COS", ip_count)
        return True
    logger.warning("[CrowdSecCOS] COS publish failed body=%s meta=%s", ok_body, ok_meta)
    return False


def read_crowdsec_cos_meta() -> Optional[Dict[str, Any]]:
    """Read CrowdSec meta JSON from COS."""
    return tencent_cos_client.get_json(crowdsec_meta_cos_key())


async def merge_crowdsec_blocklist_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download blocklist from COS and merge into Redis (consumer path)."""
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

    cos_meta = await asyncio.to_thread(read_crowdsec_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    cos_ts = cos_meta.get("last_merge_unix")
    if not force and isinstance(cos_ts, (int, float)):
        local_meta = await _get_local_merge_meta_async()
        local_ts = local_meta.get("last_merge_unix") if local_meta else None
        if isinstance(local_ts, (int, float)) and float(local_ts) >= float(cos_ts):
            result["skipped"] = True
            result["ok"] = True
            return result

    block_key = crowdsec_blocklist_cos_key()

    def _fetch_body() -> Optional[bytes]:
        return tencent_cos_client.get_object_bytes(block_key, log_prefix="[CrowdSecCOS]")

    raw = await asyncio.to_thread(_fetch_body)
    if raw is None:
        result["error"] = "cos_blocklist_missing"
        return result

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["error"] = "invalid_encoding"
        return result

    ips = parse_baseline_file_lines(text)
    if not ips:
        result["error"] = "empty_or_invalid"
        return result

    try:
        added = await _sadd_ips_chunked_async(ips)
    except (OSError, RedisError) as exc:
        result["error"] = str(exc)
        return result

    count = len(ips)
    if isinstance(cos_ts, (int, float)):
        if is_redis_available():
            redis = get_async_redis()
            if redis:
                payload = json.dumps({"last_merge_unix": float(cos_ts), "count": count})
                try:
                    await redis.set(KEY_CROWDSEC_META, payload)
                except OSError as exc:
                    logger.debug("[CrowdSecCOS] meta write failed: %s", exc)
    else:
        await _set_local_merge_meta_async(count)

    baseline_path = crowdsec_baseline_blacklist_path()
    try:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(baseline_path.write_text, text, encoding="utf-8")
    except OSError as exc:
        logger.debug("[CrowdSecCOS] baseline file write skipped: %s", exc)

    clear_ip_reputation_sismember_cache()
    result["ok"] = True
    result["count"] = count
    logger.info(
        "[CrowdSecCOS] merged %s IPs from COS (new members: %s)",
        count,
        added,
    )
    return result


async def merge_crowdsec_blocklist_for_role(*, force: bool = False) -> Dict[str, Any]:
    """Route CrowdSec merge to network (publisher/off) or COS (consumer)."""
    if is_cos_consumer():
        return await merge_crowdsec_blocklist_from_cos(force=force)
    result = await merge_crowdsec_blocklist_from_network(force=force)
    if is_cos_publisher() and result.get("ok") and not result.get("skipped"):
        payload = take_last_crowdsec_network_merge_payload()
        if payload is not None:
            body, count = payload
            published = await publish_crowdsec_blocklist_to_cos(body, count)
            result["cos_published"] = published
    return result


async def get_blacklist_ip_count_async() -> Optional[int]:
    """Return SCARD of shared blacklist set."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        count = await redis.scard(KEY_BLACKLIST)
        return int(count)
    except (OSError, RedisError):
        return None


def compare_crowdsec_sync_state(
    local_meta: Optional[Dict[str, Any]],
    cos_meta: Optional[Dict[str, Any]],
) -> str:
    """Return sync status label for admin UI."""
    if cos_meta is None:
        return "missing_on_cos"
    if local_meta is None:
        return "consumer_behind"
    local_ts = local_meta.get("last_merge_unix")
    cos_ts = cos_meta.get("last_merge_unix")
    if not isinstance(local_ts, (int, float)) or not isinstance(cos_ts, (int, float)):
        return "unknown"
    if float(local_ts) >= float(cos_ts):
        return "in_sync"
    return "consumer_behind"


async def get_crowdsec_cos_status() -> Dict[str, Any]:
    """Status snapshot for admin API."""
    local_meta = await _get_local_merge_meta_async()
    cos_meta = await asyncio.to_thread(read_crowdsec_cos_meta)
    blacklist_count = await get_blacklist_ip_count_async()
    cos_ts = cos_meta.get("last_merge_unix") if cos_meta else None
    return {
        "local_meta": local_meta,
        "cos_meta": cos_meta,
        "blacklist_ip_count": blacklist_count,
        "sync_state": compare_crowdsec_sync_state(local_meta, cos_meta),
        "cos_last_merge_iso": (
            datetime.fromtimestamp(float(cos_ts), tz=timezone.utc).isoformat()
            if isinstance(cos_ts, (int, float))
            else None
        ),
    }
