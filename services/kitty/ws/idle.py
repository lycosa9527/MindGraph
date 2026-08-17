"""Kitty WebSocket idle-timeout predicates."""

from __future__ import annotations

import time
from typing import Optional

from services.kitty.tts.lecture_cache import LECTURE_HOLD_UNTIL_KEY, PREFETCH_KEY


def kitty_session_holds_idle(
    session: object,
    *,
    now_monotonic: Optional[float] = None,
) -> bool:
    """True while lecture TTS, prefetch, or client playback should keep the socket."""
    if not isinstance(session, dict):
        return False
    if session.get("_kitty_lecture") is True:
        return True
    if session.get("_kitty_tts_speaking") is True:
        return True
    if session.get(PREFETCH_KEY) is not None:
        return True
    hold = session.get(LECTURE_HOLD_UNTIL_KEY)
    if isinstance(hold, (int, float)):
        clock = now_monotonic if now_monotonic is not None else time.monotonic()
        return clock < float(hold)
    return False


def kitty_idle_should_close(
    session: object,
    *,
    last_inbound_monotonic: float,
    now_monotonic: float,
    timeout_sec: float,
) -> bool:
    """Close only after a quiet interval with no lecture hold."""
    if kitty_session_holds_idle(session, now_monotonic=now_monotonic):
        return False
    return now_monotonic - last_inbound_monotonic >= timeout_sec
