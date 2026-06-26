"""Tests for activity preview clipping."""

from services.admin.user_usage_activity import (
    activity_row_has_content,
    clip_activity_preview,
    clip_activity_title,
)


def test_clip_activity_preview_collapses_whitespace() -> None:
    """Preview clipping collapses internal whitespace."""
    assert clip_activity_preview("  hello\n\nworld  ") == "hello world"


def test_clip_activity_preview_truncates_with_ellipsis() -> None:
    """Long previews truncate with an ellipsis at max length."""
    text = "a" * 200
    clipped = clip_activity_preview(text, max_len=120)
    assert clipped is not None
    assert len(clipped) == 120
    assert clipped.endswith("…")


def test_clip_activity_preview_empty_returns_none() -> None:
    """Blank previews return None."""
    assert clip_activity_preview("") is None
    assert clip_activity_preview("   \n") is None


def test_clip_activity_title() -> None:
    """Activity titles are trimmed of surrounding whitespace."""
    assert clip_activity_title("  Topic  ") == "Topic"


def test_activity_row_has_content() -> None:
    """Rows with any title or preview field count as having content."""
    assert activity_row_has_content(title=None, prompt_preview="hi", reply_preview=None)
    assert not activity_row_has_content(title=None, prompt_preview=None, reply_preview=None)
