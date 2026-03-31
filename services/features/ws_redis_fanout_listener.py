"""
Background Redis subscriber for WebSocket fan-out (one thread per worker).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
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
from services.redis.redis_client import get_redis

logger = logging.getLogger(__name__)


class _FanoutListenerState:
    """Holds subscriber thread handles (no module-level globals for pylint)."""

    __slots__ = ("listener_thread", "stop_event", "main_loop")

    def __init__(self) -> None:
        self.listener_thread: Optional[threading.Thread] = None
        self.stop_event: Optional[threading.Event] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None


_state = _FanoutListenerState()


def _schedule_delivery(coro: Any) -> None:
    loop = _state.main_loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError:
        logger.debug("[WSFanout] schedule_delivery: loop unavailable")


def _handle_chat_raw(payload: str) -> None:
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

        async def _run() -> None:
            await chat_ws_manager.deliver_local_channel_broadcast(
                cid,
                exclude,
                data_str,
            )

        _schedule_delivery(_run())
        return

    if kind == "u":
        uid = env.get("uid")
        if not isinstance(uid, int):
            return

        async def _run_u() -> None:
            await chat_ws_manager.deliver_local_user_message(uid, data_str)

        _schedule_delivery(_run_u())
        return

    if kind == "po":
        oid = env.get("oid")
        ex = env.get("ex")
        if not isinstance(oid, int):
            return
        exclude = ex if isinstance(ex, int) else None

        async def _run_po() -> None:
            await chat_ws_manager.deliver_local_presence_org(
                oid,
                exclude,
                data_str,
            )

        _schedule_delivery(_run_po())


def _handle_workshop_raw(payload: str) -> None:
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

    async def _run() -> None:
        await deliver_local_workshop_broadcast(
            code,
            mode,
            exclude,
            data_str,
        )

    _schedule_delivery(_run())


def _listener_loop() -> None:
    client = get_redis()
    if not client:
        return
    stop_ev = _state.stop_event
    if stop_ev is None:
        return
    pubsub = client.pubsub()
    try:
        pubsub.subscribe(CHAT_FANOUT_CHANNEL, WORKSHOP_FANOUT_CHANNEL)
        while not stop_ev.is_set():
            message = pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=0.5,
            )
            if message is None:
                continue
            if message["type"] != "message":
                continue
            channel = message.get("channel")
            data = message.get("data")
            if not isinstance(data, str):
                continue
            if channel == CHAT_FANOUT_CHANNEL:
                _handle_chat_raw(data)
            elif channel == WORKSHOP_FANOUT_CHANNEL:
                _handle_workshop_raw(data)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[WSFanout] Listener error: %s", exc, exc_info=True)
    finally:
        try:
            pubsub.close()
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Redis pubsub close failed: %s", exc)


def start_ws_fanout_listener(loop: asyncio.AbstractEventLoop) -> None:
    """Start the Redis subscriber thread (every worker process)."""
    if not is_ws_fanout_enabled():
        logger.info("[WSFanout] Disabled (WS_REDIS_FANOUT_ENABLED or Redis)")
        return

    if _state.listener_thread is not None and _state.listener_thread.is_alive():
        return

    _state.main_loop = loop
    _state.stop_event = threading.Event()
    _state.listener_thread = threading.Thread(
        target=_listener_loop,
        name="ws-redis-fanout",
        daemon=True,
    )
    _state.listener_thread.start()
    logger.info("[WSFanout] Redis pub/sub listener started")


def stop_ws_fanout_listener() -> None:
    """Signal the subscriber thread to stop."""
    if _state.stop_event is not None:
        _state.stop_event.set()
    if _state.listener_thread is not None:
        _state.listener_thread.join(timeout=2.0)
    _state.listener_thread = None
    _state.stop_event = None
    _state.main_loop = None
