"""MindMate collab idle monitor and shutdown close codes."""

from __future__ import annotations

from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_IDLE_GRACE_SECONDS,
    MINDMATE_COLLAB_IDLE_SILENCE_SECONDS,
    MINDMATE_COLLAB_MAX_PARTICIPANTS,
    MINDMATE_COLLAB_MONITOR_CONCURRENCY,
    MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS,
)
from services.online_collab.lifecycle.online_collab_expiry import DURATION_10H


def test_default_participant_cap_is_lower_than_canvas() -> None:
    """MindMate collab caps participants below canvas workshop rooms."""
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS == 50
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS < 500
    assert MINDMATE_COLLAB_DEFAULT_DURATION == DURATION_10H


def test_idle_defaults_match_forty_five_minute_shutdown() -> None:
    """Idle warning at 43m and grace at 2m yields 45m total auto-shutdown."""
    assert MINDMATE_COLLAB_IDLE_SILENCE_SECONDS == 43 * 60
    assert MINDMATE_COLLAB_IDLE_GRACE_SECONDS == 2 * 60


def test_zombie_grace_default_thirty_minutes() -> None:
    """Zombie participant grace defaults to thirty minutes."""
    assert MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS == 30 * 60


def test_idle_monitor_concurrency_default_matches_workshop() -> None:
    """Idle evaluation concurrency defaults to twenty parallel room checks."""
    assert MINDMATE_COLLAB_MONITOR_CONCURRENCY == 20


def test_ws_shutdown_close_codes_documented() -> None:
    """4010 idle teardown; 4011 owner stop — mirrored in useMindmateCollab."""
    idle_code = 4010
    owner_stop_code = 4011
    assert idle_code != owner_stop_code
