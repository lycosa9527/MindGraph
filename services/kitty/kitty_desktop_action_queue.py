"""FIFO queue for Kitty-initiated **desktop navigation** (cross-tab; mobile Kitty → desktop SPA).

Only ``kind: open_canvas`` payloads are accepted (diagram slug + optional topic seeds). This queue
must **not** carry full diagram specs or hub patches — avoid duplicating diagram mutation alongside
``apply_diagram_spec_mutation`` / ``live_spec``; use hub + Redis live spec for authoritative canvas state.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.kitty.kitty_diagram_vocabulary import coerce_open_desktop_payload_diagram_slug
from services.kitty.kitty_redis_keys import kitty_desktop_action_queue_key
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_KITTY_DESKTOP_ACTION_QUEUE_TTL = 3600
_KITTY_DESKTOP_ACTION_QUEUE_MAX_LEN = 32


async def enqueue_kitty_desktop_action(user_id: int, payload: Dict[str, Any]) -> bool:
    """
    Push one JSON payload for the authenticated user; desktop SPA pops with long-poll/interval GET.

    Returns False if Redis is unavailable or payload is rejected.
    """
    kind = payload.get("kind")
    if kind != "open_canvas":
        logger.warning("[KittyDesktopActions] unsupported kind=%s user=%s", kind, user_id)
        return False
    slug = coerce_open_desktop_payload_diagram_slug(payload)
    if slug is None:
        logger.warning("[KittyDesktopActions] invalid diagram_type user=%s payload=%s", user_id, payload)
        return False

    def _take_str(key: str, max_len: int) -> None:
        raw = payload.get(key)
        if not isinstance(raw, str):
            payload.pop(key, None)
            return
        cut = raw.strip()
        if not cut:
            payload.pop(key, None)
            return
        payload[key] = cut[:max_len]

    _take_str("topic", 512)
    _take_str("left", 256)
    _take_str("right", 256)

    redis = get_async_redis()
    if redis is None:
        return False
    key = kitty_desktop_action_queue_key(user_id)
    try:
        line = json.dumps(payload, ensure_ascii=False)
        await redis.rpush(key, line)
        await redis.expire(key, _KITTY_DESKTOP_ACTION_QUEUE_TTL)
        await redis.ltrim(key, -_KITTY_DESKTOP_ACTION_QUEUE_MAX_LEN, -1)
        return True
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyDesktopActions] enqueue failed user=%s: %s", user_id, exc)
        return False


async def pop_kitty_desktop_action(user_id: int) -> Optional[Dict[str, Any]]:
    """Atomically pop the oldest queued action for this user."""
    redis = get_async_redis()
    if redis is None:
        return None
    key = kitty_desktop_action_queue_key(user_id)
    try:
        raw = await redis.lpop(key)
        if not raw:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyDesktopActions] pop failed user=%s: %s", user_id, exc)
        return None
