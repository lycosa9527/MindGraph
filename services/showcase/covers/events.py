"""Redis pub/sub events for Showcase teaching-design cover generation."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "showcase:cover"
HEARTBEAT_SECONDS = 25
# Must outlast Celery soft limit; closes SSE if no terminal event arrives.
COVER_SSE_MAX_SECONDS = 210
TERMINAL_EVENT_TYPES = frozenset({"cover_ready", "cover_fail"})


def cover_event_channel(post_id: str) -> str:
    """Redis channel for one post's cover lifecycle events."""
    return f"{CHANNEL_PREFIX}:{post_id}"


def build_cover_event_payload(
    event_type: str,
    *,
    post_id: str,
    thumbnail_url: Optional[str] = None,
    reason: Optional[str] = None,
) -> str:
    """JSON payload for cover SSE / pub/sub."""
    body: dict[str, Any] = {"type": event_type, "post_id": post_id}
    if thumbnail_url:
        body["thumbnail_url"] = thumbnail_url
    if reason:
        body["reason"] = reason[:200]
    return json.dumps(body, ensure_ascii=False)


def build_heartbeat_payload() -> str:
    """JSON payload for SSE keep-alive."""
    return json.dumps({"type": "heartbeat"}, ensure_ascii=False)


def decode_pubsub_data(raw: Any) -> Optional[str]:
    """Decode Redis pub/sub message data to UTF-8 text."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(raw, str):
        return raw
    return None


async def publish_showcase_cover_event(
    post_id: str,
    event_type: str,
    *,
    thumbnail_url: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Push a cover lifecycle event to SSE subscribers (async Redis)."""
    redis = get_async_redis()
    if redis is None:
        return
    payload = build_cover_event_payload(
        event_type,
        post_id=post_id,
        thumbnail_url=thumbnail_url,
        reason=reason,
    )
    try:
        await redis.publish(cover_event_channel(post_id), payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning(
            "[ShowcaseCover] publish failed post=%s type=%s: %s",
            post_id[:8],
            event_type,
            exc,
        )


def publish_showcase_cover_event_sync(
    post_id: str,
    event_type: str,
    *,
    thumbnail_url: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Push a cover lifecycle event from sync contexts (enqueue / Celery wrapper)."""
    if not is_redis_available():
        return
    redis = get_redis()
    if redis is None:
        return
    payload = build_cover_event_payload(
        event_type,
        post_id=post_id,
        thumbnail_url=thumbnail_url,
        reason=reason,
    )
    try:
        redis.publish(cover_event_channel(post_id), payload)
    except (RedisError, TypeError, ValueError, RuntimeError) as exc:
        logger.warning(
            "[ShowcaseCover] sync publish failed post=%s type=%s: %s",
            post_id[:8],
            event_type,
            exc,
        )
