"""
Viewer snapshot refresh task (Phase 8.4 - Twitch/Zoom viewer pattern).

Maintains a per-room ``workshop:snapshot:{code}`` Redis key that is refreshed
every 2 s while any ViewerHandle connections are active in this process.

Viewers join via snapshot read instead of the hot live_spec key, eliminating
reconnect-storm hot-key contention when 100-500 viewers reload simultaneously.

Leader election: Redis NX lock so only one worker per machine refreshes each
code. Each worker runs its own background task per room; the second writer
simply loses the NX race every cycle and returns quickly.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS,
    ViewerHandle,
)
from services.online_collab.redis.online_collab_redis_keys import (
    live_spec_key,
    snapshot_key,
    snapshot_leader_key,
    snapshot_seq_key,
)
from services.online_collab.spec.online_collab_live_spec import spec_for_snapshot
from services.online_collab.spec.online_collab_live_spec_json import (
    parse_json_get_bulk,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_SNAPSHOT_REFRESH_INTERVAL_SEC: float = 2.0
_SNAPSHOT_TTL_SEC: int = 30
_SNAPSHOT_LEADER_TTL_SEC: int = 5

_SNAPSHOT_TASKS: Dict[str, asyncio.Task] = {}


def _has_viewers(code: str) -> bool:
    """Return True if any ViewerHandle is active for *code* in this process."""
    room = ACTIVE_CONNECTIONS.get(code)
    if not room:
        return False
    return any(isinstance(h, ViewerHandle) for h in room.values())


async def _refresh_snapshot_once(redis: Any, code: str) -> bool:
    """
    Attempt to read live spec and write the snapshot key.

    Returns True on success, False if the live spec is unavailable.
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.execute_command("JSON.GET", live_spec_key(code), "$")
        pipe.get(snapshot_seq_key(code))
        raw_doc, raw_seq = await pipe.execute()
    doc = parse_json_get_bulk(raw_doc)
    if not doc:
        return False
    snap = spec_for_snapshot(doc)
    ver = int(doc.get("v", 1))
    try:
        if raw_seq is None:
            seq = 0
        elif isinstance(raw_seq, (bytes, bytearray, memoryview)):
            seq = int(bytes(raw_seq).decode("utf-8", errors="replace").strip() or "0")
        else:
            seq = int(str(raw_seq).strip() or "0")
    except (TypeError, ValueError):
        seq = 0
    payload = json.dumps({
        "spec": snap,
        "version": ver,
        "seq": seq,
        "ts": time.time(),
    }, ensure_ascii=False)
    await redis.set(snapshot_key(code), payload, ex=_SNAPSHOT_TTL_SEC)
    return True


async def _snapshot_refresh_loop(code: str) -> None:
    """
    Background loop that refreshes the viewer snapshot every 2 s.

    Stops automatically when no ViewerHandle connections remain.
    Uses Redis NX lock so only one worker per machine does the write.
    """
    redis = get_async_redis()
    if redis is None:
        return
    while _has_viewers(code):
        try:
            leader_key = snapshot_leader_key(code)
            is_leader = await redis.set(
                leader_key, "1", nx=True, ex=_SNAPSHOT_LEADER_TTL_SEC
            )
            if is_leader:
                await _refresh_snapshot_once(redis, code)
        except (RedisError, OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.debug(
                "[ViewerSnapshot] refresh error code=%s: %s", code, exc,
            )
        await asyncio.sleep(_SNAPSHOT_REFRESH_INTERVAL_SEC)
    _SNAPSHOT_TASKS.pop(code, None)
    logger.debug("[ViewerSnapshot] loop stopped (no viewers) code=%s", code)


def ensure_snapshot_task(code: str) -> None:
    """
    Start the snapshot refresh background task for *code* if not already running.

    Safe to call on every viewer connect; idempotent.
    """
    existing = _SNAPSHOT_TASKS.get(code)
    if existing is not None and not existing.done():
        return
    task = asyncio.create_task(
        _snapshot_refresh_loop(code),
        name=f"snapshot_refresh:{code}",
    )
    _SNAPSHOT_TASKS[code] = task


async def read_viewer_snapshot(code: str) -> Optional[Dict[str, Any]]:
    """
    Read the cached viewer snapshot from Redis.

    Returns the parsed dict (keys: spec, version, seq, ts) or None if not
    available, in which case callers should fall back to the live spec read.
    """
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(snapshot_key(code))
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, OSError, ValueError, TypeError) as exc:
        logger.debug("[ViewerSnapshot] read failed code=%s: %s", code, exc)
        return None
