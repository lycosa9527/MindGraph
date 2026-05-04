"""
Shared in-process state and per-connection writer infrastructure.

Per-connection writer pattern (Discord / Centrifugo / MQTT-broker mailbox):
each WebSocket has exactly ONE writer Task that is the sole caller of
ws.send_*. All other coroutines communicate via ConnectionHandle.send_queue
(bounded asyncio.Queue). This eliminates the send-interleave race that
previously required safe_send_json, provides per-connection backpressure, and
enables sharded broadcast fanout via asyncio.TaskGroup.

Phase 8 role split (Twitch-Live-chat / Zoom-Webinar pattern):
- EditorHandle (role="host"|"editor"): full coalesce/flush infrastructure,
  queue maxsize 256, inbound editing allowed.
- ViewerHandle (role="viewer"): no coalesce_buffer / coalesce_lock /
  flush_task, queue maxsize 64.  Only ping and resync are accepted inbound.
ConnectionHandle is retained as a Union alias used by all fanout helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, Dict, Literal, Optional, Tuple, Union

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_QUEUE_MAXSIZE: int = int(os.environ.get("COLLAB_WS_QUEUE_MAXSIZE", "256"))
_VIEWER_QUEUE_MAXSIZE: int = int(os.environ.get("COLLAB_WS_QUEUE_MAXSIZE_VIEWER", "64"))
_SHARD_SIZE: int = 50

_SHUTDOWN = object()

_COALESCE_KEY: Dict[str, Callable] = {
    "node_editing": lambda p: (p.get("node_id"), p.get("user_id")),
    "node_selected": lambda p: (p.get("node_id"), p.get("user_id")),
    "room_idle_warning": lambda _: (),
}

_BACKPRESSURE_POLICY: Dict[str, str] = {
    "ping": "drop",
    "pong": "drop",
    "error": "block_short",
    "update_ack": "block_short",
    "node_editing": "coalesce",
    "node_editing_batch": "block_short",
    "node_selected": "coalesce",
    "update": "block_short",
    "joined": "block_short",
    "user_joined": "block_short",
    "user_left": "block_short",
    "snapshot": "block_short",
    "room_idle_warning": "coalesce",
    "node_editing_batch_ws": "drop_oldest",
    "kicked": "block_long",
    "session_ended_shutdown": "block_long",
    "room_idle_shutdown": "block_long",
}


@dataclass
class ConnectionHandle:
    """
    Per-WebSocket send handle for host / editor connections.

    Only _writer_loop ever calls ws.send_*; everything else enqueues here.
    Storing code and user_id enables eviction and cleanup without extra args.
    role is "host" or "editor"; viewers use ViewerHandle.
    """

    websocket: WebSocket
    code: str
    user_id: int
    send_queue: asyncio.Queue
    role: Literal["host", "editor"] = "editor"
    writer_task: Optional[asyncio.Task] = None
    coalesce_buffer: Dict[Tuple[str, tuple], Dict] = field(default_factory=dict)
    coalesce_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    flush_task: Optional[asyncio.Task] = None
    qsize_high_water: int = 0


@dataclass
class ViewerHandle:
    """
    Stripped-down send handle for passive viewer connections.

    Viewers receive broadcast frames (update diffs, snapshots) but cannot
    send editing messages. No coalesce_buffer, coalesce_lock, or flush_task.
    Queue maxsize is 64 (vs 256 for editors) — viewers receive fewer
    awareness frames.  Per-connection memory ~1 KB vs ~3 KB for editors.
    """

    websocket: WebSocket
    code: str
    user_id: int
    send_queue: asyncio.Queue
    role: Literal["viewer"] = "viewer"
    writer_task: Optional[asyncio.Task] = None
    qsize_high_water: int = 0
    last_seen_seq: int = 0


AnyHandle = Union[ConnectionHandle, ViewerHandle]

ACTIVE_CONNECTIONS: Dict[str, Dict[int, AnyHandle]] = {}
ACTIVE_EDITORS: Dict[str, Dict[str, Dict[int, str]]] = {}
_ROOM_REGISTRY_LOCKS: Dict[str, asyncio.Lock] = {}
_REGISTRY_LOCKS_GUARD = asyncio.Lock()


async def _get_room_lock(code: str) -> asyncio.Lock:
    """Return per-room mutation lock (single Lock per ``code``, TOCTOU-safe)."""
    room_lock = _ROOM_REGISTRY_LOCKS.get(code)
    if room_lock is not None:
        return room_lock
    async with _REGISTRY_LOCKS_GUARD:
        return _ROOM_REGISTRY_LOCKS.setdefault(code, asyncio.Lock())


async def _writer_loop(handle: AnyHandle) -> None:
    """
    Sole owner of ws.send_* for this connection.

    Reads from send_queue; stops on _SHUTDOWN sentinel or send error.
    By construction only this coroutine calls send_* so no Lock is needed.
    """
    ws = handle.websocket
    queue = handle.send_queue
    while True:
        item = await queue.get()
        if item is _SHUTDOWN:
            return
        kind, body = item
        try:
            async with asyncio.timeout(0.8):
                if kind == "bytes":
                    await ws.send_bytes(body)
                else:
                    await ws.send_text(body)
            logger.debug(
                "[WSFanout] writer_send code=%s user=%s kind=%s size=%d",
                handle.code, handle.user_id, kind,
                len(body) if isinstance(body, (bytes, str)) else 0,
            )
        except (
            TimeoutError,
            ConnectionError,
            OSError,
            RuntimeError,
            AssertionError,
            TypeError,
        ) as send_exc:
            logger.debug(
                "[WSFanout] writer_loop send error — closing code=%s user=%s kind=%s: %s",
                handle.code, handle.user_id, kind, send_exc,
            )
            return


async def _flush_coalesce_buffer(handle: ConnectionHandle) -> None:
    """
    50 ms batch window flush for coalesced frames.

    Groups node_editing events into node_editing_batch_ws for clients that
    support it (ship frontend handler first, then enable batching).
    """
    await asyncio.sleep(0.050)
    async with handle.coalesce_lock:
        items = list(handle.coalesce_buffer.values())
        handle.coalesce_buffer.clear()
        handle.flush_task = None
    if not items:
        return
    by_type: Dict[str, list] = {}
    for payload in items:
        by_type.setdefault(payload.get("type", "unknown"), []).append(payload)
    for msg_type, group in by_type.items():
        if msg_type == "node_editing" and len(group) > 1:
            frame = {"type": "node_editing_batch_ws", "events": group}
            try:
                from services.infrastructure.monitoring.ws_metrics import (
                    record_ws_batch_frames_emitted,
                )
                record_ws_batch_frames_emitted()
            except Exception:
                pass
        elif len(group) == 1:
            frame = group[0]
        else:
            frame = {"type": msg_type, "events": group}
        try:
            body = json.dumps(frame, ensure_ascii=False)
            handle.send_queue.put_nowait(("text", body))
            handle.qsize_high_water = max(
                handle.qsize_high_water, handle.send_queue.qsize()
            )
        except asyncio.QueueFull:
            asyncio.create_task(
                _evict_slow_consumer(handle, "coalesce flush queue full"),
                name=f"evict:{handle.code}:{handle.user_id}",
            )
            return
        except Exception as exc:
            logger.debug(
                "[ConnectionHandle] flush_coalesce_buffer error code=%s: %s",
                handle.code, exc,
            )


async def _evict_slow_consumer(handle: AnyHandle, reason: str) -> None:
    """
    Remove a slow peer from the room.

    Sends a best-effort kicked frame, closes the socket with 4014, removes
    from registry, and removes from participant set.
    """
    try:
        from services.infrastructure.monitoring.ws_metrics import record_ws_slow_consumer
        record_ws_slow_consumer(reason)
    except Exception:
        pass
    kicked_body = json.dumps({
        "type": "kicked",
        "reason": f"slow consumer: {reason}",
        "role": handle.role,
    })
    try:
        await asyncio.wait_for(
            handle.send_queue.put(("text", kicked_body)),
            timeout=0.2,
        )
    except Exception:
        pass
    try:
        async with asyncio.timeout(1.0):
            await handle.websocket.close(code=4014, reason="slow consumer evicted")
    except Exception:
        pass
    try:
        from routers.api.workshop_ws_disconnect import (
            finalize_canvas_collab_disconnect,
        )
        user_stub = SimpleNamespace(id=handle.user_id)
        owner_id = handle.user_id if handle.role == "host" else None
        await finalize_canvas_collab_disconnect(
            code=handle.code,
            user=user_stub,
            handle=handle,
            workshop_owner_id=owner_id,
        )
    except Exception as exc:
        logger.warning(
            "[ConnectionHandle] slow-consumer cleanup failed code=%s user=%s: %s",
            handle.code, handle.user_id, exc,
        )


async def enqueue(handle: AnyHandle, payload: dict, msg_type: str) -> None:
    """
    Route a message through the per-message-type backpressure policy.

    Policies:
      drop        - put_nowait; silently drop on QueueFull (low-value frames)
      coalesce    - route through coalesce buffer (last value wins per key)
      block_short - wait up to 0.1 s; evict on timeout
      block_long  - wait up to 1.0 s; evict on timeout (critical frames)
      drop_oldest - drain oldest item then retry put_nowait
    """
    policy = _BACKPRESSURE_POLICY.get(msg_type, "block_short")

    if policy == "coalesce" and isinstance(handle, ViewerHandle):
        policy = "drop"

    if policy == "coalesce":
        if not isinstance(handle, ConnectionHandle):
            return
        extractor = _COALESCE_KEY.get(msg_type)
        drain_key: tuple = extractor(payload) if extractor else ()
        async with handle.coalesce_lock:
            handle.coalesce_buffer[(msg_type, drain_key)] = payload
            if handle.flush_task is None or handle.flush_task.done():
                handle.flush_task = asyncio.create_task(
                    _flush_coalesce_buffer(handle),
                    name=f"flush:{handle.code}:{handle.user_id}",
                )
        try:
            from services.infrastructure.monitoring.ws_metrics import (
                record_ws_coalesce_hit,
            )
            record_ws_coalesce_hit(msg_type)
        except Exception:
            pass
        return

    try:
        body = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.debug(
            "[ConnectionHandle] enqueue: serialize failed msg_type=%s code=%s",
            msg_type, handle.code,
        )
        return
    item = ("text", body)

    if policy == "drop":
        try:
            handle.send_queue.put_nowait(item)
            handle.qsize_high_water = max(
                handle.qsize_high_water, handle.send_queue.qsize()
            )
        except asyncio.QueueFull:
            pass
        return

    if policy == "drop_oldest":
        try:
            handle.send_queue.put_nowait(item)
            handle.qsize_high_water = max(
                handle.qsize_high_water, handle.send_queue.qsize()
            )
        except asyncio.QueueFull:
            try:
                handle.send_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                handle.send_queue.put_nowait(item)
            except asyncio.QueueFull:
                pass
        return

    timeout = 0.1 if policy == "block_short" else 1.0
    try:
        await asyncio.wait_for(handle.send_queue.put(item), timeout=timeout)
        handle.qsize_high_water = max(
            handle.qsize_high_water, handle.send_queue.qsize()
        )
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning(
            "[ConnectionHandle] enqueue timeout policy=%s msg_type=%s "
            "code=%s user=%s",
            policy, msg_type, handle.code, handle.user_id,
        )
        asyncio.create_task(
            _evict_slow_consumer(handle, f"enqueue timeout ({msg_type})"),
            name=f"evict:{handle.code}:{handle.user_id}",
        )


def create_connection_handle(
    code: str,
    user_id: int,
    ws: WebSocket,
    role: str = "editor",
) -> AnyHandle:
    """
    Create EditorHandle or ViewerHandle and start its writer task.

    Does NOT register the handle in ACTIVE_CONNECTIONS so the socket is not
    yet eligible for fan-out delivery.  Call ``activate_connection`` after the
    join handshake/snapshot has been enqueued so the snapshot is always the
    first frame the client receives.

    role="host"/"editor" → ConnectionHandle (full coalesce).
    role="viewer"        → ViewerHandle (smaller queue, no coalesce).
    """
    if role == "viewer":
        queue: asyncio.Queue = asyncio.Queue(maxsize=_VIEWER_QUEUE_MAXSIZE)
        handle: AnyHandle = ViewerHandle(
            websocket=ws,
            code=code,
            user_id=user_id,
            send_queue=queue,
            role="viewer",
        )
    else:
        queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        effective_role: Literal["host", "editor"] = (
            "host" if role == "host" else "editor"
        )
        handle = ConnectionHandle(
            websocket=ws,
            code=code,
            user_id=user_id,
            send_queue=queue,
            role=effective_role,
        )
    writer = asyncio.create_task(
        _writer_loop(handle),
        name=f"ws_writer:{code}:{user_id}:{role}",
    )

    def _on_writer_done(task: asyncio.Task) -> None:
        exc = task.exception() if not task.cancelled() else None
        if exc is not None:
            logger.warning(
                "[WriterTask] Unexpected exception code=%s user=%s: %s",
                code, user_id, exc,
            )
            try:
                from services.infrastructure.monitoring.ws_metrics import (  # pylint: disable=import-outside-toplevel
                    record_ws_writer_task_failed,
                )
                record_ws_writer_task_failed()
            except Exception:
                pass

    writer.add_done_callback(_on_writer_done)
    handle.writer_task = writer
    return handle


async def activate_connection(code: str, user_id: int, handle: AnyHandle) -> None:
    """
    Register an already-created handle in ACTIVE_CONNECTIONS.

    Call this AFTER the join handshake (snapshot) has been enqueued so that
    fan-out delivery can never place an ``update`` frame ahead of the baseline
    snapshot in the handle's send_queue.
    """
    room_lock = await _get_room_lock(code)
    async with room_lock:
        ACTIVE_CONNECTIONS.setdefault(code, {})[user_id] = handle
    logger.debug(
        "[WorkshopWS] activate_connection code=%s user=%s role=%s",
        code, user_id, handle.role,
    )


async def register_connection(
    code: str,
    user_id: int,
    ws: WebSocket,
    role: str = "editor",
) -> AnyHandle:
    """
    Convenience wrapper: create handle + activate in ACTIVE_CONNECTIONS atomically.

    Retained for callers that do not need the two-step
    create → handshake → activate sequence (e.g. test helpers, admin paths).
    The canonical WebSocket endpoint in ``workshop_ws.py`` uses the two-step
    form to prevent the join-time fan-out race.
    """
    handle = create_connection_handle(code, user_id, ws, role=role)
    await activate_connection(code, user_id, handle)
    return handle


async def _cancel_flush_and_drain_writer(handle: AnyHandle) -> None:
    """
    Cancel coalesce flush task, send writer _SHUTDOWN, await writer briefly.

    Used by unregister and supersede paths so tasks do not leak.
    """
    flush_task = getattr(handle, "flush_task", None)
    if flush_task is not None and not flush_task.done():
        flush_task.cancel()
        try:
            await flush_task
        except asyncio.CancelledError:
            pass
    writer = handle.writer_task
    if writer is not None and not writer.done():
        try:
            handle.send_queue.put_nowait(_SHUTDOWN)
        except asyncio.QueueFull:
            writer.cancel()
        else:
            try:
                await asyncio.wait_for(writer, timeout=0.5)
            except (asyncio.TimeoutError, TimeoutError, asyncio.CancelledError):
                writer.cancel()
                try:
                    await writer
                except asyncio.CancelledError:
                    pass


async def finalize_handle_writer_shutdown(handle: AnyHandle) -> None:
    """
    Cancel coalesce flush and stop the per-connection writer task.

    Used by force-close paths and shared with ``unregister_connection``.
    """
    await _cancel_flush_and_drain_writer(handle)


async def teardown_superseded_connection(
    code: str,
    user_id: int,
    superseded: AnyHandle,
) -> None:
    """
    Remove superseded handle from ACTIVE_CONNECTIONS if still registered, then
    stop its writer / flush tasks.

    Call before register_connection when the same user opens a new session
    so the prior tab's tasks are not leaked.
    """
    room_lock = await _get_room_lock(code)
    async with room_lock:
        room = ACTIVE_CONNECTIONS.get(code)
        if room is not None and room.get(user_id) is superseded:
            room.pop(user_id, None)
            if not room:
                ACTIVE_CONNECTIONS.pop(code, None)
                _ROOM_REGISTRY_LOCKS.pop(code, None)
    await finalize_handle_writer_shutdown(superseded)


async def unregister_connection(code: str, user_id: int) -> None:
    """
    Remove from registry and tear down writer/flush tasks.

    Sends _SHUTDOWN sentinel so the writer drains its queue before exiting.
    Falls back to cancel() if the queue is full.

    Uses the per-room lock to guard the dict mutation so the
    remove-last-user → pop-room path is always atomic.
    """
    room_lock = await _get_room_lock(code)
    async with room_lock:
        room = ACTIVE_CONNECTIONS.get(code)
        if room is None:
            handle = None
        else:
            handle = room.pop(user_id, None)
            if not room:
                ACTIVE_CONNECTIONS.pop(code, None)
                _ROOM_REGISTRY_LOCKS.pop(code, None)

    if handle is None:
        return

    logger.debug(
        "[WorkshopWS] unregister_connection code=%s user=%s",
        code, user_id,
    )
    await finalize_handle_writer_shutdown(handle)
