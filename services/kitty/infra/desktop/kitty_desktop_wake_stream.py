"""SSE stream: push ``mobile_active`` changes to desktop Kitty poll clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError

from config.settings import config
from models.domain.auth import User
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import build_kitty_desktop_wake_payload
from services.kitty.infra.desktop.kitty_mobile_active import read_kitty_mobile_active
from services.kitty.infra.guards.http_guards import kitty_http_allowed
from services.kitty.infra.redis.kitty_redis_keys import kitty_desktop_wake_channel
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 25
MAX_SSE_CONNECTIONS_PER_USER = 2

_active_connections: Dict[int, int] = {}


def _increment_connection(user_id: int) -> None:
    """Increment connection."""
    _active_connections[user_id] = _active_connections.get(user_id, 0) + 1


def _decrement_connection(user_id: int) -> None:
    """Decrement connection."""
    count = _active_connections.get(user_id, 0)
    if count <= 1:
        _active_connections.pop(user_id, None)
        return
    _active_connections[user_id] = count - 1


def _decode_pubsub_data(raw: Any) -> Optional[str]:
    """Decode pubsub data."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(raw, str):
        return raw
    return None


async def _iter_wake_events(user_id: int) -> AsyncIterator[str]:
    """Iter wake events."""
    yield ": stream_open\n\n"

    redis = get_async_redis()
    if redis is None:
        initial = await read_kitty_mobile_active(user_id)
        last_payload = build_kitty_desktop_wake_payload(initial)
        yield f"data: {last_payload}\n\n"
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            current = await read_kitty_mobile_active(user_id)
            payload = build_kitty_desktop_wake_payload(current)
            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        return

    channel = kitty_desktop_wake_channel(user_id)
    pubsub = redis.pubsub()
    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    async def _reader() -> None:
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                text = _decode_pubsub_data(message.get("data"))
                if text:
                    await queue.put(text)
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("[KittyDesktopWake] pubsub reader stopped user=%s: %s", user_id, exc)
        finally:
            await queue.put(None)

    await pubsub.subscribe(channel)
    initial = await read_kitty_mobile_active(user_id)
    last_payload = build_kitty_desktop_wake_payload(initial)
    yield f"data: {last_payload}\n\n"
    reader_task = asyncio.create_task(_reader(), name=f"kitty-desktop-wake-{user_id}")
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                current = await read_kitty_mobile_active(user_id)
                payload = build_kitty_desktop_wake_payload(current)
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue
            if item is None:
                break
            last_payload = item
            yield f"data: {item}\n\n"
    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("[KittyDesktopWake] reader join user=%s: %s", user_id, exc)
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except (RedisError, OSError, RuntimeError, AttributeError) as exc:
            logger.debug("[KittyDesktopWake] pubsub close user=%s: %s", user_id, exc)


async def kitty_desktop_wake_stream_response(current_user: User) -> StreamingResponse:
    """Return SSE ``StreamingResponse`` for desktop mobile-active wake events."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kitty Agent disabled")
    if not await kitty_http_allowed(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kitty Agent access denied")

    user_id = int(current_user.id)
    current_count = _active_connections.get(user_id, 0)
    if current_count >= MAX_SSE_CONNECTIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {MAX_SSE_CONNECTIONS_PER_USER} concurrent wake streams allowed",
        )

    _increment_connection(user_id)
    logger.debug(
        "[KittyDesktopWake] SSE started user=%s connections=%s",
        user_id,
        _active_connections.get(user_id, 0),
    )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in _iter_wake_events(user_id):
                yield chunk
        except asyncio.CancelledError:
            logger.debug("[KittyDesktopWake] SSE cancelled user=%s", user_id)
            raise
        except (RedisError, OSError, RuntimeError, ValueError) as exc:
            logger.warning("[KittyDesktopWake] SSE error user=%s: %s", user_id, exc)
            error_data = json.dumps({"type": "error", "error": "stream_unavailable"})
            yield f"data: {error_data}\n\n"
        finally:
            _decrement_connection(user_id)
            logger.debug(
                "[KittyDesktopWake] SSE closed user=%s remaining=%s",
                user_id,
                _active_connections.get(user_id, 0),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
