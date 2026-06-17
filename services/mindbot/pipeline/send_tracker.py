"""Redis-backed per-turn send state for MindBot (sending / error / complete)."""

from __future__ import annotations

import logging
import time

from services.mindbot.core.redis_keys import SEND_TRACKER_PREFIX, SEND_TRACKER_TTL
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from services.utils.typing_helpers import redis_hset_mapping

logger = logging.getLogger(__name__)


def _send_track_key(msg_id: str) -> str:
    """Send track key."""
    return f"{SEND_TRACKER_PREFIX}{msg_id}"


async def _hset_expire(
    msg_id: str,
    mapping: dict[str, str],
    pipeline_ctx: str,
) -> None:
    """Hset expire."""
    if not msg_id.strip():
        return
    key = _send_track_key(msg_id.strip())
    try:
        client = get_async_redis()
        async with client.pipeline(transaction=False) as pipe:
            pipe.hset(key, mapping=redis_hset_mapping(mapping))
            pipe.expire(key, SEND_TRACKER_TTL)
            await pipe.execute()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[MindBot] send_tracker_redis_error %s key=%s: %s",
            pipeline_ctx,
            key,
            exc,
        )


async def mark_sending(msg_id: str, pipeline_ctx: str) -> None:
    """Mark that outbound delivery for this DingTalk message has started."""
    ts = str(int(time.time()))
    await _hset_expire(
        msg_id,
        {"status": "sending", "ts": ts, "err_detail": ""},
        pipeline_ctx,
    )


async def mark_error(msg_id: str, err_detail: str, pipeline_ctx: str) -> None:
    """Mark a recoverable or terminal error for this turn."""
    ts = str(int(time.time()))
    detail = err_detail.strip() if err_detail else "unknown"
    if len(detail) > 512:
        detail = detail[:511] + "…"
    await _hset_expire(
        msg_id,
        {"status": "error", "ts": ts, "err_detail": detail},
        pipeline_ctx,
    )


async def mark_complete(msg_id: str, pipeline_ctx: str) -> None:
    """Mark that the user-visible reply for this turn finished successfully."""
    ts = str(int(time.time()))
    await _hset_expire(
        msg_id,
        {"status": "complete", "ts": ts, "err_detail": ""},
        pipeline_ctx,
    )
