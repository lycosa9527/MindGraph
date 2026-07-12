"""FIFO queue for Kitty-initiated **desktop navigation** (cross-tab; mobile Kitty → desktop SPA).

Accepted payload kinds:

- ``open_canvas`` — diagram slug + optional topic seeds (new blank canvas).
- ``open_library_diagram`` — saved MindGraph library id (+ optional title for UX).

This queue must **not** carry full diagram specs or hub patches — avoid duplicating diagram
mutation alongside ``apply_diagram_spec_mutation`` / ``live_spec``; use hub + Redis live spec
for authoritative canvas state.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Dict, Optional, cast

from redis.exceptions import RedisError

from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import coerce_open_desktop_payload_diagram_slug
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_desktop_action_explicit_key,
    kitty_desktop_action_queue_key,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.redis_async_client import get_async_redis, get_async_redis_socket_timeout

logger = logging.getLogger(__name__)

_KITTY_DESKTOP_ACTION_QUEUE_TTL = 3600
_KITTY_DESKTOP_ACTION_QUEUE_MAX_LEN = 32
_KITTY_DESKTOP_ACTION_BLPOP_MAX_SEC = 30
_KITTY_DESKTOP_ACTION_EXPLICIT_TTL = 120
_KITTY_DESKTOP_ACTION_MAX_AGE_SEC = 120


def _blpop_chunk_timeout_sec(wait_remaining: float) -> int:
    """BLPOP block must stay under Redis ``socket_timeout`` or the client raises.

    Shared async pool defaults to ``REDIS_SOCKET_TIMEOUT=5``. A single BLPOP with
    ``timeout=25`` then retries (~15s) and logs ``Timeout reading from localhost:6379``.
    Chunk under the socket timeout and loop for the caller's ``wait_sec``.
    """
    socket_timeout = get_async_redis_socket_timeout()
    # Leave 1s headroom so the server returns before the client socket deadline.
    max_chunk = max(1, min(_KITTY_DESKTOP_ACTION_BLPOP_MAX_SEC, int(socket_timeout) - 1))
    return max(1, min(max_chunk, int(max(1.0, wait_remaining))))


def _decode_action_raw(raw: Any) -> Optional[Dict[str, Any]]:
    """Decode action raw."""
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _take_optional_str(payload: Dict[str, Any], key: str, max_len: int) -> None:
    """Take optional str."""
    raw = payload.get(key)
    if not isinstance(raw, str):
        payload.pop(key, None)
        return
    cut = raw.strip()
    if not cut:
        payload.pop(key, None)
        return
    payload[key] = cut[:max_len]


def _normalize_open_canvas_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize open canvas payload."""
    slug = coerce_open_desktop_payload_diagram_slug(payload)
    if slug is None:
        return None
    payload["diagram_type"] = slug
    _take_optional_str(payload, "topic", 512)
    _take_optional_str(payload, "left", 256)
    _take_optional_str(payload, "right", 256)
    return payload


