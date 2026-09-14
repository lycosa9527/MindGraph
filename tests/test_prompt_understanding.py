"""Shared prepare_generation_prompt for gallery, DingTalk, and Kitty."""

from agents.core.prompt_understanding import prepare_generation_prompt
from prompts.mind_map_audience import build_mind_map_audience_instructions


def test_prepare_defaults_to_general_without_level() -> None:
    """Plain topics stay general and keep the prompt."""
    prepared = prepare_generation_prompt("比较猫和狗", "zh")
    assert prepared.ai_content_level == "general"
    assert prepared.topic_prompt == "比较猫和狗"
    assert prepared.generation_instructions is None
    assert prepared.merged_prompt() == "比较猫和狗"
    assert prepared.is_learning_sheet is False


def test_prepare_strips_nl_level_and_builds_canvas_block() -> None:
    """小学水平 becomes the canvas audience block."""
    prepared = prepare_generation_prompt("画一个光合作用的思维导图，小学水平", "zh")
    assert prepared.ai_content_level == "primary"
    assert "小学水平" not in prepared.topic_prompt
    assert "光合作用" in prepared.topic_prompt
    assert prepared.generation_instructions == build_mind_map_audience_instructions("primary", "zh")
    merged = prepared.merged_prompt()
    assert "【用户要求】" in merged
    assert "请按「小学」专业程度生成内容。" in merged
    assert prepared.topic_seed == "光合作用"


def test_prepare_explicit_instructions_win_but_topic_is_stripped() -> None:
    """Canvas picker text wins; NL level is still stripped from the topic."""
    explicit = build_mind_map_audience_instructions("expert", "zh")
    prepared = prepare_generation_prompt(
        "光合作用，小学水平",
        "zh",
        explicit_instructions=explicit,
    )
    assert prepared.generation_instructions == explicit
    assert "小学水平" not in prepared.topic_prompt
    assert prepared.topic_prompt == "光合作用"


def test_prepare_learning_sheet_and_level_together() -> None:
    """半成品 plus 小学水平 both apply."""
    prepared = prepare_generation_prompt("光合作用半成品，小学水平", "zh")
    assert prepared.is_learning_sheet is True
    assert prepared.ai_content_level == "primary"
    assert "半成品" not in prepared.topic_prompt
    assert "小学水平" not in prepared.topic_prompt
    assert "光合作用" in prepared.topic_prompt


def test_prepare_empty_after_strip_falls_back_to_raw() -> None:
    """A prompt that is only a level phrase keeps the raw text as topic."""
    prepared = prepare_generation_prompt("小学水平", "zh")
    assert prepared.ai_content_level == "primary"
    assert prepared.topic_prompt == "小学水平"


def test_prepare_double_clean_learning_sheet_stays_nonempty() -> None:
    """Cleaning 半成品 twice does not wipe a real topic."""
    first = prepare_generation_prompt("鸦片战争流程图半成品", "zh")
    second = prepare_generation_prompt(first.topic_prompt, "zh")
    assert first.is_learning_sheet is True
    assert "鸦片战争" in second.topic_prompt
    assert second.topic_prompt.strip() != ""
