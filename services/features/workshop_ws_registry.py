"""
Shared workshop WebSocket connection registry.

Holds process-local room/handle maps and per-room asyncio locks without
importing metrics or connection-handle implementation details (breaks the
``workshop_ws_connection_state`` ↔ ``ws_metrics`` import cycle).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

ACTIVE_CONNECTIONS: Dict[str, Dict[int, Any]] = {}
ACTIVE_EDITORS: Dict[str, Dict[str, Dict[int, str]]] = {}
_ROOM_REGISTRY_LOCKS: Dict[str, asyncio.Lock] = {}
_REGISTRY_LOCKS_GUARD = asyncio.Lock()


async def get_room_lock(code: str) -> asyncio.Lock:
    """Return per-room mutation lock (single Lock per ``code``, TOCTOU-safe)."""
    room_lock = _ROOM_REGISTRY_LOCKS.get(code)
    if room_lock is not None:
        return room_lock
    async with _REGISTRY_LOCKS_GUARD:
        return _ROOM_REGISTRY_LOCKS.setdefault(code, asyncio.Lock())


def clear_room_lock(code: str) -> None:
    """Drop cached lock when a room is removed from the registry."""
    _ROOM_REGISTRY_LOCKS.pop(code, None)
