"""Pinned seminar brief rewrite: goals and materials can change after start."""

from services.features.mindmate_seminar.brief_edit import (
    normalize_brief_lines,
    rewrite_seminar_brief_text,
)


_SEED = """[[seminar-brief]]
教研主题
测试

教研目标
1. 目标1
2. 目标2

参与人员
跨校教研
1. 王雅萱（组长）
2. 董长华（教研员）

资源准备
1. 框架.pdf
"""


def test_rewrite_replaces_goals_and_keeps_people() -> None:
    """Topic, visibility, and member lines stay; only the goal list changes."""
    text = rewrite_seminar_brief_text(_SEED, ["新的目标"], ["框架.pdf"])
    assert text is not None
    assert "教研主题\n测试" in text
    assert "1. 新的目标" in text
    assert "目标1" not in text
    assert "1. 王雅萱（组长）" in text
    assert "跨校教研" in text
    assert text.startswith("[[seminar-brief]]")


def test_rewrite_drops_empty_optional_sections() -> None:
    """Clearing goals and materials removes those headings from the card text."""
    text = rewrite_seminar_brief_text(_SEED, [], [])
    assert text is not None
    assert "教研目标" not in text
    assert "资源准备" not in text
    assert "参与人员" in text


def test_rewrite_keeps_english_headings() -> None:
    """An English seed stays in English when the host edits it."""
    text = rewrite_seminar_brief_text(
        "Seminar topic\nLesson\n\nParticipants\nSchool",
        ["One goal"],
        [],
    )
    assert text is not None
    assert text.startswith("Seminar topic\nLesson")
    assert "Seminar goals\n1. One goal" in text
    assert "Participants\nSchool" in text
    assert "教研" not in text


def test_rewrite_renames_the_topic_and_keeps_materials() -> None:
    """Omitting materials leaves the file list in place while the topic changes."""
    text = rewrite_seminar_brief_text(_SEED, ["目标1"], None, "新主题")
    assert text is not None
    assert "教研主题\n新主题" in text
    assert "资源准备\n1. 框架.pdf" in text
    assert "1. 王雅萱（组长）" in text


def test_rewrite_ignores_chat() -> None:
    """Ordinary messages are not brief cards."""
    assert rewrite_seminar_brief_text("hello", ["目标"], []) is None


def test_normalize_brief_lines_rejects_a_line_past_the_cap() -> None:
    """A single goal cannot exceed the row limit."""
    assert normalize_brief_lines(["ok", "x" * 201], limit=12, max_len=200) is None
    assert normalize_brief_lines(["  one  ", ""], limit=12, max_len=200) == ["one"]
