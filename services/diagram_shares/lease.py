"""
Redis-backed FIFO edit lease for a shared diagram.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Optional

from services.diagram_shares.fanout import publish_share_close, publish_share_kick, publish_share_roster
from services.diagram_shares.queue import (
    LEASE_TTL_SECONDS,
    ShareTab,
    ShareTabStatus,
    decode_tabs,
    drop_user_tabs,
    encode_tabs,
    head_tab,
    join_tab,
    leave_tab,
    prune_tabs,
    tab_status,
    touch_tab,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_KEY_TTL_SECONDS = LEASE_TTL_SECONDS + 15
_MUTATE_ATTEMPTS = 8
_TabTransform = Callable[[list[ShareTab], float], list[ShareTab]]

# Compare-and-swap the whole queue so two writers cannot drop each other.
_CAS_LUA = """
local current = redis.call('GET', KEYS[1])
if current == false then current = '' end
if current ~= ARGV[1] then return 0 end
if ARGV[2] == '' then redis.call('DEL', KEYS[1]) return 1 end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""


def _queue_key(diagram_id: str) -> str:
    return f"diagram:share:queue:{diagram_id}"


def _decode(raw: Any) -> list[ShareTab]:
    if not raw:
        return []
    if isinstance(raw, str):
        return decode_tabs(raw)
    if isinstance(raw, (bytes, bytearray)):
        try:
            return decode_tabs(raw.decode("utf-8"))
        except UnicodeDecodeError:
            return []
    return []


async def _read(diagram_id: str) -> list[ShareTab]:
    redis = get_async_redis()
    if not redis:
        return []
    try:
        raw = await redis.get(_queue_key(diagram_id))
    except REDIS_ERRORS as exc:
        logger.warning("[DiagramShare] queue read failed diagram=%s: %s", diagram_id, exc)
        return []
    return prune_tabs(_decode(raw), time.time())


def _raw_text(raw: Any) -> str:
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8")
    return ""


async def _mutate(diagram_id: str, transform: _TabTransform) -> Optional[list[ShareTab]]:
    """Apply ``transform`` with compare-and-swap. None when Redis cannot store the queue."""
    redis = get_async_redis()
    if not redis:
        return None
    key = _queue_key(diagram_id)
    for _attempt in range(_MUTATE_ATTEMPTS):
        try:
            raw = await redis.get(key)
        except REDIS_ERRORS as exc:
            logger.warning("[DiagramShare] queue read failed diagram=%s: %s", diagram_id, exc)
            return None
        expected = _raw_text(raw)
        now = time.time()
        tabs = transform(prune_tabs(_decode(raw), now), now)
        new_value = encode_tabs(tabs) if tabs else ""
        try:
            swapped = await redis.eval(_CAS_LUA, 1, key, expected, new_value, str(_KEY_TTL_SECONDS))
        except REDIS_ERRORS as exc:
            logger.warning("[DiagramShare] queue write failed diagram=%s: %s", diagram_id, exc)
            return None
        if int(swapped or 0) == 1:
            return tabs
    logger.warning("[DiagramShare] queue update lost the race diagram=%s", diagram_id)
    return None


async def _announce(diagram_id: str, tabs: Optional[list[ShareTab]]) -> None:
    if tabs is None:
        return
    await publish_share_roster(diagram_id, tabs)


async def join_lease(
    diagram_id: str,
    user_id: int,
    tab_id: str,
    name: str,
    epoch: int,
    stream: int,
) -> Optional[ShareTabStatus]:
    """Add or refresh this tab and return its role. None when the queue cannot be stored."""

    def transform(tabs: list[ShareTab], now: float) -> list[ShareTab]:
        return join_tab(tabs, now, user_id, tab_id, name, epoch, stream)

    stored = await _mutate(diagram_id, transform)
    await _announce(diagram_id, stored)
    if stored is None:
        return None
    for tab in stored:
        owns = tab.user_id == user_id and tab.tab_id == tab_id
        if owns and tab.epoch == epoch and tab.stream == stream:
            return tab_status(stored, user_id, tab_id)
    absent: ShareTabStatus = {"role": "viewer", "editor_name": "", "viewer_count": 0, "present": False}
    return absent


async def leave_lease(
    diagram_id: str,
    user_id: int,
    tab_id: str,
    epoch: int,
    stream: Optional[int] = None,
) -> None:
    """Remove this SSE connection, or the whole page when ``stream`` is omitted."""

    def transform(tabs: list[ShareTab], now: float) -> list[ShareTab]:
        return leave_tab(tabs, now, user_id, tab_id, epoch, stream)

    await _announce(diagram_id, await _mutate(diagram_id, transform))


async def touch_lease(
    diagram_id: str,
    user_id: int,
    tab_id: str,
    epoch: int,
    stream: int,
) -> str:
    """Keep one live connection in the queue.

    ``replaced`` means a newer connection owns the tab. ``missing`` means this
    connection was pruned and may join again. ``unavailable`` means Redis is down.
    """

    kind = "missing"

    def transform(tabs: list[ShareTab], now: float) -> list[ShareTab]:
        nonlocal kind
        updated, kind = touch_tab(tabs, now, user_id, tab_id, epoch, stream)
        return updated

    stored = await _mutate(diagram_id, transform)
    if stored is None:
        return "unavailable"
    return kind


async def lease_head(diagram_id: str) -> ShareTab | None:
    """Tab that may write the diagram, if anyone has it open."""
    return head_tab(await _read(diagram_id))


async def drop_user_lease(diagram_id: str, user_id: int) -> None:
    """Drop a user from the queue after their share is revoked, and close their sockets."""

    def transform(tabs: list[ShareTab], now: float) -> list[ShareTab]:
        return drop_user_tabs(tabs, now, user_id)

    await _announce(diagram_id, await _mutate(diagram_id, transform))
    await publish_share_kick(diagram_id, user_id)


async def clear_lease(diagram_id: str) -> None:
    """Remove the queue and its sockets when the diagram itself is deleted."""

    def transform(_tabs: list[ShareTab], _now: float) -> list[ShareTab]:
        return []

    await _announce(diagram_id, await _mutate(diagram_id, transform))
    await publish_share_close(diagram_id)
