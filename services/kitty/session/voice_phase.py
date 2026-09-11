"""Kitty voice-phase machine (server contract for every client).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_session,
)
from services.kitty.session.runtime_state import voice_sessions

VALID_PHASES: FrozenSet[str] = frozenset({"listening", "speaking", "active", "thinking"})
SESSION_PHASE_KEY = "_desktop_voice_phase"

# Documented half-duplex flow. Barge-in (speaking → listening) is legal.
_ALLOWED: dict[str, FrozenSet[str]] = {
    "active": frozenset({"listening", "thinking", "speaking"}),
    "listening": frozenset({"thinking", "active", "speaking"}),
    "thinking": frozenset({"speaking", "active", "listening"}),
    "speaking": frozenset({"active", "listening", "thinking"}),
}


def normalize_voice_phase(raw: object) -> Optional[str]:
    """Return a fanout phase or ``None`` when the value is not a server phase."""
    phase = str(raw or "").strip().lower()
    if phase not in VALID_PHASES:
        return None
    return phase


def session_voice_phase(voice_session_id: str) -> str:
    """Last published phase, or ``active`` when the session has not spoken yet."""
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return "active"
    current = normalize_voice_phase(sess.get(SESSION_PHASE_KEY))
    return current or "active"


def is_legal_transition(source: str, dest: str) -> bool:
    """True when ``source`` → ``dest`` is a documented half-duplex step."""
    src = normalize_voice_phase(source)
    dst = normalize_voice_phase(dest)
    if src is None or dst is None:
        return False
    if src == dst:
        return True
    return dst in _ALLOWED[src]


async def set_voice_phase(voice_session_id: str, phase: str) -> bool:
    """Publish a phase when it is valid. Same-phase is a no-op success."""
    dest = normalize_voice_phase(phase)
    if dest is None:
        return False
    current = session_voice_phase(voice_session_id)
    if current == dest:
        return True
    if not is_legal_transition(current, dest):
        return False
    await fanout_voice_phase_from_session(voice_session_id, dest)
    return True
