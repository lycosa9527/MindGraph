"""Cross-worker collab WebSocket cap via Redis INCR (optional)."""

from __future__ import annotations

import logging
import os

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_KEY_TMPL = "mg:ws:collab:user:{uid}:open"


def redis_collab_socket_cap_enabled() -> bool:
    return os.getenv(
        "COLLAB_WS_REDIS_GLOBAL_SOCKET_CAP", "0",
    ) not in ("0", "false", "False", "")


def _effective_max_sockets_per_user() -> int:
    raw = os.environ.get("COLLAB_WS_MAX_PER_USER_GLOBAL", "20")
    default = 20
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


async def try_acquire_collab_redis_socket_slot(user_id: int) -> bool:
    """Return False when Redis count already exceeds configured cap."""
    if not redis_collab_socket_cap_enabled():
        return True
    client = get_async_redis()
    if not client:
        return True
    key = _KEY_TMPL.format(uid=int(user_id))
    ceiling = _effective_max_sockets_per_user()
    try:
        count = await client.incr(key)
        await client.expire(key, 86400)
        if count > ceiling:
            dec = await client.decr(key)
            if dec is not None and int(dec) < 0:
                await client.delete(key)
            logger.warning(
                "[WSCollabCap] Redis cap exceeded user_id=%s ceiling=%s",
                user_id, ceiling,
            )
            return False
        return True
    except RedisError as exc:
        logger.debug(
            "[WSCollabCap] incr failed user_id=%s: %s — allowing", user_id, exc,
        )
        return True


async def release_collab_redis_socket_slot(user_id: int) -> None:
    if not redis_collab_socket_cap_enabled():
        return
    client = get_async_redis()
    if not client:
        return
    key = _KEY_TMPL.format(uid=int(user_id))
    try:
        remainder = await client.decr(key)
        if remainder is not None and int(remainder) < 0:
            await client.delete(key)
    except RedisError as exc:
        logger.debug("[WSCollabCap] decr failed user_id=%s: %s", user_id, exc)
