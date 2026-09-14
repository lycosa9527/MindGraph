"""Redis pub/sub doorbell for chat-handoff pairing status.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

HANDOFF_WAKE_CHANNEL = "chat_handoff:{code}:wake"
SSE_KEEPALIVE_INTERVAL_S = 20.0
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"


def handoff_wake_channel(code: str) -> str:
    """Per-code Redis channel for pairing status."""
    return HANDOFF_WAKE_CHANNEL.format(code=code)


def format_handoff_sse(status: str, package_id: int, document_id: Optional[int]) -> str:
    """Encode one status frame."""
    payload = json.dumps(
        {
            "status": status,
            "package_id": package_id,
            "document_id": document_id,
        },
        separators=(",", ":"),
    )
    return f"event: status\ndata: {payload}\n\n"


async def publish_handoff_status(
    code: str,
    status: str,
    package_id: int,
    document_id: Optional[int] = None,
) -> None:
    """Wake the desktop EventSource when pairing status changes."""
    redis = get_async_redis()
    if redis is None:
        return
    envelope = json.dumps(
        {
            "status": status,
            "package_id": package_id,
            "document_id": document_id,
        },
        separators=(",", ":"),
    )
    try:
        await redis.publish(handoff_wake_channel(code), envelope)
    except REDIS_ERRORS as exc:
        logger.debug("[ChatHandoff] wake publish failed: %s", exc)


async def iter_handoff_events(code: str) -> AsyncIterator[str]:
    """Yield SSE keepalives plus published status frames for one code."""
    redis = get_async_redis()
    if redis is None:
        yield SSE_KEEPALIVE_COMMENT
        return
    channel = handoff_wake_channel(code)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_KEEPALIVE_INTERVAL_S,
            )
            if message is None:
                yield SSE_KEEPALIVE_COMMENT
                continue
            frame = frame_from_handoff_payload(message.get("data"))
            if frame:
                yield frame
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except REDIS_ERRORS as exc:
            logger.debug("[ChatHandoff] pubsub close failed: %s", exc)


def frame_from_handoff_payload(raw: Any) -> Optional[str]:
    """Turn a Redis payload into a status SSE frame."""
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
    status = str(parsed.get("status") or "")
    if not status:
        return None
    package_raw = parsed.get("package_id")
    if package_raw is None:
        return None
    try:
        package_id = int(package_raw)
    except (TypeError, ValueError):
        return None
    document_raw = parsed.get("document_id")
    document_id: Optional[int]
    if document_raw is None:
        document_id = None
    else:
        try:
            document_id = int(document_raw)
        except (TypeError, ValueError):
            document_id = None
    return format_handoff_sse(status, package_id, document_id)
