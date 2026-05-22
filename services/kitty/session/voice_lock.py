"""Per-diagram_session_id asyncio locks for Kitty voice session registry consistency."""

from __future__ import annotations

import asyncio
from typing import Dict

from services.kitty.session.runtime_state import active_websockets, voice_sessions

_locks: Dict[str, asyncio.Lock] = {}


def diagram_session_voice_lock(diagram_session_id: str) -> asyncio.Lock:
    """Serialize register/cleanup for a given WebSocket scope id (path segment)."""
    if diagram_session_id not in _locks:
        _locks[diagram_session_id] = asyncio.Lock()
    return _locks[diagram_session_id]


def release_diagram_session_voice_lock_if_idle(diagram_session_id: str) -> None:
    """Drop the lock entry when no local sockets or voice sessions remain for the scope."""
    if diagram_session_id in active_websockets and active_websockets[diagram_session_id]:
        return
    for session in voice_sessions.values():
        if session.get("diagram_session_id") == diagram_session_id:
            return
    _locks.pop(diagram_session_id, None)
