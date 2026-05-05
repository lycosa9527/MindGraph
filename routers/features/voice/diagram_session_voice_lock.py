"""Per-diagram_session_id asyncio locks for Kitty voice session registry consistency."""

from __future__ import annotations

import asyncio
from typing import Dict

_locks: Dict[str, asyncio.Lock] = {}


def diagram_session_voice_lock(diagram_session_id: str) -> asyncio.Lock:
    """Serialize register/cleanup for a given WebSocket scope id (path segment)."""
    if diagram_session_id not in _locks:
        _locks[diagram_session_id] = asyncio.Lock()
    return _locks[diagram_session_id]
