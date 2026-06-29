"""Tests for chapter/section hints in user queries."""

from services.knowledge.section_query import is_section_summary_query, parse_section_hint


def test_parse_summary_chapter_5() -> None:
    """Natural-language chapter requests resolve to chapter-5."""
    hint = parse_section_hint("summary chapter 5")
    assert hint is not None
    assert hint.section_key == "chapter-5"
    assert hint.section_number == "5"


def test_parse_chinese_chapter() -> None:
    """Chinese chapter references resolve to numeric keys."""
    hint = parse_section_hint("请总结第5章")
    assert hint is not None
    assert hint.section_key == "chapter-5"


def test_parse_chinese_numeral_chapter() -> None:
    """Chinese numeral chapters map to arabic section keys."""
    hint = parse_section_hint("总结第五章")
    assert hint is not None
    assert hint.section_key == "chapter-5"


def test_no_section_hint_for_generic_query() -> None:
    """Generic queries do not force section scope."""
    assert parse_section_hint("explain neural networks") is None


def test_is_section_summary_query() -> None:
    """Summary + chapter hint triggers section summary mode."""
    assert is_section_summary_query("summary chapter 5") is True
    assert is_section_summary_query("chapter 5 details") is False
