"""
Background Redis subscriber for WebSocket fan-out (native asyncio pub/sub).

Replaces the previous daemon-thread + run_coroutine_threadsafe bridge with a
supervised asyncio.Task using redis.asyncio native pub/sub.  Benefits:
- Zero polling latency (push-based, no 500 ms sleep)
- No OS thread; runs entirely on the event loop
- Automatic reconnection via supervisor loop

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from services.features.ws_redis_fanout_config import (
    CHAT_FANOUT_CHANNEL,
    ENVELOPE_VERSION,
    WORKSHOP_FANOUT_CHANNEL,
    is_ws_fanout_enabled,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from services.features.workshop_ws_fanout_delivery import (
    deliver_local_workshop_broadcast,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_fanout_chat_received,
    record_ws_fanout_workshop_received,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

# Reconnect delay after a pub/sub error (seconds)
_RECONNECT_DELAY = 2.0


class _FanoutListenerState:
    """Holds the asyncio.Task handle and stop signal (no module-level globals for pylint)."""

    __slots__ = ("listener_task", "stop_event")

    def __init__(self) -> None:
        self.listener_task: Optional[asyncio.Task] = None
        self.stop_event: Optional[asyncio.Event] = None


_state = _FanoutListenerState()


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


async def _handle_workshop_raw(payload: str) -> None:
    """Dispatch a workshop fan-out envelope to local WebSocket connections."""
    try:
        env = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("[WSFanout] Workshop fan-out: bad JSON")
        return
    if env.get("v") != ENVELOPE_VERSION:
        return
    if env.get("k") != "ws":
        return
    code = env.get("code")
    mode = env.get("mode")
    data_str = env.get("d")
    ex = env.get("ex")
    if not isinstance(code, str) or mode not in ("all", "others"):
        return
    if not isinstance(data_str, str):
        return
    exclude = ex if isinstance(ex, int) else None

    record_ws_fanout_workshop_received()
    await deliver_local_workshop_broadcast(code, mode, exclude, data_str)


async def _listener_loop_async(stop_event: asyncio.Event) -> None:
    """
    Native asyncio pub/sub listener.

    Subscribes to both fan-out channels and dispatches messages directly as
    coroutines on the event loop — no thread bridge, no polling delay.
    Reconnects automatically after errors until stop_event is set.
    """
    while not stop_event.is_set():
        client = get_async_redis()
        if not client:
            logger.warning("[WSFanout] No async Redis client; retrying in %.1fs", _RECONNECT_DELAY)
            await asyncio.sleep(_RECONNECT_DELAY)
            continue

        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(CHAT_FANOUT_CHANNEL, WORKSHOP_FANOUT_CHANNEL)
            logger.info("[WSFanout] Subscribed to %s, %s", CHAT_FANOUT_CHANNEL, WORKSHOP_FANOUT_CHANNEL)

            async for message in pubsub.listen():
                if stop_event.is_set():
                    break

                if message is None or message.get("type") != "message":
                    continue

                channel: Any = message.get("channel")
                data: Any = message.get("data")
                if not isinstance(data, str):
                    continue

                if channel == CHAT_FANOUT_CHANNEL:
                    await _handle_chat_raw(data)
                elif channel == WORKSHOP_FANOUT_CHANNEL:
                    await _handle_workshop_raw(data)

        except asyncio.CancelledError:
            break
        except Exception as exc:  # pylint: disable=broad-except
            if stop_event.is_set():
                break
            logger.error("[WSFanout] Listener error: %s — reconnecting in %.1fs", exc, _RECONNECT_DELAY)
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("[WSFanout] pubsub close: %s", exc)

    logger.info("[WSFanout] Listener stopped")


def start_ws_fanout_listener(loop: asyncio.AbstractEventLoop) -> None:  # pylint: disable=unused-argument
    """Start the native asyncio pub/sub listener task (called once per worker process).

    The ``loop`` parameter is accepted for backward-compatibility but is no
    longer used; the task is scheduled on the running event loop via
    ``asyncio.create_task``.
    """
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
    """Signal the listener task to stop and cancel it."""
    if _state.stop_event is not None:
        _state.stop_event.set()
    if _state.listener_task is not None and not _state.listener_task.done():
        _state.listener_task.cancel()
    _state.listener_task = None
    _state.stop_event = None
