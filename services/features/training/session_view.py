"""
Read-only stale-session rules for org training follow.

Readers never write Redis. ``audience_view`` is what clients should see;
``present_session`` (in session_store) persists pause/end at most once.
"""

from __future__ import annotations

import time
from typing import Any, Optional, TypeGuard

from services.features.training.constants import (
    ACTIVE_STATES,
    INSTRUCTOR_HEARTBEAT_STALE_SECONDS,
    STATE_ENDED,
    STATE_LIVE,
    STATE_PAUSED,
)


def is_hard_expired(session: dict[str, Any], *, now: Optional[float] = None) -> bool:
    """True when the 4h wall clock has passed and the room is not already ended."""
    if session.get("state") == STATE_ENDED:
        return False
    expires = float(session.get("expires_at") or 0)
    if not expires:
        return False
    return (now if now is not None else time.time()) >= expires


def is_instructor_stale(session: dict[str, Any], *, now: Optional[float] = None) -> bool:
    """True when a live session has not seen the instructor recently."""
    if session.get("state") != STATE_LIVE:
        return False
    if is_hard_expired(session, now=now):
        return False
    seen = float(session.get("instructor_seen_at") or 0)
    clock = now if now is not None else time.time()
    return clock - seen >= INSTRUCTOR_HEARTBEAT_STALE_SECONDS


def is_active_session(
    session: Optional[dict[str, Any]],
    *,
    now: Optional[float] = None,
) -> TypeGuard[dict[str, Any]]:
    """Live or paused, and still inside the hard TTL."""
    if session is None:
        return False
    if session.get("state") not in ACTIVE_STATES:
        return False
    return not is_hard_expired(session, now=now)


def audience_view(session: dict[str, Any], *, now: Optional[float] = None) -> dict[str, Any]:
    """Copy with ended/paused overlaid. Same seq. No Redis write."""
    if is_hard_expired(session, now=now):
        viewed = dict(session)
        viewed["state"] = STATE_ENDED
        return viewed
    if is_instructor_stale(session, now=now):
        viewed = dict(session)
        viewed["state"] = STATE_PAUSED
        return viewed
    return session
