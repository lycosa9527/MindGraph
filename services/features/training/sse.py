"""
Redis pub/sub doorbell for training SSE clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator, Optional

from services.features.training.connection_lease import (
    refresh_org_connection_lease,
    refresh_user_connection_lease,
)
from services.features.training.constants import EVENTS_CHANNEL, STATE_ENDED
from services.features.training.wake_fanout import training_user_wake_channel
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

SSE_KEEPALIVE_INTERVAL_S = 20.0
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"

KeepaliveFn = Callable[[], Awaitable[None]]


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


async def iter_org_events(org_id: int, viewer_user_id: Optional[int] = None) -> AsyncIterator[str]:
    """Yield SSE text: keepalives plus published events for this org."""

    async def _on_keepalive() -> None:
        if viewer_user_id is None:
            return
        await refresh_org_connection_lease(org_id, viewer_user_id)

    async for chunk in _iter_pubsub(_channel(org_id), frame_from_payload, _on_keepalive):
        yield chunk


async def iter_user_wake_events(user_id: int) -> AsyncIterator[str]:
    """Yield SSE doorbells from the instructor user-wake channel (no org yet)."""

    async def _on_keepalive() -> None:
        await refresh_user_connection_lease(user_id)

    async for chunk in _iter_pubsub(
        training_user_wake_channel(user_id),
        frame_from_user_wake,
        _on_keepalive,
    ):
        yield chunk


async def _iter_pubsub(
    channel: str,
    frame_fn: Callable[[Any], Optional[str]],
    on_keepalive: KeepaliveFn,
) -> AsyncIterator[str]:
    """Subscribe to one Redis channel and yield SSE frames plus keepalives."""
    redis = get_async_redis()
    if redis is None:
        yield SSE_KEEPALIVE_COMMENT
        return
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_KEEPALIVE_INTERVAL_S,
            )
            if message is None:
                await on_keepalive()
                yield SSE_KEEPALIVE_COMMENT
                continue
            raw = message.get("data")
            frame = frame_fn(raw)
            if frame:
                yield frame
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except REDIS_ERRORS as exc:
            logger.debug("[Training] pubsub close failed: %s", exc)


def frame_from_payload(raw: Any) -> Optional[str]:
    """Turn a Redis pub/sub payload into an SSE frame, or None if invalid."""
    parsed = _parse_json_object(raw)
    if parsed is None:
        return None
    event = str(parsed.get("event") or "seq")
    data = parsed.get("data")
    if not isinstance(data, dict):
        data = {}
    return format_sse(event, data)


def frame_from_user_wake(raw: Any) -> Optional[str]:
    """Turn a training-remote snapshot wake into a tiny SSE doorbell."""
    parsed = _parse_json_object(raw)
    if parsed is None:
        return None
    data: dict[str, Any] = {}
    seq = parsed.get("seq")
    if seq is not None:
        try:
            data["seq"] = int(seq)
        except (TypeError, ValueError):
            pass
    org_id = parsed.get("org_id")
    if org_id is not None:
        try:
            data["org_id"] = int(org_id)
        except (TypeError, ValueError):
            pass
    event = "ended" if str(parsed.get("state") or "") == STATE_ENDED else "seq"
    return format_sse(event, data)


def _parse_json_object(raw: Any) -> Optional[dict[str, Any]]:
    """Decode a Redis payload that must be a JSON object."""
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
    return parsed
