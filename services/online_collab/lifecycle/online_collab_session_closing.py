"""Redis flag for workshop stop / idle-kick flush windows (suppress live merges)."""

from __future__ import annotations

import logging
import os
from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.online_collab_redis_keys import session_closing_key

logger = logging.getLogger(__name__)

_CLOSING_TTL_FALLBACK_SEC = 120


def workshop_session_closing_ttl_seconds() -> int:
    raw = os.environ.get("WORKSHOP_SESSION_CLOSING_TTL_SEC")
    if raw is None:
        return _CLOSING_TTL_FALLBACK_SEC
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return _CLOSING_TTL_FALLBACK_SEC
    return parsed if parsed > 0 else _CLOSING_TTL_FALLBACK_SEC


async def mark_workshop_session_closing(norm_code_upper: str) -> None:
    """Set transient marker while DB flush / teardown runs."""
    client = get_async_redis()
    if not client:
        return
    key = session_closing_key(norm_code_upper.strip().upper())
    try:
        await client.set(key, "1", ex=workshop_session_closing_ttl_seconds())
    except RedisError as exc:
        logger.debug("[OnlineCollab] mark closing failed code=%s: %s", norm_code_upper, exc)


async def unmark_workshop_session_closing(norm_code_upper: str) -> None:
    """Delete the transient closing marker (called when flush/stop fails)."""
    client = get_async_redis()
    if not client:
        return
    key = session_closing_key(norm_code_upper.strip().upper())
    try:
        await client.delete(key)
    except RedisError as exc:
        logger.debug(
            "[OnlineCollab] unmark closing failed code=%s: %s", norm_code_upper, exc,
        )


async def workshop_session_is_closing(norm_code_upper: str) -> bool:
    """True when this room must reject collaborative spec merges."""
    client = get_async_redis()
    if not client:
        return False
    key = session_closing_key(norm_code_upper.strip().upper())
    try:
        raw = await client.get(key)
    except RedisError as exc:
        logger.debug("[OnlineCollab] closing probe failed code=%s: %s", norm_code_upper, exc)
        return False
    return raw is not None and raw not in (b"", "", b"0", "0")
