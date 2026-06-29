"""Tests for fuzzy section key resolution."""

from services.knowledge.section_resolver import (
    best_section_key_match,
    collect_distinct_section_keys,
    score_section_key_match,
    section_title_matches_hint,
)


def test_score_section_key_exact_match() -> None:
    """Exact section keys score 1.0."""
    assert score_section_key_match("chapter-5", "chapter-5") == 1.0


def test_best_section_key_fuzzy_prefix() -> None:
    """Prefix matches prefer the closest section key."""
    matched = best_section_key_match("chapter-5", ["chapter-5-intro", "chapter-6"])
    assert matched == "chapter-5-intro"


def test_best_section_key_no_match() -> None:
    """Unknown chapter numbers return no match."""
    assert best_section_key_match("chapter-99", ["chapter-1", "chapter-2"]) is None


def test_collect_distinct_section_keys() -> None:
    """Duplicate section keys are deduplicated in order."""
    payloads = [
        {"section_key": "chapter-1"},
        {"section_key": "chapter-1"},
        {"section_key": "chapter-2"},
        {"section_key": ""},
    ]
    assert collect_distinct_section_keys(payloads) == ["chapter-1", "chapter-2"]


def test_section_title_matches_hint_chapter_en() -> None:
    """English chapter titles match numeric hints."""
    assert section_title_matches_hint("Chapter 5: Networks", "5", "Chapter 5")


def test_section_title_matches_hint_chapter_zh() -> None:
    """Chinese chapter titles match numeric hints."""
    assert section_title_matches_hint("第5章 网络基础", "5", "第5章")
