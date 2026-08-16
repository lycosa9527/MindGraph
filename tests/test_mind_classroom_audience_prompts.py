"""专业程度 briefs must tell the LLM which expertise level the diagram is on."""

from __future__ import annotations

from services.mind_classroom.prompts.audience_prompts import (
    audience_brief,
    audience_label,
    normalize_audience_level,
)
from services.mind_classroom.prompts.canvas_tour_prompts import build_canvas_tour_user_message
from services.mind_classroom.prompts.lesson_planner_prompts import build_open_planner_message


def test_normalize_audience_defaults_to_general() -> None:
    """Unknown or empty 专业程度 falls back to general."""
    assert normalize_audience_level("") == "general"
    assert normalize_audience_level("phd") == "general"
    assert normalize_audience_level("expert") == "expert"


def test_audience_briefs_differ_by_level() -> None:
    """Primary and expert must not share the same teaching contract."""
    primary = audience_brief("primary", "zh")
    expert = audience_brief("expert", "zh")
    assert audience_label("primary", "zh") == "小学"
    assert audience_label("expert", "zh") == "专家"
    assert "小学" in primary
    assert "禁止术语" in primary
    assert "专家" in expert
    assert "科普开场" in expert
    assert primary != expert


def test_canvas_tour_prompt_embeds_audience_brief() -> None:
    """Voice-script user message carries the diagram 专业程度 brief."""
    nodes = [{"id": "topic", "text": "光合作用", "kind": "topic"}]
    primary = build_canvas_tour_user_message(
        nodes,
        settings={"audience_level": "primary", "language": "zh"},
        max_steps=8,
    )
    expert = build_canvas_tour_user_message(
        nodes,
        settings={"audience_level": "expert", "language": "zh"},
        max_steps=8,
    )
    assert "audience_brief" in primary
    assert "小学" in primary
    assert "专家" in expert
    assert "禁止术语" in primary
    assert "禁止术语" not in expert


def test_slide_planner_prompt_embeds_audience_brief() -> None:
    """Slide teacher_script planning follows the same 专业程度 brief."""
    outline = {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]}
    senior = build_open_planner_message(
        outline,
        language="zh",
        diagram_title="光合作用",
        settings={"audience_level": "senior", "language": "zh"},
    )
    assert "audience_brief" in senior
    assert "高中" in senior
    assert "大学论文腔" in senior
