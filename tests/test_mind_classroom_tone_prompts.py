"""讲解语气 briefs must produce distinct spoken cadence."""

from __future__ import annotations

from services.mind_classroom.prompts.canvas_tour_prompts import build_canvas_tour_user_message
from services.mind_classroom.prompts.lesson_planner_prompts import build_open_planner_message
from services.mind_classroom.prompts.tone_prompts import (
    TONE_TABLE_HEADER_ZH,
    normalize_tone,
    tone_brief,
    tone_label,
)


def test_normalize_tone_defaults_to_classroom() -> None:
    """Unknown or empty tone falls back to classroom."""
    assert normalize_tone("") == "classroom"
    assert normalize_tone("whisper") == "classroom"
    assert normalize_tone("socratic") == "socratic"


def test_tone_briefs_differ() -> None:
    """Fast talk and exam outline must not share the same contract."""
    fast = tone_brief("fast", "zh")
    exam = tone_brief("exam_outline", "zh")
    story = tone_brief("story", "zh")
    assert tone_label("fast", "zh") == "速讲"
    assert tone_label("exam_outline", "zh") == "考点提纲"
    assert TONE_TABLE_HEADER_ZH in fast
    assert "【速讲】" in fast
    assert "【考点提纲】" in exam
    assert "画面" in story
    assert "3～4 句" in fast
    assert "【记】" in exam
    assert fast != exam != story


def test_canvas_tour_prompt_embeds_tone_brief() -> None:
    """Voice-script user message carries the selected 讲解语气 brief."""
    nodes = [{"id": "topic", "text": "光合作用", "kind": "topic"}]
    socratic = build_canvas_tour_user_message(
        nodes,
        settings={"tone": "socratic", "language": "zh"},
        max_steps=8,
    )
    fast = build_canvas_tour_user_message(
        nodes,
        settings={"tone": "fast", "language": "zh"},
        max_steps=8,
    )
    assert "tone_brief" in socratic
    assert TONE_TABLE_HEADER_ZH in socratic
    assert "【苏格拉底】" in socratic
    assert "【速讲】" in fast
    assert "只丢问题不解答" in socratic
    assert "不铺垫" in fast


def test_slide_planner_prompt_embeds_tone_brief() -> None:
    """Slide teacher_script planning follows the same 讲解语气 brief."""
    outline = {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]}
    story = build_open_planner_message(
        outline,
        language="zh",
        diagram_title="光合作用",
        settings={"tone": "story", "language": "zh"},
    )
    assert "tone_brief" in story
    assert TONE_TABLE_HEADER_ZH in story
    assert "【讲故事】" in story
    assert "画面" in story
