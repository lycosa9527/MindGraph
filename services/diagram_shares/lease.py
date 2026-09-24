"""
Redis-backed FIFO edit lease for a shared diagram.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from services.diagram_shares.queue import (
    LEASE_TTL_SECONDS,
    ShareTab,
    ShareTabStatus,
    drop_user_tabs,
    head_tab,
    join_tab,
    leave_tab,
    prune_tabs,
    tab_status,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_KEY_TTL_SECONDS = LEASE_TTL_SECONDS + 15


def _queue_key(diagram_id: str) -> str:
    return f"diagram:share:queue:{diagram_id}"


def _decode(raw: Any) -> list[ShareTab]:
    if not raw:
        return []
    text = raw if isinstance(raw, str) else raw.decode("utf-8")
    try:
        payload = json.loads(text)
    except JSON_PARSE_ERRORS:
        return []
    if not isinstance(payload, list):
        return []
    tabs: list[ShareTab] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            tabs.append(
                ShareTab(
                    user_id=int(item["user_id"]),
                    tab_id=str(item["tab_id"]),
                    name=str(item.get("name") or ""),
                    seen_at=float(item["seen_at"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tabs


def _encode(tabs: list[ShareTab]) -> str:
    return json.dumps(
        [
            {
                "user_id": tab.user_id,
                "tab_id": tab.tab_id,
                "name": tab.name,
                "seen_at": tab.seen_at,
            }
            for tab in tabs
        ]
    )


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


async def _write(diagram_id: str, tabs: list[ShareTab]) -> None:
    redis = get_async_redis()
    if not redis:
        return
    key = _queue_key(diagram_id)
    try:
        if not tabs:
            await redis.delete(key)
            return
        await redis.set(key, _encode(tabs), ex=_KEY_TTL_SECONDS)
    except REDIS_ERRORS as exc:
        logger.warning("[DiagramShare] queue write failed diagram=%s: %s", diagram_id, exc)


async def read_queue(diagram_id: str) -> list[ShareTab]:
    """Current live tabs, oldest first."""
    return await _read(diagram_id)


async def join_lease(diagram_id: str, user_id: int, tab_id: str, name: str) -> ShareTabStatus:
    """Add or refresh this tab and return its role."""
    now = time.time()
    tabs = join_tab(await _read(diagram_id), now, user_id, tab_id, name)
    await _write(diagram_id, tabs)
    return tab_status(tabs, user_id, tab_id)


async def leave_lease(diagram_id: str, user_id: int, tab_id: str) -> None:
    """Remove this tab so the next arrival can edit."""
    now = time.time()
    tabs = leave_tab(await _read(diagram_id), now, user_id, tab_id)
    await _write(diagram_id, tabs)


async def lease_head(diagram_id: str) -> ShareTab | None:
    """Tab that may write the diagram, if anyone has it open."""
    return head_tab(await _read(diagram_id))


async def drop_user_lease(diagram_id: str, user_id: int) -> None:
    """Drop a user from the queue after their share is revoked."""
    now = time.time()
    tabs = drop_user_tabs(await _read(diagram_id), now, user_id)
    await _write(diagram_id, tabs)


async def clear_lease(diagram_id: str) -> None:
    """Remove the queue when the diagram itself is deleted."""
    await _write(diagram_id, [])
