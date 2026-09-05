"""
Redis pub/sub doorbell for training SSE clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

from services.features.training.constants import EVENTS_CHANNEL
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

SSE_KEEPALIVE_INTERVAL_S = 20.0
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"


def _channel(org_id: int) -> str:
    return EVENTS_CHANNEL.format(org_id=int(org_id))


def format_sse(event: str, data: dict[str, Any]) -> str:
    """Encode one SSE frame."""
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def publish_event(org_id: int, event: str, data: dict[str, Any]) -> None:
    """Publish a tiny event to org subscribers."""
    try:
        redis = get_async_redis()
        if redis is None:
            return
        envelope = json.dumps({"event": event, "data": data}, separators=(",", ":"))
        await redis.publish(_channel(org_id), envelope)
    except REDIS_ERRORS as exc:
        logger.debug("[Training] publish_event failed: %s", exc)


async def iter_org_events(org_id: int) -> AsyncIterator[str]:
    """Yield SSE text: keepalives plus published events for this org."""
    redis = get_async_redis()
    if redis is None:
        yield SSE_KEEPALIVE_COMMENT
        return
    pubsub = redis.pubsub()
    await pubsub.subscribe(_channel(org_id))
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_KEEPALIVE_INTERVAL_S,
            )
            if message is None:
                yield SSE_KEEPALIVE_COMMENT
                continue
            raw = message.get("data")
            frame = frame_from_payload(raw)
            if frame:
                yield frame
    finally:
        try:
            await pubsub.unsubscribe(_channel(org_id))
            await pubsub.aclose()
        except REDIS_ERRORS as exc:
            logger.debug("[Training] pubsub close failed: %s", exc)


def frame_from_payload(raw: Any) -> Optional[str]:
    """Turn a Redis pub/sub payload into an SSE frame, or None if invalid."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    event = str(parsed.get("event") or "seq")
    data = parsed.get("data")
    if not isinstance(data, dict):
        data = {}
    return format_sse(event, data)
