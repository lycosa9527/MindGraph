"""Rules for saving a finished MindMate seminar into the owner's library."""

from __future__ import annotations

from datetime import UTC, datetime

from models.domain.mindmate_collab import MindmateCollabSession
from services.features.mindmate_collab.library_archive import (
    finished_seminar_save_block_reason,
    saved_seminar_summary,
)


def test_owner_can_save_after_the_seminar_ends() -> None:
    """A finished room may be saved by its host."""
    reason = finished_seminar_save_block_reason(
        ended_at=datetime(2026, 9, 28, tzinfo=UTC),
        owner_user_id=7,
        actor_user_id=7,
    )
    assert reason is None


def test_live_seminar_cannot_be_saved_yet() -> None:
    """Save waits until the room has actually ended."""
    reason = finished_seminar_save_block_reason(
        ended_at=None,
        owner_user_id=7,
        actor_user_id=7,
    )
    assert reason == "still_live"


def test_only_the_owner_can_save() -> None:
    """Another participant is not the library owner."""
    reason = finished_seminar_save_block_reason(
        ended_at=datetime(2026, 9, 28, tzinfo=UTC),
        owner_user_id=7,
        actor_user_id=8,
    )
    assert reason == "not_owner"


def test_saved_seminar_summary_includes_save_time() -> None:
    """The library row exposes the title and when it was saved."""
    saved_at = datetime(2026, 9, 28, 1, 2, tzinfo=UTC)
    ended_at = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
    session = MindmateCollabSession(
        id="session-1",
        code="ABC-DEF",
        owner_user_id=7,
        title="Grade 5 seminar",
        visibility="organization",
        duration_preset="today",
        started_at=ended_at,
        ended_at=ended_at,
        library_saved_at=saved_at,
    )
    summary = saved_seminar_summary(session)
    assert summary["session_id"] == "session-1"
    assert summary["title"] == "Grade 5 seminar"
    assert summary["library_saved_at"] == saved_at.isoformat()
    assert summary["ended_at"] == ended_at.isoformat()