def _normalize_open_library_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize open library payload."""
    raw_id = payload.get("diagram_library_id")
    if not isinstance(raw_id, str):
        return None
    normalized = normalize_kitty_diagram_session_id(raw_id)
    if normalized is None:
        return None
    payload["diagram_library_id"] = normalized
    _take_optional_str(payload, "title", 256)
    return payload


def _action_is_fresh(payload: Dict[str, Any], *, max_age_sec: int) -> bool:
    """Reject stale queue items so opening Kitty does not replay old navigation."""
    raw_ts = payload.get("enqueued_at")
    if not isinstance(raw_ts, (int, float)):
        return False
    return (time.time() - float(raw_ts)) <= max_age_sec


async def mark_kitty_desktop_action_explicit_drain(user_id: int) -> None:
    """Allow one inactive instant pop after mobile REST enqueue."""
    redis = get_async_redis()
    if redis is None:
        return
    key = kitty_desktop_action_explicit_key(user_id)
    try:
        await cast(Awaitable[Any], redis.set(key, "1", ex=_KITTY_DESKTOP_ACTION_EXPLICIT_TTL))
    except RedisError as exc:
        logger.debug(
            "[KittyDesktopActions] explicit drain mark failed user=%s: %s",
            user_id,
            exc,
        )


async def consume_kitty_desktop_action_explicit_drain(user_id: int) -> bool:
    """Return True when inactive instant pop is allowed; clears the one-shot flag."""
    redis = get_async_redis()
    if redis is None:
        return False
    key = kitty_desktop_action_explicit_key(user_id)
    try:
        deleted = await cast(Awaitable[int], redis.delete(key))
        return int(deleted or 0) > 0
    except RedisError as exc:
        logger.debug(
            "[KittyDesktopActions] explicit drain consume failed user=%s: %s",
            user_id,
            exc,
        )
        return False


async def _push_desktop_action(user_id: int, payload: Dict[str, Any]) -> bool:
    """Push desktop action."""
    redis = get_async_redis()
    if redis is None:
        return False
    key = kitty_desktop_action_queue_key(user_id)
    try:
        stamped = dict(payload)
        stamped["enqueued_at"] = int(time.time())
        line = json.dumps(stamped, ensure_ascii=False)
        await cast(Awaitable[int], redis.rpush(key, line))
        await cast(Awaitable[bool], redis.expire(key, _KITTY_DESKTOP_ACTION_QUEUE_TTL))
        await cast(Awaitable[str], redis.ltrim(key, -_KITTY_DESKTOP_ACTION_QUEUE_MAX_LEN, -1))
        kind = str(payload.get("kind") or "")
        kitty_wf_log(
            "desktop_queue_enqueue",
            kind,
            user_id=user_id,
            action=kind or None,
        )
        return True
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyDesktopActions] enqueue failed user=%s: %s", user_id, exc)
        return False


async def enqueue_kitty_desktop_action(user_id: int, payload: Dict[str, Any]) -> bool:
    """
    Push one JSON payload for the authenticated user; desktop SPA pops with long-poll GET.

    Returns False if Redis is unavailable or payload is rejected.
    """
    kind = payload.get("kind")
    if kind == "open_canvas":
        normalized = _normalize_open_canvas_payload(dict(payload))
        if normalized is None:
            logger.warning(
                "[KittyDesktopActions] invalid open_canvas user=%s payload=%s",
                user_id,
                payload,
            )
            return False
        return await _push_desktop_action(user_id, normalized)

    if kind == "open_library_diagram":
        normalized = _normalize_open_library_payload(dict(payload))
        if normalized is None:
            logger.warning(
                "[KittyDesktopActions] invalid open_library_diagram user=%s payload=%s",
                user_id,
                payload,
            )
            return False
        return await _push_desktop_action(user_id, normalized)

    logger.warning("[KittyDesktopActions] unsupported kind=%s user=%s", kind, user_id)
    return False


async def pop_kitty_desktop_action(user_id: int) -> Optional[Dict[str, Any]]:
    """Atomically pop the oldest queued action for this user (instant LPOP)."""
    return await pop_kitty_desktop_action_wait(user_id, wait_sec=0)


async def pop_kitty_desktop_action_wait(
    user_id: int,
    wait_sec: float = 0,
    *,
    discard_stale: bool = False,
    max_age_sec: int = _KITTY_DESKTOP_ACTION_MAX_AGE_SEC,
) -> Optional[Dict[str, Any]]:
    """
    Pop the oldest queued action; optionally block up to ``wait_sec`` (Redis BLPOP).

    ``wait_sec <= 0`` uses instant LPOP. Otherwise blocks up to 30s for the next item.
    When ``discard_stale`` is true, skip items older than ``max_age_sec``.
    """
    redis = get_async_redis()
    if redis is None:
        return None
    key = kitty_desktop_action_queue_key(user_id)
    try:
        if wait_sec <= 0:
            while True:
                raw = await cast(Awaitable[Any], redis.lpop(key))
                data = _decode_action_raw(raw)
                if data is None:
                    return None
                if not discard_stale or _action_is_fresh(data, max_age_sec=max_age_sec):
                    kind = str(data.get("kind") or "")
                    kitty_wf_log(
                        "desktop_queue_pop",
                        kind,
                        user_id=user_id,
                        action=kind or None,
                    )
                    return data
                logger.debug(
                    "[KittyDesktopActions] discarded stale action user=%s kind=%s",
                    user_id,
                    data.get("kind"),
                )
        deadline = time.monotonic() + min(float(wait_sec), float(_KITTY_DESKTOP_ACTION_BLPOP_MAX_SEC))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            block = _blpop_chunk_timeout_sec(remaining)
            result = await cast(Awaitable[Any], redis.blpop(key, timeout=block))
            if not result:
                continue
            if isinstance(result, (list, tuple)) and len(result) >= 2:
                raw = result[1]
            else:
                raw = result
            data = _decode_action_raw(raw)
            if data is None:
                return None
            if not discard_stale or _action_is_fresh(data, max_age_sec=max_age_sec):
                kind = str(data.get("kind") or "")
                kitty_wf_log(
                    "desktop_queue_pop",
                    kind,
                    user_id=user_id,
                    action=kind or None,
                )
                return data
            logger.debug(
                "[KittyDesktopActions] discarded stale action user=%s kind=%s",
                user_id,
                data.get("kind"),
            )
            return await pop_kitty_desktop_action_wait(
                user_id,
                0,
                discard_stale=discard_stale,
                max_age_sec=max_age_sec,
            )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug("[KittyDesktopActions] pop failed user=%s: %s", user_id, exc)
        return None
