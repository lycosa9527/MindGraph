"""Tests for activity preview clipping."""

from services.admin.user_usage_activity import (
    activity_row_has_content,
    clip_activity_preview,
    clip_activity_title,
)


def test_clip_activity_preview_collapses_whitespace() -> None:
    assert clip_activity_preview("  hello\n\nworld  ") == "hello world"


def test_clip_activity_preview_truncates_with_ellipsis() -> None:
    text = "a" * 200
    clipped = clip_activity_preview(text, max_len=120)
    assert clipped is not None
    assert len(clipped) == 120
    assert clipped.endswith("…")


def test_clip_activity_preview_empty_returns_none() -> None:
    assert clip_activity_preview("") is None
    assert clip_activity_preview("   \n") is None


def test_clip_activity_title() -> None:
    assert clip_activity_title("  Topic  ") == "Topic"


def test_activity_row_has_content() -> None:
    assert activity_row_has_content(title=None, prompt_preview="hi", reply_preview=None)
    assert not activity_row_has_content(title=None, prompt_preview=None, reply_preview=None)
