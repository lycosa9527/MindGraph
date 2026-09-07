"""Tests for mind-map audience instruction append helper."""

from prompts.ai_content_level import (
    append_audience_instructions,
    extract_appended_generation_instructions,
    merge_generation_instructions,
)


def test_append_audience_instructions_joins_when_both_present() -> None:
    """Audience block is appended after the base prompt."""
    result = append_audience_instructions("base prompt", "小学短句")
    assert result == "base prompt\n\n小学短句"


def test_append_audience_instructions_skips_empty_block() -> None:
    """Missing audience text leaves the prompt unchanged."""
    assert append_audience_instructions("base prompt", None) == "base prompt"
    assert append_audience_instructions("base prompt", "  ") == "base prompt"


def test_append_audience_instructions_uses_block_when_prompt_empty() -> None:
    """A block alone is returned when the prompt is empty."""
    assert append_audience_instructions("", "expert") == "expert"


def test_merge_generation_instructions_uses_locale_marker() -> None:
    """Chinese and English merges use the same marker the router historically used."""
    zh = merge_generation_instructions("主题", "小学短句", "zh")
    assert zh == "主题\n\n【用户要求】\n小学短句"
    en = merge_generation_instructions("Topic", "Keep it expert", "en")
    assert en == "Topic\n\nUser requirements:\nKeep it expert"


def test_extract_appended_generation_instructions_round_trips() -> None:
    """The suffix after the locale marker is recovered for branch-expand prompts."""
    merged = merge_generation_instructions("主题", "小学短句", "zh")
    assert extract_appended_generation_instructions(merged, "zh") == "小学短句"
    assert extract_appended_generation_instructions("主题", "zh") is None
    assert extract_appended_generation_instructions("小学短句", "zh") is None
