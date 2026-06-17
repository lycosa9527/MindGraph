"""Redis-backed hint: last library diagram the user focused on desktop MindGraph.

**Scope (navigation pairing only):** stores which **library / diagram session id** desktop had open so
mobile Kitty can align ``/ws/kitty/{scope}`` with the PC. This is **not** a channel for diagram
content or ``diagram_data`` — canvas truth for edits lives in **Agent Hub** /
``kitty:live_spec`` (see ``apply_diagram_spec_mutation`` and desktop ``live_context`` poll).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import kitty_desktop_focus_key, kitty_redis_ttl_seconds
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


async def set_kitty_desktop_focus_diagram(user_id: int, diagram_library_id: Optional[str]) -> None:
    """Set or clear the user's desktop MindGraph library focus (for mobile Kitty pairing)."""
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_desktop_focus_key(user_id)
    ttl = kitty_redis_ttl_seconds()
    if not diagram_library_id or not str(diagram_library_id).strip():
        try:
            await redis.delete(key)
        except RedisError as exc:
            logger.warning("[KittyDesktopFocus] delete failed user=%s: %s", user_id, exc)
        return

    normalized = normalize_kitty_diagram_session_id(diagram_library_id)
    if normalized is None:
        try:
            await redis.delete(key)
        except RedisError as exc:
            logger.warning("[KittyDesktopFocus] delete invalid id user=%s: %s", user_id, exc)
        return

    payload: Dict[str, Any] = {
        "diagram_library_id": normalized,
        "updated_at": int(time.time()),
    }
    try:
        text = json.dumps(payload, ensure_ascii=False)
        await redis.set(key, text, ex=ttl)
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyDesktopFocus] set failed user=%s: %s", user_id, exc)


async def get_kitty_desktop_focus_diagram(user_id: int) -> Tuple[Optional[str], Optional[int]]:
    """Return ``(diagram_library_id, updated_at_epoch)`` from Redis, or ``(None, None)``."""
    redis = get_async_redis()
    if redis is None:
        return None, None
    key = kitty_desktop_focus_key(user_id)
    try:
        raw = await redis.get(key)
        if not raw:
            return None, None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        if not isinstance(data, dict):
            return None, None
        lib = data.get("diagram_library_id")
        if not isinstance(lib, str) or not lib.strip():
            return None, None
        normalized = normalize_kitty_diagram_session_id(lib)
        if normalized is None:
            return None, None
        updated = data.get("updated_at")
        if isinstance(updated, bool) or updated is None:
            ts: Optional[int] = None
        elif isinstance(updated, (int, float)):
            ts = int(updated)
        else:
            ts = None
        return normalized, ts
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[KittyDesktopFocus] read failed user=%s: %s", user_id, exc)
        return None, None
