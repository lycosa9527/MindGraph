"""Kitty WebSocket idle-timeout predicates."""

from __future__ import annotations


def kitty_session_holds_idle(session: object) -> bool:
    """True while lecture TTS is in flight — do not idle-close the socket."""
    return isinstance(session, dict) and session.get("_kitty_lecture") is True


def kitty_idle_should_close(
    session: object,
    *,
    last_inbound_monotonic: float,
    now_monotonic: float,
    timeout_sec: float,
) -> bool:
    """Close only after a quiet interval with no lecture hold."""
    if kitty_session_holds_idle(session):
        return False
    return now_monotonic - last_inbound_monotonic >= timeout_sec
