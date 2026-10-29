"""Rules for saving a finished MindMate seminar into the owner's library."""

from __future__ import annotations

from datetime import UTC, datetime

from models.domain.mindmate_seminar import MindmateSeminarSession
from services.features.mindmate_seminar.library_archive import (
    finished_seminar_save_block_reason,
    saved_seminar_edit_block_reason,
    saved_seminar_summary,
    saved_seminar_title_error,
    viewer_may_open_saved_seminar,
)
from services.features.mindmate_seminar.reopen_session import (
    reopen_block_reason,
    reopen_duration,
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


def test_only_the_owner_can_reopen_a_saved_seminar() -> None:
    """Continue session is refused for a joiner and for a seminar that was never saved."""
    saved_at = datetime(2026, 9, 28, tzinfo=UTC)
    assert reopen_block_reason(owner_user_id=7, actor_user_id=8, library_saved_at=saved_at) == "not_owner"
    assert reopen_block_reason(owner_user_id=7, actor_user_id=7, library_saved_at=None) == "not_saved"
    assert reopen_block_reason(owner_user_id=7, actor_user_id=7, library_saved_at=saved_at) is None


def test_reopen_keeps_a_valid_duration_preset() -> None:
    """An organization seminar keeps its saved duration when that preset is still allowed."""
    assert reopen_duration("organization", "10h") == "10h"
    assert reopen_duration("organization", "not-a-duration") == "10h"


def test_saved_seminar_summary_includes_save_time() -> None:
    """The library row exposes the title and when it was saved."""
    saved_at = datetime(2026, 9, 28, 1, 2, tzinfo=UTC)
    ended_at = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
    session = MindmateSeminarSession(
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
    summary = saved_seminar_summary(session, 7)
    assert summary["session_id"] == "session-1"
    assert summary["title"] == "Grade 5 seminar"
    assert summary["library_saved_at"] == saved_at.isoformat()
    assert summary["ended_at"] == ended_at.isoformat()
    assert summary["pinned"] is False
    assert summary["owned"] is True


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


def test_a_joiner_can_open_a_saved_seminar() -> None:
    """History is for everyone who joined, not only the host."""
    saved_at = datetime(2026, 9, 28, tzinfo=UTC)
    assert (
        viewer_may_open_saved_seminar(
            owner_user_id=7,
            viewer_user_id=8,
            library_saved_at=saved_at,
            is_member=True,
        )
        is True
    )
    assert (
        viewer_may_open_saved_seminar(
            owner_user_id=7,
            viewer_user_id=8,
            library_saved_at=saved_at,
            is_member=False,
        )
        is False
    )
    assert (
        viewer_may_open_saved_seminar(
            owner_user_id=7,
            viewer_user_id=7,
            library_saved_at=saved_at,
            is_member=False,
        )
        is True
    )
    assert (
        viewer_may_open_saved_seminar(
            owner_user_id=7,
            viewer_user_id=7,
            library_saved_at=None,
            is_member=True,
        )
        is False
    )


def test_only_the_owner_sees_the_pin() -> None:
    """A joiner sees the seminar, and the host's pin does not pin it for them."""
    saved_at = datetime(2026, 9, 28, tzinfo=UTC)
    session = MindmateSeminarSession(
        id="session-1",
        code="ABC-DEF",
        owner_user_id=7,
        title="Grade 5 seminar",
        visibility="organization",
        duration_preset="today",
        started_at=saved_at,
        ended_at=saved_at,
        library_saved_at=saved_at,
        library_pinned=True,
    )
    host = saved_seminar_summary(session, 7)
    guest = saved_seminar_summary(session, 8)
    assert host["owned"] is True
    assert host["pinned"] is True
    assert guest["owned"] is False
    assert guest["pinned"] is False
