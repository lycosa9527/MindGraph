"""Canvas 专业程度 builder and DingTalk prompt detection."""

from prompts.mind_map_audience import (
    build_mind_map_audience_instructions,
    detect_ai_content_level_from_prompt,
    resolve_prompt_audience,
)


def test_builder_leaves_general_unconstrained() -> None:
    """general matches canvas: no extra instruction block."""
    assert build_mind_map_audience_instructions("general", "zh") is None
    assert build_mind_map_audience_instructions("general", "en") is None
    assert build_mind_map_audience_instructions("unknown", "zh") is None


def test_builder_matches_canvas_zh_primary() -> None:
    """Chinese primary block is the native canvas template."""
    block = build_mind_map_audience_instructions("primary", "zh")
    assert block is not None
    assert block.startswith("请按「小学」专业程度生成内容。")
    assert "用语：" in block
    assert "句子：" in block
    assert "前提：" in block
    assert "深度：" in block


def test_builder_matches_canvas_en_expert() -> None:
    """English expert block is the native canvas template."""
    block = build_mind_map_audience_instructions("expert", "en")
    assert block is not None
    assert block.startswith("Write this content for an expert peer.")
    assert "Voice:" in block
    assert "domain terminology" in block


def test_builder_uses_zh_for_zh_tw() -> None:
    """zh-tw still uses the Chinese canvas templates."""
    block = build_mind_map_audience_instructions("university", "zh-tw")
    assert block is not None
    assert "大学" in block


def test_detect_defaults_to_general_without_level_request() -> None:
    """Topics that mention school words as content stay general."""
    assert detect_ai_content_level_from_prompt("比较猫和狗") == "general"
    assert detect_ai_content_level_from_prompt("大学生活规划") == "general"
    assert detect_ai_content_level_from_prompt("画一个关于小学教育的思维导图") == "general"
    assert detect_ai_content_level_from_prompt("draw a mind map about college admissions") == "general"
    assert detect_ai_content_level_from_prompt("draw a mind map about primary school") == "general"
    assert detect_ai_content_level_from_prompt("reasons for primary school reform") == "general"
    assert detect_ai_content_level_from_prompt("") == "general"


def test_detect_explicit_zh_level_requests() -> None:
    """Trailing / leading / 按 / 面向 phrases map onto catalog ids."""
    assert detect_ai_content_level_from_prompt("画一个光合作用的思维导图，小学水平") == "primary"
    assert detect_ai_content_level_from_prompt("画一个小学水平的光合作用思维导图") == "primary"
    assert detect_ai_content_level_from_prompt("小学水平画光合作用") == "primary"
    assert detect_ai_content_level_from_prompt("按高中专业程度生成呼吸作用导图") == "senior"
    assert detect_ai_content_level_from_prompt("面向小学生画水循环") == "primary"
    assert detect_ai_content_level_from_prompt("专业程度：专家 比较猫和狗") == "expert"
    assert detect_ai_content_level_from_prompt("机器学习，成人水平") == "adult"
    assert detect_ai_content_level_from_prompt("画通货膨胀，大学程度") == "university"
    assert detect_ai_content_level_from_prompt("初中难度的茶叶导图") == "junior"


def test_detect_explicit_en_level_requests() -> None:
    """English professional-level phrases map onto catalog ids."""
    assert detect_ai_content_level_from_prompt("photosynthesis, primary school") == "primary"
    assert detect_ai_content_level_from_prompt("draw photosynthesis for primary school") == "primary"
    assert detect_ai_content_level_from_prompt("content level: university photosynthesis") == "university"
    assert detect_ai_content_level_from_prompt("professional level to expert: inflation") == "expert"
    assert detect_ai_content_level_from_prompt("tea, adult level") == "adult"
    assert detect_ai_content_level_from_prompt("expert-level machine learning") == "expert"


def test_resolve_strips_level_phrase_and_builds_canvas_block() -> None:
    """Detected level is stripped from the topic and replaced by canvas instructions."""
    topic, level, block = resolve_prompt_audience("画一个光合作用的思维导图，小学水平", "zh")
    assert level == "primary"
    assert topic == "画一个光合作用的思维导图"
    assert block is not None
    assert "请按「小学」专业程度生成内容。" in block
    assert "小学水平" not in topic


def test_resolve_general_keeps_prompt_and_omits_block() -> None:
    """No requested level leaves the prompt unchanged."""
    topic, level, block = resolve_prompt_audience("比较猫和狗", "zh")
    assert topic == "比较猫和狗"
    assert level == "general"
    assert block is None


def test_resolve_general_request_still_omits_block() -> None:
    """Explicit 通用水平 is general: strip the phrase, no instruction block."""
    topic, level, block = resolve_prompt_audience("比较猫和狗，通用水平", "zh")
    assert level == "general"
    assert topic == "比较猫和狗"
    assert block is None
