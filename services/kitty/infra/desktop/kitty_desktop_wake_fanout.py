"""Redis pub/sub wake events for desktop Kitty SSE (mobile connect / disconnect)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import kitty_desktop_wake_channel
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_EVENT_TYPE = "mobile_active"


def build_kitty_desktop_wake_payload(mobile_state: Dict[str, Any]) -> str:
    """JSON SSE payload for a ``mobile_active`` snapshot."""
    body: Dict[str, Any] = {"type": _EVENT_TYPE}
    active = mobile_state.get("active")
    body["active"] = active is True
    scopes = mobile_state.get("scopes")
    if isinstance(scopes, list):
        body["scopes"] = [str(item) for item in scopes if isinstance(item, str)]
    else:
        body["scopes"] = []
    primary = mobile_state.get("primary_scope")
    body["primary_scope"] = primary if isinstance(primary, str) and primary.strip() else None
    return json.dumps(body, ensure_ascii=False)


async def publish_kitty_desktop_wake(user_id: int, mobile_state: Dict[str, Any]) -> None:
    """Notify desktop SSE listeners that ``mobile_active`` changed for ``user_id``."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    payload = build_kitty_desktop_wake_payload(mobile_state)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] publish failed user=%s: %s",
            user_id,
            exc,
        )


async def publish_kitty_desktop_action_pending(user_id: int) -> None:
    """Wake desktop tabs to drain an explicit mobile REST enqueue (library pick, etc.)."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    payload = json.dumps({"type": "desktop_action_pending"}, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] action_pending publish failed user=%s: %s",
            user_id,
            exc,
        )
