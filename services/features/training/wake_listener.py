"""One Redis pattern-subscribe per worker for 校本培训 watch snapshots.

O(workers), not O(users). Frames go out only when a session/step changes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from services.features.training.constants import WAKE_CHANNEL_PATTERN
from services.features.training.wake_fanout import (
    org_id_from_wake_channel,
    user_id_from_wake_channel,
)
from services.features.training.ws_manager import training_remote_ws_manager
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0
_PUBSUB_CLOSE_ERRORS = (*REDIS_ERRORS, AttributeError)


class TrainingRemoteWakeListenerRuntime:
    """Process-local listener task and stop event."""

    __slots__ = ("task", "stop_event")

    def __init__(self) -> None:
        """Create empty runtime slots."""
        self.task: Optional[asyncio.Task[None]] = None
        self.stop_event: Optional[asyncio.Event] = None


LISTENER_RUNTIME = TrainingRemoteWakeListenerRuntime()


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


async def dispatch_training_wake_message(channel: str, payload: str) -> int:
    """Deliver one wake to local training sockets. Returns send count."""
    if not payload:
        return 0
    user_id = user_id_from_wake_channel(channel)
    if user_id is not None:
        return await training_remote_ws_manager.send_to_user(user_id, payload)
    if org_id_from_wake_channel(channel) is not None:
        return await training_remote_ws_manager.send_to_all(payload)
    return 0


async def _listen_loop(stop_event: asyncio.Event) -> None:
    """Subscribe to ``training_remote:*:wake`` until stopped."""
    while not stop_event.is_set():
        client = get_async_redis()
        if client is None:
            await asyncio.sleep(_RECONNECT_DELAY)
            continue
        pubsub = client.pubsub()
        try:
            await pubsub.psubscribe(WAKE_CHANNEL_PATTERN)
            logger.debug("[TrainingRemote] subscribed %s", WAKE_CHANNEL_PATTERN)
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message is None or message.get("type") != "pmessage":
                    continue
                channel = _channel_text(message.get("channel"))
                payload = _payload_text(message.get("data"))
                try:
                    await dispatch_training_wake_message(channel, payload)
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.debug("[TrainingRemote] wake dispatch failed: %s", exc)
        except asyncio.CancelledError:
            break
        except REDIS_ERRORS as exc:
            if stop_event.is_set():
                break
            logger.warning(
                "[TrainingRemote] pubsub error: %s — reconnect in %.1fs",
                exc,
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.punsubscribe(WAKE_CHANNEL_PATTERN)
                await pubsub.aclose()
            except _PUBSUB_CLOSE_ERRORS as exc:
                logger.debug("[TrainingRemote] pubsub close: %s", exc)


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


def start_training_remote_wake_listener(_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Start the per-worker pattern subscriber (once)."""
    del _loop
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        return
    LISTENER_RUNTIME.stop_event = asyncio.Event()
    LISTENER_RUNTIME.task = asyncio.create_task(
        _supervisor(LISTENER_RUNTIME.stop_event),
        name="training-remote-wake-pubsub",
    )
    logger.debug("[TrainingRemote] wake listener started")


def stop_training_remote_wake_listener() -> None:
    """Signal the pattern subscriber to stop."""
    if LISTENER_RUNTIME.stop_event is not None:
        LISTENER_RUNTIME.stop_event.set()
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        LISTENER_RUNTIME.task.cancel()


async def await_training_remote_wake_listener_stopped(timeout: float = 5.0) -> None:
    """Await listener shutdown after ``stop_training_remote_wake_listener``."""
    task = LISTENER_RUNTIME.task
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError, *BACKGROUND_INFRA_ERRORS):
            pass
    LISTENER_RUNTIME.task = None
    LISTENER_RUNTIME.stop_event = None
