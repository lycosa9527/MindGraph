"""Tests for mind-map audience instruction append helper."""

from prompts.ai_content_level import append_audience_instructions


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
