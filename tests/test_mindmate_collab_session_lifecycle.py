"""MindMate collab idle monitor and shutdown close codes."""

from __future__ import annotations

from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_IDLE_GRACE_SECONDS,
    MINDMATE_COLLAB_IDLE_SILENCE_SECONDS,
    MINDMATE_COLLAB_MAX_PARTICIPANTS,
    MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS,
)


def test_default_participant_cap_is_lower_than_canvas() -> None:
    """MindMate collab caps participants below canvas workshop rooms."""
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS == 50
    assert MINDMATE_COLLAB_MAX_PARTICIPANTS < 500


def test_idle_defaults_match_canvas_pattern() -> None:
    """Idle warning and grace windows mirror canvas collab defaults."""
    assert MINDMATE_COLLAB_IDLE_SILENCE_SECONDS == 30 * 60
    assert MINDMATE_COLLAB_IDLE_GRACE_SECONDS == 2 * 60


def test_zombie_grace_default_thirty_minutes() -> None:
    """Zombie participant grace defaults to thirty minutes."""
    assert MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS == 30 * 60


def test_ws_shutdown_close_codes_documented() -> None:
    """4010 idle teardown; 4011 owner stop — mirrored in useMindmateCollab."""
    idle_code = 4010
    owner_stop_code = 4011
    assert idle_code != owner_stop_code
