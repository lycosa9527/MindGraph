"""
Background Redis subscriber for WebSocket fan-out (native asyncio pub/sub).

Phase 1 architecture: pub/sub is the ONLY broadcast delivery path.
  The previous XREADGROUP Streams consumer group has been removed: a single
  consumer group with N workers load-balances each entry to exactly ONE
  worker, silently dropping ~(N-1)/N of broadcasts on multi-worker deployments.
  Pub/sub broadcasts to ALL subscribers, which is the correct semantic for
  room-broadcast fanout.

Benefits of native asyncio pub/sub:
- Zero polling latency (push-based, no 500 ms sleep)
- No OS thread; runs entirely on the event loop
- Automatic reconnection via supervisor loop

Local deliveries are routed through a bounded ``asyncio.Queue`` so the Redis
listen loop never awaits slow WebSocket sends (head-of-line blocking).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Final, Optional, Tuple

from redis.exceptions import RedisError

from services.features.ws_redis_fanout_config import (
    CHAT_FANOUT_CHANNEL,
    ENVELOPE_VERSION,
    WORKSHOP_FANOUT_CHANNEL,
    is_ws_fanout_enabled,
    set_sharded_pubsub_active,
    use_sharded_pubsub,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from services.features.workshop_ws_fanout_delivery import (
    deliver_local_workshop_broadcast,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_fanout_chat_received,
    record_ws_fanout_delivery_queue_drop,
    record_ws_fanout_workshop_received,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0
_KIND_CHAT: Final[str] = "chat"
_KIND_WS: Final[str] = "ws"


def _fanout_delivery_queue_maxsize() -> int:
    raw = os.environ.get("WORKSHOP_FANOUT_DELIVERY_QUEUE_MAX")
    default = 8192
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class _FanoutListenerState:
    """Holds the asyncio.Task handle and stop signal."""

    __slots__ = ("listener_task", "stop_event")

    def __init__(self) -> None:
        self.listener_task: Optional[asyncio.Task] = None
        self.stop_event: Optional[asyncio.Event] = None


_state = _FanoutListenerState()


def _enqueue_fanout_payload(
    delivery_queue: "asyncio.Queue[Tuple[str, str]]",
    kind: str,
    payload: str,
) -> None:
    try:
        delivery_queue.put_nowait((kind, payload))
    except asyncio.QueueFull:
        try:
            record_ws_fanout_delivery_queue_drop()
        except Exception:
            pass
        logger.warning("[WSFanout] delivery queue full; dropping %s frame", kind)


async def _fanout_delivery_worker(
    delivery_queue: "asyncio.Queue[Tuple[str, str]]",
    stop_event: asyncio.Event,
) -> None:
    """Drain the queue and await local WebSocket delivery (off the pub/sub path)."""
    while True:
        if stop_event.is_set() and delivery_queue.empty():
            break
        try:
            kind, payload = await asyncio.wait_for(
                delivery_queue.get(), timeout=0.25,
            )
        except asyncio.TimeoutError:
            continue
        try:
            if kind == _KIND_CHAT:
                await _handle_chat_raw(payload)
            elif kind == _KIND_WS:
                await _handle_workshop_raw(payload)
        except Exception as exc:
            logger.debug("[WSFanout] delivery worker error kind=%s: %s", kind, exc)
        finally:
            delivery_queue.task_done()


async def _handle_chat_raw(payload: str) -> None:
    """Dispatch a chat fan-out envelope to local WebSocket connections."""
    try:
        env = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("[WSFanout] Chat fan-out: bad JSON")
        return
    if env.get("v") != ENVELOPE_VERSION:
        return
    kind = env.get("k")
    data_str = env.get("d")
    if not isinstance(data_str, str):
        return

    record_ws_fanout_chat_received()

    if kind == "ch":
        cid = env.get("cid")
        ex = env.get("ex")
        if not isinstance(cid, int):
            return
        exclude = ex if isinstance(ex, int) else None
        await chat_ws_manager.deliver_local_channel_broadcast(cid, exclude, data_str)
        return

    if kind == "u":
        uid = env.get("uid")
        if not isinstance(uid, int):
            return
        await chat_ws_manager.deliver_local_user_message(uid, data_str)
        return

    if kind == "po":
        oid = env.get("oid")
        ex = env.get("ex")
        if not isinstance(oid, int):
            return
        exclude = ex if isinstance(ex, int) else None
        await chat_ws_manager.deliver_local_presence_org(oid, exclude, data_str)


_FANOUT_ORIGIN_SECRET: str = os.environ.get("COLLAB_FANOUT_ORIGIN_SECRET", "")


async def _handle_workshop_raw(payload: str) -> None:
    """Dispatch a workshop fan-out envelope to local WebSocket connections."""
    try:
        env = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("[WSFanout] Workshop fan-out: bad JSON")
        return
    if env.get("v") != ENVELOPE_VERSION:
        logger.debug(
            "[WSFanout] workshop envelope version mismatch got=%s expected=%s",
            env.get("v"), ENVELOPE_VERSION,
        )
        return
    if env.get("k") != "ws":
        logger.debug("[WSFanout] workshop envelope wrong kind=%s", env.get("k"))
        return
    # Reject envelopes that lack the expected origin secret when enforcement is
    # active.  This prevents a Redis-write-capable attacker from injecting
    # arbitrary payloads (e.g. forged shutdown signals) into the fan-out pipe.
    if _FANOUT_ORIGIN_SECRET and env.get("origin") != _FANOUT_ORIGIN_SECRET:
        logger.warning("[WSFanout] rejected envelope with invalid origin")
        return
    code = env.get("code")
    mode = env.get("mode")
    data_str = env.get("d")
    ex = env.get("ex")
    if not isinstance(code, str) or mode not in ("all", "others"):
        logger.debug(
            "[WSFanout] workshop envelope invalid fields code=%s mode=%s",
            code, mode,
        )
        return
    if not isinstance(data_str, str):
        logger.debug(
            "[WSFanout] workshop envelope missing data_str code=%s",
            code,
        )
        return
    exclude = ex if isinstance(ex, int) else None

    record_ws_fanout_workshop_received()
    try:
        _inner_msg = json.loads(data_str) if data_str else {}
    except Exception:
        logger.debug("[WSFanout] workshop envelope inner JSON parse failed code=%s", code)
        _inner_msg = {}
    logger.debug(
        "[WSFanout] recv_dispatch code=%s mode=%s exclude=%s msg_type=%s seq=%s",
        code, mode, exclude,
        _inner_msg.get("type"), _inner_msg.get("seq"),
    )
    await deliver_local_workshop_broadcast(code, mode, exclude, data_str)


async def _pubsub_subscribe(pubsub: Any, *channels: str) -> None:
    """
    Subscribe via SSUBSCRIBE when the sharded flag is set, else plain SUBSCRIBE.

    SSUBSCRIBE on redis-py async requires ``pubsub.ssubscribe`` which is
    available on redis-py 5+. When either the client or server lacks
    support we transparently fall back to SUBSCRIBE.

    Sets ``_sharded_pubsub_active`` so the publisher uses the matching
    transport (SPUBLISH when sharded, PUBLISH when plain).  Without this
    coordination, SPUBLISH messages are silently lost on Redis 7.0+ when
    the subscriber is on a plain SUBSCRIBE channel.
    """
    if use_sharded_pubsub() and hasattr(pubsub, "ssubscribe"):
        try:
            await pubsub.ssubscribe(*channels)
            set_sharded_pubsub_active(True)
            logger.info("[WSFanout] SSUBSCRIBED to %s", ", ".join(channels))
            return
        except (RedisError, AttributeError, TypeError) as exc:
            logger.info(
                "[WSFanout] SSUBSCRIBE failed (%s) — falling back to SUBSCRIBE"
                " (publisher will also use PUBLISH)",
                exc,
            )
    set_sharded_pubsub_active(False)
    await pubsub.subscribe(*channels)
    logger.info("[WSFanout] Subscribed to %s", ", ".join(channels))


async def _pubsub_listen_loop(
    pubsub: Any,
    stop_event: asyncio.Event,
    delivery_queue: "asyncio.Queue[Tuple[str, str]]",
) -> None:
    """Inner loop for pub/sub deliveries (non-blocking: only enqueues payloads)."""
    async for message in pubsub.listen():
        if stop_event.is_set():
            break
        if message is None or message.get("type") not in ("message", "smessage"):
            continue

        channel: Any = message.get("channel")
        data: Any = message.get("data")
        if isinstance(channel, (bytes, bytearray)):
            try:
                channel = channel.decode("utf-8")
            except UnicodeDecodeError:
                continue
        if isinstance(data, (bytes, bytearray)):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
        if not isinstance(data, str):
            continue

        if channel == CHAT_FANOUT_CHANNEL:
            _enqueue_fanout_payload(delivery_queue, _KIND_CHAT, data)
        elif channel == WORKSHOP_FANOUT_CHANNEL:
            logger.debug(
                "[WSFanout] pubsub_recv channel=%s data_len=%d",
                channel, len(data),
            )
            _enqueue_fanout_payload(delivery_queue, _KIND_WS, data)


async def _listener_loop_async(stop_event: asyncio.Event) -> None:
    """
    Native asyncio pub/sub listener (sole delivery path for broadcast fanout).

    Subscribes to both CHAT and WORKSHOP pub/sub channels and dispatches
    messages directly as coroutines on the event loop. SSUBSCRIBE is used
    when COLLAB_REDIS_SPUBLISH is on (default). Reconnects automatically
    after errors until stop_event is set.

    Note: Streams consumer group was removed in Phase 1 because XREADGROUP
    load-balances entries to only ONE consumer in the group, which is wrong
    for broadcast semantics. Pub/sub delivers to ALL subscribers, which is
    the correct model for room broadcast across uvicorn workers.
    """
    while not stop_event.is_set():
        client = get_async_redis()
        if not client:
            logger.warning(
                "[WSFanout] No async Redis client; retrying in %.1fs",
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
            continue

        pubsub = client.pubsub()
        delivery_queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue(
            maxsize=_fanout_delivery_queue_maxsize(),
        )
        worker_task = asyncio.create_task(
            _fanout_delivery_worker(delivery_queue, stop_event),
            name="ws-fanout-delivery",
        )
        listen_task: Optional[asyncio.Task[None]] = None
        loop_error: Optional[BaseException] = None
        listener_cancelled = False
        try:
            await _pubsub_subscribe(
                pubsub,
                CHAT_FANOUT_CHANNEL,
                WORKSHOP_FANOUT_CHANNEL,
            )
            listen_task = asyncio.create_task(
                _pubsub_listen_loop(pubsub, stop_event, delivery_queue),
                name="ws-fanout-pubsub",
            )
            await listen_task
        except asyncio.CancelledError:
            listener_cancelled = True
        except BaseException as exc:
            loop_error = exc
        finally:
            if listen_task is not None and not listen_task.done():
                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass
            if not worker_task.done():
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
            while True:
                try:
                    delivery_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception as exc:
                logger.debug("[WSFanout] pubsub close: %s", exc)

        if listener_cancelled:
            break
        if loop_error is not None:
            if stop_event.is_set():
                break
            logger.error(
                "[WSFanout] Listener error: %s — reconnecting in %.1fs",
                loop_error, _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)

    logger.info("[WSFanout] Listener stopped")


async def dispatch_chat_fanout_raw(payload: str) -> None:
    """Replay one chat channel payload (used by PostgreSQL NOTIFY fallback)."""
    await _handle_chat_raw(payload)


def start_ws_fanout_listener(
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """
    Start the native asyncio pub/sub listener task (called once per worker process).

    The ``loop`` parameter is accepted for backward-compatibility but is no
    longer used; the task is scheduled on the running event loop via
    ``asyncio.create_task``.
    """
    _ = loop
    if not is_ws_fanout_enabled():
        logger.info("[WSFanout] Disabled (WS_REDIS_FANOUT_ENABLED or Redis)")
        return

    if _state.listener_task is not None and not _state.listener_task.done():
        return

    _state.stop_event = asyncio.Event()
    _state.listener_task = asyncio.create_task(
        _listener_loop_async(_state.stop_event),
        name="ws-redis-fanout",
    )
    logger.info("[WSFanout] Native async pub/sub listener task started")


def stop_ws_fanout_listener() -> None:
    """Signal the listener task to stop and cancel it (synchronous)."""
    if _state.stop_event is not None:
        _state.stop_event.set()
    if _state.listener_task is not None and not _state.listener_task.done():
        _state.listener_task.cancel()


async def await_ws_fanout_listener_stopped(timeout: float = 5.0) -> None:
    """
    Await the listener task to finish after ``stop_ws_fanout_listener`` has been
    called.  Swallows CancelledError and TimeoutError so shutdown always
    proceeds cleanly.
    """
    task = _state.listener_task
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass
    _state.listener_task = None
    _state.stop_event = None
