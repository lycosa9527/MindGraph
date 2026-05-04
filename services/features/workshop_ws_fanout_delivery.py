"""
Local WebSocket delivery for diagram workshop Redis fan-out (per worker).

Sharded broadcast pattern (Discord / Centrifugo style):
- Pre-encode payload to bytes ONCE per broadcast
- Split room into shards of _SHARD_SIZE peers
- Fan out shards concurrently via asyncio.TaskGroup (put_nowait into each
  handle's send_queue; no direct ws.send_* here)
- Slow peers that fill their queue are evicted without affecting others

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
from collections import OrderedDict
from typing import Optional

from fastapi.websockets import WebSocketState

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS,
    ACTIVE_EDITORS,
    AnyHandle,
    ViewerHandle,
    _SHARD_SIZE,
    _evict_slow_consumer,
    _get_room_lock,
    enqueue,
    finalize_handle_writer_shutdown,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_broadcast_latency,
    record_ws_broadcast_send_failure,
    record_ws_broadcast_shards,
)

logger = logging.getLogger(__name__)

_DEDUP_CAP = max(512, int(os.getenv('WORKSHOP_FANOUT_MSG_DEDUP', '8192')))
_RECENT_FANOUT_IDS: OrderedDict[str, None] = OrderedDict()

ROOM_IDLE_SHUTDOWN_TYPE = 'room_idle_shutdown'
SESSION_ENDED_SHUTDOWN_TYPE = 'session_ended_shutdown'


async def _close_one_handle(
    user_id: int,
    handle: AnyHandle,
    reason: str,
    close_code: int,
    close_reason: str,
    kicked_payload: dict,
) -> None:
    """Enqueue kicked frame, stop writer/flush tasks, then close the socket."""
    try:
        await enqueue(handle, dict(kicked_payload), "kicked")
    except Exception:
        try:
            record_ws_broadcast_send_failure()
        except Exception:
            pass
    try:
        await finalize_handle_writer_shutdown(handle)
    except Exception as exc:
        logger.warning(
            "[WorkshopWS] %s writer finalize failed user=%s workshop=%s: %s",
            reason,
            user_id,
            str(getattr(handle, "code", "")),
            exc,
        )
    try:
        if handle.websocket.client_state == WebSocketState.CONNECTED:
            await handle.websocket.close(code=close_code, reason=close_reason)
    except (
        AssertionError,
        ConnectionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        logger.warning(
            "[WorkshopWS] %s close failed user=%s workshop=%s: %s",
            reason, user_id, str(getattr(handle, "code", "")), exc,
        )


async def _force_close_local_room(
    code: str,
    *,
    reason: str,
    close_code: int,
    close_reason: str,
) -> None:
    """Send a kicked frame + close code to every local socket for ``code`` in parallel."""
    kicked = {"type": "kicked", "reason": reason}
    room_snapshot = list(ACTIVE_CONNECTIONS.get(code, {}).items())
    async with asyncio.TaskGroup() as tg:
        for user_id, handle in room_snapshot:
            tg.create_task(
                _close_one_handle(
                    user_id, handle, reason, close_code, close_reason, kicked,
                ),
                name=f"force_close:{code}:{user_id}",
            )
    room_lock = await _get_room_lock(code)
    async with room_lock:
        ACTIVE_EDITORS.pop(code, None)
        ACTIVE_CONNECTIONS.pop(code, None)


async def force_disconnect_local_workshop_session_ended(code: str) -> None:
    """Tell each local socket the host ended the session (close 4011)."""
    await _force_close_local_room(
        code,
        reason="session_ended",
        close_code=4011,
        close_reason="session ended by host",
    )


async def force_disconnect_local_workshop_room_idle(code: str) -> None:
    """Tell each local socket collaboration ended for room idle (close 4010)."""
    await _force_close_local_room(
        code,
        reason="room_idle",
        close_code=4010,
        close_reason="room idle timeout",
    )


_FANOUT_SHARD_CONCURRENCY = int(
    __import__("os").getenv("WORKSHOP_FANOUT_SHARD_CONCURRENCY", "50")
)


async def _push_shard(
    shard: list,
    body_payload: tuple,
    mode: str,
    exclude_user: Optional[int],
    code: str,
    sem: asyncio.Semaphore,
    seq: Optional[int] = None,
) -> None:
    """Push pre-encoded payload to a shard of handles via put_nowait."""
    try:
        async with sem:
            for user_id, handle in shard:
                if mode == "others" and exclude_user is not None and user_id == exclude_user:
                    continue
                if isinstance(handle, ViewerHandle) and seq is not None:
                    handle.last_seen_seq = seq
                try:
                    handle.send_queue.put_nowait(body_payload)
                    handle.qsize_high_water = max(
                        handle.qsize_high_water, handle.send_queue.qsize()
                    )
                except asyncio.QueueFull:
                    await _evict_slow_consumer(handle, "broadcast queue full")
                except Exception as exc:
                    logger.debug(
                        "[WorkshopWS] _push_shard: put_nowait error user=%s code=%s: %s",
                        user_id, code, exc,
                    )
    except Exception as exc:
        logger.warning(
            "[WorkshopWS] _push_shard unhandled error code=%s: %s", code, exc,
        )


async def deliver_local_workshop_broadcast(
    code: str,
    mode: str,
    exclude_user: Optional[int],
    data_str: str,
) -> None:
    """Deliver a workshop payload to WebSockets connected on this worker."""
    try:
        message = json.loads(data_str)
    except json.JSONDecodeError:
        logger.warning(
            "[WorkshopWS] Fan-out: JSONDecodeError for workshop %s, dropping payload",
            code,
        )
        return
    if isinstance(message, dict):
        raw_mid = message.get('msg_id')
        if isinstance(raw_mid, str) and raw_mid.strip():
            mid = raw_mid.strip()
            if mid in _RECENT_FANOUT_IDS:
                _RECENT_FANOUT_IDS.move_to_end(mid)
                logger.debug(
                    "[WorkshopWS] Fan-out duplicate msg_id=%s workshop=%s (dedup)",
                    mid,
                    code,
                )
                return
            _RECENT_FANOUT_IDS[mid] = None
            while len(_RECENT_FANOUT_IDS) > _DEDUP_CAP:
                _RECENT_FANOUT_IDS.popitem(last=False)
        msg_type = message.get("type")
        if msg_type == ROOM_IDLE_SHUTDOWN_TYPE:
            logger.debug(
                "[WSFanout] room_idle_shutdown dispatch code=%s",
                code,
            )
            await force_disconnect_local_workshop_room_idle(code)
            return
        if msg_type == SESSION_ENDED_SHUTDOWN_TYPE:
            logger.debug(
                "[WSFanout] session_ended_shutdown dispatch code=%s",
                code,
            )
            await force_disconnect_local_workshop_session_ended(code)
            return
    if code not in ACTIVE_CONNECTIONS:
        logger.debug(
            "[WSFanout] deliver_drop code=%s — no local participants",
            code,
        )
        return

    seq: Optional[int] = None
    if isinstance(message, dict):
        raw_seq = message.get("seq")
        if isinstance(raw_seq, int):
            seq = raw_seq

    body_payload: tuple = ("text", data_str)

    handles = list(ACTIVE_CONNECTIONS.get(code, {}).items())
    if not handles:
        return

    logger.debug(
        "[WSFanout] deliver_start code=%s mode=%s exclude=%s peers=%d"
        " msg_type=%s seq=%s",
        code, mode, exclude_user, len(handles),
        message.get("type") if isinstance(message, dict) else None,
        seq,
    )

    shards = [
        handles[i: i + _SHARD_SIZE]
        for i in range(0, len(handles), _SHARD_SIZE)
    ]
    try:
        record_ws_broadcast_shards(len(shards))
    except Exception:
        pass

    sem = asyncio.Semaphore(_FANOUT_SHARD_CONCURRENCY)
    _t0 = time.perf_counter()
    async with asyncio.TaskGroup() as task_group:
        for shard in shards:
            task_group.create_task(
                _push_shard(shard, body_payload, mode, exclude_user, code, sem, seq),
                name=f"fanout_shard:{code}",
            )
    asyncio.create_task(
        _record_broadcast_latency((time.perf_counter() - _t0) * 1000.0)
    )


async def _record_broadcast_latency(latency_ms: float) -> None:
    """Fire-and-forget latency sample recording."""
    try:
        record_ws_broadcast_latency(latency_ms)
    except Exception:
        pass
