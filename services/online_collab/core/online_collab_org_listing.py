"""
Redis-first org-session listing for the online-collab manager.

Separated from online_collab_manager.py to keep that file under 600 LOC.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, cast

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.online_collab_redis_keys import (
    participants_key,
    registry_global_org_key,
    registry_org_key,
    session_meta_key,
)

logger = logging.getLogger(__name__)


def _s(val: Any) -> str:
    """Decode bytes / memoryview to str; return '' for None."""
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


async def list_org_sessions_redis(
    org_id: int,
    db_fallback_fn: Optional[Callable[[], Coroutine[Any, Any, List[Dict[str, Any]]]]] = None,
) -> List[Dict[str, Any]]:
    """
    Return live sessions for org_id (Redis-first, single-pipeline).

    Algorithm:
      1. Pipeline SMEMBERS registry:org:{org_id} + SMEMBERS registry:org:global
         to capture both org-scoped sessions AND sessions hosted by org-less admins.
      2. If both registries are empty or Redis is unavailable, call db_fallback_fn()
      3. Pipeline HGETALL + HLEN for all codes in one round-trip
      4. Filter out expired or zero-participant sessions
    """
    redis = get_async_redis()
    if not redis:
        logger.warning(
            "[OnlineCollabMgr] list_org_sessions: redis_unavailable_fallback org_id=%s",
            org_id,
        )
        if db_fallback_fn:
            return await db_fallback_fn()
        return []

    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.smembers(registry_org_key(org_id))
            pipe.smembers(registry_global_org_key())
            org_raw, global_raw = await pipe.execute()
    except (RedisError, OSError, TypeError, RuntimeError) as exc:
        logger.warning(
            "[OnlineCollabMgr] list_org_sessions: SMEMBERS error org_id=%s: %s",
            org_id,
            exc,
        )
        if db_fallback_fn:
            return await db_fallback_fn()
        return []

    def _decode_set(raw: Any) -> set:
        if not raw:
            return set()
        return {c.decode("utf-8") if isinstance(c, bytes) else c for c in raw}

    codes_set = _decode_set(org_raw) | _decode_set(global_raw)

    if not codes_set:
        logger.debug(
            "[OnlineCollabMgr] list_org_sessions: both org and global registries "
            "empty for org_id=%s, falling back to DB.",
            org_id,
        )
        if db_fallback_fn:
            return await db_fallback_fn()
        return []

    codes = list(codes_set)

    try:
        async with redis.pipeline(transaction=False) as pipe:
            for code in codes:
                pipe.hgetall(session_meta_key(code))
                pipe.hlen(participants_key(code))
            pipeline_results = await pipe.execute()
    except (RedisError, OSError, TypeError, RuntimeError) as exc:
        logger.warning(
            "[OnlineCollabMgr] list_org_sessions: pipeline error org_id=%s: %s",
            org_id,
            exc,
        )
        if db_fallback_fn:
            return await db_fallback_fn()
        return []

    out: List[Dict[str, Any]] = []
    now = int(time.time())
    logger.debug(
        "[OnlineCollabMgr] list_org_sessions: org_id=%s checking %d code(s) "
        "(org=%d global=%d): %s",
        org_id, len(codes),
        len(_decode_set(org_raw)), len(_decode_set(global_raw)),
        codes,
    )
    for idx, code in enumerate(codes):
        meta_raw = pipeline_results[idx * 2]
        count = pipeline_results[idx * 2 + 1]
        if not isinstance(meta_raw, dict) or not meta_raw:
            logger.debug(
                "[OnlineCollabMgr] list_org_sessions: skipping code=%s — "
                "session_meta empty or expired",
                code,
            )
            continue
        if not isinstance(count, int) or count == 0:
            logger.debug(
                "[OnlineCollabMgr] list_org_sessions: skipping code=%s — "
                "participant count=%s (zero or unavailable)",
                code, count,
            )
            continue
        meta = {_s(k): _s(v) for k, v in meta_raw.items()}
        expires_at_str = meta.get("expires_at", "")
        expires_at_iso: Optional[str] = None
        rem: Optional[int] = None
        if expires_at_str:
            try:
                expires_unix = int(expires_at_str)
                if expires_unix <= now:
                    logger.debug(
                        "[OnlineCollabMgr] list_org_sessions: skipping code=%s — "
                        "session expired (expires_unix=%s now=%s delta=%s)",
                        code, expires_unix, now, expires_unix - now,
                    )
                    continue
                rem = expires_unix - now
                expires_at_iso = (
                    datetime.fromtimestamp(expires_unix, UTC).isoformat() + "Z"
                )
            except (TypeError, ValueError):
                pass
        owner_name_val = meta.get("owner_name") or None
        out.append({
            "diagram_id": meta.get("diagram_id", ""),
            "title": meta.get("title", ""),
            "owner_name": owner_name_val,
            "participant_count": count,
            "expires_at": expires_at_iso,
            "remaining_seconds": rem,
        })
    return out
