"""One Redis pattern-subscribe per worker for 演讲模式 event frames.

O(workers), not O(users). Frames go out only when a click is queued or the HUD changes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from services.features.slides_remote.constants import WAKE_CHANNEL_PATTERN
from services.features.slides_remote.wake_fanout import user_id_from_wake_channel
from services.features.slides_remote.ws_manager import slides_remote_ws_manager
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0
_PUBSUB_CLOSE_ERRORS = (*REDIS_ERRORS, AttributeError)


class SlidesRemoteWakeListenerRuntime:
    """Process-local listener task and stop event."""

    __slots__ = ("task", "stop_event")

    def __init__(self) -> None:
        """Create empty runtime slots."""
        self.task: Optional[asyncio.Task[None]] = None
        self.stop_event: Optional[asyncio.Event] = None


LISTENER_RUNTIME = SlidesRemoteWakeListenerRuntime()


def _channel_text(raw: Any) -> str:
    """Decode a Redis pub/sub channel name."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    if isinstance(raw, str):
        return raw
    return ""


def _payload_text(raw: Any) -> str:
    """Decode a Redis pub/sub payload."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    if isinstance(raw, str):
        return raw
    return ""


async def dispatch_slides_wake_message(channel: str, payload: str) -> int:
    """Deliver one wake to local desktop sockets. Returns send count."""
    user_id = user_id_from_wake_channel(channel)
    if user_id is None or not payload:
        return 0
    return await slides_remote_ws_manager.send_to_user(user_id, payload)


async def _listen_loop(stop_event: asyncio.Event) -> None:
    """Subscribe to ``slide_remote:user:*:wake`` until stopped."""
    while not stop_event.is_set():
        client = get_async_redis()
        if client is None:
            await asyncio.sleep(_RECONNECT_DELAY)
            continue
        pubsub = client.pubsub()
        try:
            await pubsub.psubscribe(WAKE_CHANNEL_PATTERN)
            logger.debug("[SlideRemote] subscribed %s", WAKE_CHANNEL_PATTERN)
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message is None or message.get("type") != "pmessage":
                    continue
                channel = _channel_text(message.get("channel"))
                payload = _payload_text(message.get("data"))
                try:
                    await dispatch_slides_wake_message(channel, payload)
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.debug("[SlideRemote] wake dispatch failed: %s", exc)
        except asyncio.CancelledError:
            break
        except REDIS_ERRORS as exc:
            if stop_event.is_set():
                break
            logger.warning(
                "[SlideRemote] pubsub error: %s — reconnect in %.1fs",
                exc,
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.punsubscribe(WAKE_CHANNEL_PATTERN)
                await pubsub.aclose()
            except _PUBSUB_CLOSE_ERRORS as exc:
                logger.debug("[SlideRemote] pubsub close: %s", exc)


async def _supervisor(stop_event: asyncio.Event) -> None:
    """Restart the listen loop until shutdown."""
    while not stop_event.is_set():
        try:
            await _listen_loop(stop_event)
        except asyncio.CancelledError:
            break
        if stop_event.is_set():
            break
        await asyncio.sleep(_RECONNECT_DELAY)


def start_slides_remote_wake_listener(_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Start the per-worker pattern subscriber (once)."""
    del _loop
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        return
    LISTENER_RUNTIME.stop_event = asyncio.Event()
    LISTENER_RUNTIME.task = asyncio.create_task(
        _supervisor(LISTENER_RUNTIME.stop_event),
        name="slides-remote-wake-pubsub",
    )
    logger.debug("[SlideRemote] wake listener started")


def stop_slides_remote_wake_listener() -> None:
    """Signal the pattern subscriber to stop."""
    if LISTENER_RUNTIME.stop_event is not None:
        LISTENER_RUNTIME.stop_event.set()
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        LISTENER_RUNTIME.task.cancel()


async def await_slides_remote_wake_listener_stopped(timeout: float = 5.0) -> None:
    """Await listener shutdown after ``stop_slides_remote_wake_listener``."""
    task = LISTENER_RUNTIME.task
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError, *BACKGROUND_INFRA_ERRORS):
            pass
    LISTENER_RUNTIME.task = None
    LISTENER_RUNTIME.stop_event = None
