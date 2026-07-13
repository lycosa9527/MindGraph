"""Redis lease: desktop canvas-owner Kitty is live for user+scope.

Used so verified edits can fail closed with ``no_owner`` instead of waiting for
``ack_timeout`` when no desktop tab holds the canvas-owner WebSocket (including
cross-worker cases where ``find_canvas_owner_websocket`` is process-local).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_canvas_owner_presence_key,
    kitty_redis_ttl_seconds,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


def _normalize(user_id: int, scope: str) -> Optional[tuple[int, str]]:
    """Return ``(user_id, scope)`` or None when inputs are unusable."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    normalized = normalize_kitty_diagram_session_id(scope)
    if normalized is None:
        return None
    return uid, normalized


async def mark_kitty_canvas_owner_present(user_id: int, scope: str) -> None:
    """Record that a desktop canvas-owner WS is live for ``user_id`` + ``scope``."""
    pair = _normalize(user_id, scope)
    if pair is None:
        return
    uid, norm_scope = pair
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_canvas_owner_presence_key(uid, norm_scope)
    try:
        await redis.set(key, "1", ex=kitty_redis_ttl_seconds())
    except RedisError as exc:
        logger.debug(
            "[KittyCanvasOwnerPresence] mark failed user=%s scope=%s: %s",
            uid,
            norm_scope[:12],
            exc,
        )


async def clear_kitty_canvas_owner_present(user_id: int, scope: str) -> None:
    """Clear desktop canvas-owner presence for ``user_id`` + ``scope``."""
    pair = _normalize(user_id, scope)
    if pair is None:
        return
    uid, norm_scope = pair
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_canvas_owner_presence_key(uid, norm_scope)
    try:
        await redis.delete(key)
    except RedisError as exc:
        logger.debug(
            "[KittyCanvasOwnerPresence] clear failed user=%s scope=%s: %s",
            uid,
            norm_scope[:12],
            exc,
        )


async def has_kitty_canvas_owner_present(user_id: int, scope: str) -> bool:
    """True when Redis reports a live desktop canvas-owner for this user+scope."""
    pair = _normalize(user_id, scope)
    if pair is None:
        return False
    uid, norm_scope = pair
    redis = get_async_redis()
    if redis is None:
        return False
    key = kitty_canvas_owner_presence_key(uid, norm_scope)
    try:
        raw = await redis.get(key)
        return raw is not None
    except RedisError as exc:
        logger.debug(
            "[KittyCanvasOwnerPresence] get failed user=%s scope=%s: %s",
            uid,
            norm_scope[:12],
            exc,
        )
        return False
