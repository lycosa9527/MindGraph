"""Clip-teaching rules: trim, chapters, replies, and the clip-teaching feature gate."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from services.features.clip_lessons.errors import ClipLessonError
from services.features.clip_lessons.rules import (
    ChapterDraft,
    assert_reply_target,
    can_delete_comment,
    can_edit_lesson,
    drop_chapters_outside,
    normalize_chapters,
    parse_lesson_id,
    validate_trim,
)
from services.infrastructure.http.feature_gate import feature_flag_gate


def _request(path: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


def test_trim_rejects_an_end_that_is_not_after_the_start() -> None:
    """A playback window must move forward."""
    assert validate_trim(1000, None) == (1000, None)
    assert validate_trim(0, 5000) == (0, 5000)
    with pytest.raises(ClipLessonError) as caught:
        validate_trim(4000, 4000)
    assert caught.value.code == "trim_invalid"


def test_chapters_reject_duplicates_and_points_outside_the_trim() -> None:
    """Chapter starts are unique and sit inside the saved window."""
    trimmed = normalize_chapters(
        [ChapterDraft("结尾", 8000), ChapterDraft("开场", 1000)],
        0,
        9000,
    )
    assert [row.start_ms for row in trimmed] == [1000, 8000]
    with pytest.raises(ClipLessonError) as duplicate:
        normalize_chapters(
            [ChapterDraft("甲", 1000), ChapterDraft("乙", 1000)],
            0,
            None,
        )
    assert duplicate.value.code == "chapter_invalid"
    with pytest.raises(ClipLessonError):
        normalize_chapters([ChapterDraft("太早", 100)], 1000, 5000)


def test_saving_a_tighter_trim_drops_chapters_outside_it() -> None:
    """Chapters that no longer sit in the window are removed."""
    kept = drop_chapters_outside(
        [ChapterDraft("甲", 500), ChapterDraft("乙", 2500), ChapterDraft("丙", 9000)],
        1000,
        8000,
    )
    assert [row.title for row in kept] == ["乙"]


def test_replies_only_attach_to_a_live_root_on_the_same_lesson() -> None:
    """A reply to a reply is rejected."""
    assert_reply_target(
        parent_lesson_id="lesson",
        lesson_id="lesson",
        parent_parent_id=None,
        parent_deleted=False,
    )
    with pytest.raises(ClipLessonError) as depth:
        assert_reply_target(
            parent_lesson_id="lesson",
            lesson_id="lesson",
            parent_parent_id=4,
            parent_deleted=False,
        )
    assert depth.value.code == "reply_depth"
    with pytest.raises(ClipLessonError) as missing:
        assert_reply_target(
            parent_lesson_id="other",
            lesson_id="lesson",
            parent_parent_id=None,
            parent_deleted=False,
        )
    assert missing.value.code == "parent_not_found"


def test_owner_edits_the_lesson_and_either_party_deletes_a_comment() -> None:
    """Organization members comment. Only the owner changes the lesson."""
    assert can_edit_lesson(3, 3) is True
    assert can_edit_lesson(4, 3) is False
    assert can_delete_comment(4, 3, 4) is True
    assert can_delete_comment(3, 3, 9) is True
    assert can_delete_comment(8, 3, 4) is False


def test_lesson_ids_are_uuids() -> None:
    """A non-UUID path does not reach storage."""
    parsed = parse_lesson_id("550e8400-e29b-41d4-a716-446655440000")
    assert parsed == "550e8400-e29b-41d4-a716-446655440000"
    with pytest.raises(ClipLessonError) as caught:
        parse_lesson_id("../deck")
    assert caught.value.code == "not_found"


@pytest.mark.asyncio
async def test_feature_gate_blocks_clip_lessons_when_flag_is_off() -> None:
    """The online library can stay on while clip teaching is off."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_CLIP_TEACHING=False, FEATURE_VOD=True),
    ):
        response = await feature_flag_gate(_request("/api/clip-lessons"), call_next)
    assert response.status_code == 404
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_feature_gate_allows_clip_lessons_when_flag_is_on() -> None:
    """Clip teaching does not require the admin video library."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_CLIP_TEACHING=True, FEATURE_VOD=False),
    ):
        await feature_flag_gate(_request("/api/clip-lessons"), call_next)
    call_next.assert_awaited()
