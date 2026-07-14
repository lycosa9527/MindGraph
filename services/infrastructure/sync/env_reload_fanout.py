"""
Cross-worker runtime .env reload via Redis pub/sub.

Admin ``reload-runtime`` updates the handling worker locally, then publishes so
sibling uvicorn workers reload ``.env`` into their process env + config cache.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from typing import Optional

from dotenv import load_dotenv
from redis.exceptions import RedisError

from config.settings import config
from services.infrastructure.utils.env_manager import EnvManager
from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 2.0
_PAYLOAD_VERSION = 1


class EnvReloadListenerRuntime:
    """Process-local listener task and stop event."""

    __slots__ = ("task", "stop_event")

    def __init__(self) -> None:
        """init."""
        self.task: Optional[asyncio.Task[None]] = None
        self.stop_event: Optional[asyncio.Event] = None


LISTENER_RUNTIME = EnvReloadListenerRuntime()


def env_reload_channel() -> str:
    """Redis channel for runtime env reload fan-out."""
    return redis_keys.ENV_RELOAD_CHANNEL


def get_env_reload_instance_id() -> str:
    """Per-process id so the publisher can skip its own fan-out message."""
    explicit = os.getenv("ENV_RELOAD_INSTANCE_ID", "").strip()
    if explicit:
        return explicit[:128]
    return f"{socket.gethostname()}:{os.getpid()}"[:128]


def reload_runtime_config_from_dotenv() -> None:
    """Reload ``.env`` into ``os.environ`` and clear the in-process config cache."""
    env_manager = EnvManager()
    env_path = env_manager.env_path.resolve()
    if env_path.is_file():
        load_dotenv(env_path, override=True)
    config.refresh_env_cache()


async def publish_env_reload_fanout(*, origin: Optional[str] = None) -> bool:
    """
    Notify other workers to reload ``.env``.

    Returns True when publish succeeded. Missing Redis is not fatal — the
    publishing worker already reloaded locally.
    """
    client = get_async_redis()
    if client is None:
        logger.warning("[EnvReload] Redis unavailable; skip fan-out publish")
        return False
    payload = {
        "v": _PAYLOAD_VERSION,
        "origin": origin or get_env_reload_instance_id(),
    }
    try:
        await client.publish(env_reload_channel(), json.dumps(payload, separators=(",", ":")))
        return True
    except (*BACKGROUND_INFRA_ERRORS, RedisError) as exc:
        logger.warning("[EnvReload] Fan-out publish failed: %s", exc)
        return False


def _origin_from_message(data: object) -> Optional[str]:
    """Parse origin from a pub/sub payload."""
    if isinstance(data, (bytes, bytearray)):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(data, str) or not data:
        return None
    try:
        parsed = json.loads(data)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    origin = parsed.get("origin")
    if isinstance(origin, str) and origin:
        return origin[:128]
    return None


async def handle_env_reload_message(data: object, local_instance: str) -> None:
    """Apply reload when the message came from another worker."""
    origin = _origin_from_message(data)
    if origin is None:
        return
    if origin == local_instance:
        return
    try:
        reload_runtime_config_from_dotenv()
        logger.warning("[EnvReload] Applied fan-out reload from origin=%s", origin)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[EnvReload] Fan-out reload failed: %s", exc, exc_info=True)


async def _listen_loop(stop_event: asyncio.Event, local_instance: str) -> None:
    """Subscribe and apply reload messages until stopped."""
    channel = env_reload_channel()
    while not stop_event.is_set():
        client = get_async_redis()
        if not client:
            await asyncio.sleep(_RECONNECT_DELAY)
            continue
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(channel)
            logger.info("[EnvReload] Subscribed to %s", channel)
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message is None or message.get("type") != "message":
                    continue
                await handle_env_reload_message(message.get("data"), local_instance)
        except asyncio.CancelledError:
            break
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            if stop_event.is_set():
                break
            logger.warning(
                "[EnvReload] pubsub error: %s — reconnect in %.1fs",
                exc,
                _RECONNECT_DELAY,
            )
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except (RedisError, OSError, RuntimeError, AttributeError) as exc:
                logger.debug("[EnvReload] pubsub close: %s", exc)

    logger.info("[EnvReload] Listener stopped")


async def _supervisor(stop_event: asyncio.Event) -> None:
    """Restart the listen loop until stop is requested."""
    local_instance = get_env_reload_instance_id()
    while not stop_event.is_set():
        try:
            await _listen_loop(stop_event, local_instance)
        except asyncio.CancelledError:
            break
        if stop_event.is_set():
            break
        await asyncio.sleep(_RECONNECT_DELAY)


def start_env_reload_listener(_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Start the env-reload subscriber once per worker."""
    _ = _loop
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        return
    LISTENER_RUNTIME.stop_event = asyncio.Event()
    LISTENER_RUNTIME.task = asyncio.create_task(
        _supervisor(LISTENER_RUNTIME.stop_event),
        name="env-reload-redis-pubsub",
    )
    logger.info("[EnvReload] Listener task started")


def stop_env_reload_listener() -> None:
    """Signal the env-reload listener to stop."""
    if LISTENER_RUNTIME.stop_event is not None:
        LISTENER_RUNTIME.stop_event.set()
    if LISTENER_RUNTIME.task is not None and not LISTENER_RUNTIME.task.done():
        LISTENER_RUNTIME.task.cancel()


async def await_env_reload_listener_stopped(timeout: float = 5.0) -> None:
    """Await listener shutdown after ``stop_env_reload_listener``."""
    task = LISTENER_RUNTIME.task
    if task is None or task.done():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
