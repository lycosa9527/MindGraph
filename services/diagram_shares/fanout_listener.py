"""
One Redis subscriber per worker for shared-diagram spec snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from services.diagram_shares.fanout import SHARE_FANOUT_CHANNEL, parse_share_fanout_body
from services.diagram_shares.rooms import relay_share_spec
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0
_PUBSUB_CLOSE_ERRORS = (*REDIS_ERRORS, AttributeError)


class _ShareFanoutListenerRuntime:
    """Process-local listener task and stop event."""

    __slots__ = ("task", "stop_event")

    def __init__(self) -> None:
        """Create empty runtime slots."""
        self.task: Optional[asyncio.Task[None]] = None
        self.stop_event: Optional[asyncio.Event] = None


_RUNTIME = _ShareFanoutListenerRuntime()


def _text(raw: Any) -> str:
    """Decode a Redis pub/sub field."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    if isinstance(raw, str):
        return raw
    return ""


async def _listen_loop(stop_event: asyncio.Event) -> None:
    """Subscribe until shutdown or a Redis error."""
    while not stop_event.is_set():
        client = get_async_redis()
        if client is None:
            await asyncio.sleep(_RECONNECT_DELAY)
            continue
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(SHARE_FANOUT_CHANNEL)
            logger.debug("[DiagramShare] subscribed %s", SHARE_FANOUT_CHANNEL)
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message is None or message.get("type") != "message":
                    continue
                parsed = parse_share_fanout_body(_text(message.get("data")))
                if parsed is None:
                    continue
                diagram_id, from_tab, body = parsed
                try:
                    await relay_share_spec(diagram_id, from_tab, body)
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.debug("[DiagramShare] fan-out delivery failed: %s", exc)
        except asyncio.CancelledError:
            break
        except REDIS_ERRORS as exc:
            if stop_event.is_set():
                break
            logger.warning(
                "[DiagramShare] pubsub error: %s — reconnect in %.1fs",
                exc,
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.unsubscribe(SHARE_FANOUT_CHANNEL)
                await pubsub.aclose()
            except _PUBSUB_CLOSE_ERRORS as exc:
                logger.debug("[DiagramShare] pubsub close: %s", exc)


def start_diagram_share_fanout_listener(_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Start the per-worker subscriber when Redis fan-out is enabled."""
    del _loop
    if not is_ws_fanout_enabled():
        return
    if _RUNTIME.task is not None and not _RUNTIME.task.done():
        return
    _RUNTIME.stop_event = asyncio.Event()
    _RUNTIME.task = asyncio.create_task(
        _listen_loop(_RUNTIME.stop_event),
        name="diagram-share-fanout",
    )
    logger.debug("[DiagramShare] fan-out listener started")


def stop_diagram_share_fanout_listener() -> None:
    """Signal the subscriber to stop."""
    if _RUNTIME.stop_event is not None:
        _RUNTIME.stop_event.set()
    if _RUNTIME.task is not None and not _RUNTIME.task.done():
        _RUNTIME.task.cancel()


async def await_diagram_share_fanout_listener_stopped(timeout: float = 5.0) -> None:
    """Await listener shutdown after ``stop_diagram_share_fanout_listener``."""
    task = _RUNTIME.task
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError, *BACKGROUND_INFRA_ERRORS):
            pass
    _RUNTIME.task = None
    _RUNTIME.stop_event = None
