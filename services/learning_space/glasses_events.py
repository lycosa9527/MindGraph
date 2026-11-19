"""Wake one account when a course slide, a tap, a recording, or a canvas nudge changes.

The browser and the bound glasses each hold one server-sent stream on this
channel. A frame names what changed. The listener fetches that one thing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

CHANNEL = "mg:glasses:events:{user_id}"
KEEPALIVE_SECONDS = 20.0
KEEPALIVE = ": keepalive\n\n"


def glasses_events_channel(user_id: int) -> str:
    """Redis channel for one signed-in account."""
    return CHANNEL.format(user_id=int(user_id))


def _frame(event: str) -> str:
    payload = json.dumps({}, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def publish_glasses_event(user_id: int, event: str) -> None:
    """Tell the open course that a cue is waiting. A missed publish stays in the queue."""
    try:
        redis = get_async_redis()
        if redis is None:
            return
        await redis.publish(glasses_events_channel(user_id), event)
    except REDIS_ERRORS as exc:
        logger.debug("[Glasses] event publish failed: %s", exc)


async def iter_glasses_events(user_id: int) -> AsyncIterator[str]:
    """Yield keepalive comments and one frame per published cue."""
    redis = get_async_redis()
    if redis is None:
        yield KEEPALIVE
        return
    channel = glasses_events_channel(user_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=KEEPALIVE_SECONDS)
            if message is None:
                yield KEEPALIVE
                continue
            raw = message.get("data")
            event = _event_name(raw)
            if event:
                yield _frame(event)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except REDIS_ERRORS as exc:
            logger.debug("[Glasses] event stream close failed: %s", exc)


def _event_name(raw: Any) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if raw in {"play", "remote", "follow", "voice"}:
        return str(raw)
    return ""
