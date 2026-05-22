"""
Background Redis subscriber for cross-worker Kitty session coordination.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from redis.exceptions import RedisError

from config.settings import config
from services.infrastructure.monitoring.ws_metrics import record_kitty_control_dispatch_exception
from services.kitty.infra.control.kitty_control_fanout import (
    get_kitty_control_instance_id,
    handle_kitty_control_message,
    kitty_control_channel,
)
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0


class KittyControlListenerRuntime:
    """Process-local listener task and stop event (avoids module-level mutable globals)."""

    __slots__ = ("task", "stop_event")

    def __init__(self) -> None:
        self.task: Optional[asyncio.Task[None]] = None
        self.stop_event: Optional[asyncio.Event] = None


LISTENER_RUNTIME = KittyControlListenerRuntime()


def is_kitty_control_listener_enabled() -> bool:
    """Run listener when Kitty WebSockets are enabled and async Redis exists."""
    if not getattr(config, "FEATURE_KITTY_WS_ENABLED", False):
        return False
    return get_async_redis() is not None


async def _listen_loop(stop_event: asyncio.Event, local_instance: str) -> None:
    ch = kitty_control_channel()
    while not stop_event.is_set():
        client = get_async_redis()
        if not client:
            await asyncio.sleep(_RECONNECT_DELAY)
            continue
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(ch)
            logger.info("[KittyControl] Subscribed to %s", ch)
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message is None or message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, (bytes, bytearray)):
                    try:
                        data = data.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                if not isinstance(data, str) or not data:
                    continue
                try:
                    await handle_kitty_control_message(data, local_instance)
                except Exception as exc:
                    record_kitty_control_dispatch_exception()
                    logger.warning(
                        "[KittyControl] dispatch error: %s",
                        exc,
                        exc_info=True,
                        extra=kitty_extra(
                            "control_dispatch_exception",
                            error_type=type(exc).__name__,
                        ),
                    )
        except asyncio.CancelledError:
            break
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            if stop_event.is_set():
                break
            logger.warning(
                "[KittyControl] pubsub error: %s — reconnect in %.1fs",
                exc,
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.unsubscribe(ch)
                await pubsub.aclose()
            except (RedisError, OSError, RuntimeError, AttributeError) as exc:
                logger.debug("[KittyControl] pubsub close: %s", exc)

    logger.info("[KittyControl] Listener stopped")


async def _supervisor(stop_event: asyncio.Event) -> None:
    local_instance = get_kitty_control_instance_id()
    while not stop_event.is_set():
        try:
            await _listen_loop(stop_event, local_instance)
        except asyncio.CancelledError:
            break
        if stop_event.is_set():
            break
        await asyncio.sleep(_RECONNECT_DELAY)


def start_kitty_control_listener(_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Start the Kitty control subscriber (once per worker)."""
    _ = _loop
    if not config.FEATURE_KITTY_WS_ENABLED:
        logger.info("[KittyControl] Listener not started (FEATURE_KITTY_WS_ENABLED is off)")
        return
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        return
    LISTENER_RUNTIME.stop_event = asyncio.Event()
    LISTENER_RUNTIME.task = asyncio.create_task(
        _supervisor(LISTENER_RUNTIME.stop_event),
        name="kitty-control-redis-pubsub",
    )
    logger.info("[KittyControl] Listener task started")


def stop_kitty_control_listener() -> None:
    """Signal the Kitty control listener to stop."""
    if LISTENER_RUNTIME.stop_event is not None:
        LISTENER_RUNTIME.stop_event.set()
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        LISTENER_RUNTIME.task.cancel()


async def await_kitty_control_listener_stopped(timeout: float = 5.0) -> None:
    """Await listener shutdown after ``stop_kitty_control_listener``."""
    task = LISTENER_RUNTIME.task
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass
    LISTENER_RUNTIME.task = None
    LISTENER_RUNTIME.stop_event = None
