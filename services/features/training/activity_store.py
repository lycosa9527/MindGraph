"""
Per-teacher activity hash for the instructor friends rail.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from services.features.training.constants import (
    ACTIVITY_KEY,
    ACTIVITY_SSE_KEY,
    ACTIVITY_SSE_MIN_SECONDS,
    ACTIVITY_SUMMARY_KEY,
    ACTIVITY_SUMMARY_TTL_SECONDS,
    ACTIVITY_TTL_SECONDS,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


def _key(org_id: int) -> str:
    return ACTIVITY_KEY.format(org_id=int(org_id))


def _summary_key(org_id: int) -> str:
    return ACTIVITY_SUMMARY_KEY.format(org_id=int(org_id))


def _sse_gate_key(org_id: int) -> str:
    return ACTIVITY_SSE_KEY.format(org_id=int(org_id))


def _decode_field(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def touch_activity(
    org_id: int,
    user_id: int,
    payload: dict[str, Any],
) -> None:
    """Write one teacher's status and refresh the hash TTL."""
    try:
        redis = get_async_redis()
        if redis is None:
            return
        previous = _decode_field(await redis.hget(_key(org_id), str(int(user_id))))
        body = dict(previous or {})
        for key, value in payload.items():
            if value is not None:
                body[key] = value
        body["user_id"] = int(user_id)
        body["updated_at"] = time.time()
        encoded = json.dumps(body, separators=(",", ":"))
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hset(_key(org_id), str(int(user_id)), encoded)
            pipe.expire(_key(org_id), ACTIVITY_TTL_SECONDS * 3)
            pipe.delete(_summary_key(org_id))
            await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.debug("[Training] touch_activity failed: %s", exc)


async def list_activity(org_id: int) -> list[dict[str, Any]]:
    """Return non-stale activity rows."""
    try:
        redis = get_async_redis()
        if redis is None:
            return []
        raw = await redis.hgetall(_key(org_id))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] list_activity failed: %s", exc)
        return []
    cutoff = time.time() - ACTIVITY_TTL_SECONDS
    rows: list[dict[str, Any]] = []
    stale_fields: list[str] = []
    for field, value in (raw or {}).items():
        key = field.decode("utf-8") if isinstance(field, bytes) else str(field)
        parsed = _decode_field(value)
        if parsed is None:
            stale_fields.append(key)
            continue
        updated = float(parsed.get("updated_at") or 0)
        if updated < cutoff:
            stale_fields.append(key)
            continue
        rows.append(parsed)
    if stale_fields:
        try:
            redis = get_async_redis()
            if redis is not None:
                await redis.hdel(_key(org_id), *stale_fields)
        except REDIS_ERRORS as exc:
            logger.debug("[Training] activity stale delete failed: %s", exc)
    rows.sort(key=lambda item: (-float(item.get("updated_at") or 0), int(item.get("user_id") or 0)))
    return rows


async def activity_summary(org_id: int) -> dict[str, int]:
    """Counts for the instructor header, cached a few seconds."""
    try:
        redis = get_async_redis()
        if redis is not None:
            raw = await redis.get(_summary_key(org_id))
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return {
                        "online": int(parsed.get("online") or 0),
                        "generating": int(parsed.get("generating") or 0),
                        "done": int(parsed.get("done") or 0),
                    }
    except REDIS_ERRORS as exc:
        logger.debug("[Training] activity_summary cache missed: %s", exc)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("[Training] activity_summary cache missed: %s", exc)
    rows = await list_activity(org_id)
    generating = 0
    done = 0
    for row in rows:
        state = str(row.get("generate_state") or "idle")
        if state == "generating":
            generating += 1
        elif state == "done":
            done += 1
    counts = {
        "online": len(rows),
        "generating": generating,
        "done": done,
    }
    try:
        redis = get_async_redis()
        if redis is not None:
            await redis.set(
                _summary_key(org_id),
                json.dumps(counts, separators=(",", ":")),
                ex=ACTIVITY_SUMMARY_TTL_SECONDS,
            )
    except REDIS_ERRORS as exc:
        logger.debug("[Training] activity_summary cache write failed: %s", exc)
    return counts


async def should_publish_activity(org_id: int) -> bool:
    """Allow at most one activity SSE doorbell per second per org."""
    try:
        redis = get_async_redis()
        if redis is None:
            return True
        won = await redis.set(
            _sse_gate_key(org_id),
            "1",
            nx=True,
            ex=ACTIVITY_SSE_MIN_SECONDS,
        )
        return bool(won)
    except REDIS_ERRORS as exc:
        logger.debug("[Training] activity SSE gate failed: %s", exc)
        return True


async def clear_activity(org_id: int) -> None:
    """Drop activity when a session ends."""
    try:
        redis = get_async_redis()
        if redis is None:
            return
        await redis.delete(_key(org_id), _summary_key(org_id), _sse_gate_key(org_id))
    except REDIS_ERRORS as exc:
        logger.debug("[Training] clear_activity failed: %s", exc)
