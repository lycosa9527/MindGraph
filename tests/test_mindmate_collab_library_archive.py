"""Rules for saving a finished MindMate seminar into the owner's library."""

from __future__ import annotations

from datetime import UTC, datetime

from models.domain.mindmate_collab import MindmateCollabSession
from services.features.mindmate_collab.library_archive import (
    finished_seminar_save_block_reason,
    saved_seminar_edit_block_reason,
    saved_seminar_summary,
    saved_seminar_title_error,
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
    assert summary["pinned"] is False


def test_blank_or_oversized_titles_are_rejected() -> None:
    """Rename requires a title that fits the column."""
    assert saved_seminar_title_error("   ") == "empty_title"
    assert saved_seminar_title_error("x" * 201) == "title_too_long"
    assert saved_seminar_title_error("  Grade 5  ") is None


def test_only_the_owner_can_edit_a_saved_seminar() -> None:
    """Pin, rename, and delete stay on the owner's saved copy."""
    saved_at = datetime(2026, 9, 28, tzinfo=UTC)
    assert (
        saved_seminar_edit_block_reason(
            owner_user_id=7,
            actor_user_id=8,
            library_saved_at=saved_at,
            ended_at=saved_at,
        )
        == "not_found"
    )
    assert (
        saved_seminar_edit_block_reason(
            owner_user_id=7,
            actor_user_id=7,
            library_saved_at=None,
            ended_at=saved_at,
        )
        == "not_found"
    )
    assert (
        saved_seminar_edit_block_reason(
            owner_user_id=7,
            actor_user_id=7,
            library_saved_at=saved_at,
            ended_at=None,
        )
        == "still_live"
    )
    assert (
        saved_seminar_edit_block_reason(
            owner_user_id=7,
            actor_user_id=7,
            library_saved_at=saved_at,
            ended_at=saved_at,
        )
        is None
    )
