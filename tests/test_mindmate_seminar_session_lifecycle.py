"""MindMate seminar live cap and shutdown close codes."""

from __future__ import annotations

from services.features.mindmate_seminar.config import (
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_MAX_LIVE_SECONDS,
    MINDMATE_COLLAB_MAX_PARTICIPANTS,
    MINDMATE_COLLAB_MONITOR_CONCURRENCY,
    MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS,
)
from services.features.mindmate_seminar.ws_broadcast import (
    ROOM_IDLE_CLOSE_CODE,
    SESSION_ENDED_CLOSE_CODE,
)
from services.online_collab.lifecycle.online_collab_expiry import DURATION_10H


def test_default_participant_cap_is_lower_than_canvas() -> None:
    """MindMate collab caps participants below canvas workshop rooms."""
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS == 50
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS < 500
    assert MINDMATE_COLLAB_DEFAULT_DURATION == DURATION_10H


def test_live_cap_is_thirty_days() -> None:
    """A seminar stays live for 30 days. Silence does not close it."""
    assert MINDMATE_COLLAB_MAX_LIVE_SECONDS == 30 * 24 * 60 * 60


def test_orphan_idle_score_grace_is_thirty_minutes() -> None:
    """An idle score whose room hash is already gone is dropped after thirty minutes."""
    assert MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS == 30 * 60


def test_idle_monitor_concurrency_default_matches_workshop() -> None:
    """Idle evaluation concurrency defaults to twenty parallel room checks."""
    assert MINDMATE_COLLAB_MONITOR_CONCURRENCY == 20


def test_ws_shutdown_close_codes_documented() -> None:
    """4010 is the 30-day close. 4011 is the host stop. The page handles both."""
    assert ROOM_IDLE_CLOSE_CODE == 4010
    assert SESSION_ENDED_CLOSE_CODE == 4011
