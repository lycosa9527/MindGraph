"""Familiarity-level briefs must differ for 初识 / 复习巩固 / 备课讲授."""

from __future__ import annotations

from services.mind_classroom.outline import canvas_place_code
from services.mind_classroom.prompts.canvas_tour_prompts import build_canvas_tour_user_message
from services.mind_classroom.prompts.lesson_planner_prompts import build_open_planner_message
from services.mind_classroom.prompts.mastery_prompts import (
    mastery_brief,
    mastery_label,
    normalize_mastery,
    skip_forced_choice_frame,
)


def test_normalize_mastery_defaults_to_first_look() -> None:
    """Unknown or empty mastery falls back to first look."""
    assert normalize_mastery("") == "first_look"
    assert normalize_mastery("nope") == "first_look"
    assert normalize_mastery("teach") == "teach"


def test_three_mastery_briefs_are_distinct() -> None:
    """Each familiarity level has its own teaching contract."""
    first = mastery_brief("first_look", "zh")
    review = mastery_brief("review", "zh")
    teach = mastery_brief("teach", "zh")
    assert mastery_label("first_look", "zh") == "初识"
    assert mastery_label("review", "zh") == "复习巩固"
    assert mastery_label("teach", "zh") == "备课讲授"
    assert "第一次看" in first
    assert "已经看过" in review
    assert "教别人" in teach
    assert first != review != teach
    assert skip_forced_choice_frame("first_look")
    assert not skip_forced_choice_frame("teach")


def test_canvas_tour_prompt_embeds_mastery_brief() -> None:
    """Voice-script user message carries the selected familiarity brief."""
    nodes = [{"id": "topic", "text": "光合作用", "kind": "topic"}]
    first = build_canvas_tour_user_message(
        nodes,
        settings={"mastery": "first_look", "language": "zh"},
        max_steps=8,
    )
    teach = build_canvas_tour_user_message(
        nodes,
        settings={"mastery": "teach", "language": "zh", "audience_title": "高一"},
        max_steps=8,
    )
    assert "mastery_brief" in first
    assert "第一次看" in first
    assert "教别人" in teach
    assert "第一次看" not in teach
    assert "tour_scope_brief" in first
    assert "tour_scope_brief" in teach
    assert "按主分支" in first
    assert "10～16 句" not in first
    deep = build_canvas_tour_user_message(
        nodes,
        settings={"mastery": "teach", "language": "zh", "tour_scope": "each_node"},
        max_steps=20,
    )
    assert "逐个节点" in deep
    assert "stop=leaf" in deep
    assert "6～10 句" not in deep


def test_slide_planner_prompt_embeds_mastery_brief() -> None:
    """Slide teacher_script planning follows the same familiarity brief."""
    outline = {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]}
    review = build_open_planner_message(
        outline,
        language="zh",
        diagram_title="光合作用",
        settings={"mastery": "review", "language": "zh"},
    )
    assert "mastery_brief" in review
    assert "已经看过" in review
    assert "合上图" in review or "复述" in review


def test_canvas_place_code_from_branch_prefixes() -> None:
    """Without Y, only name the side so clockwise left order cannot flip top/bottom."""
    by_id = {
        "topic": {"id": "topic"},
        "branch-r-1-0": {"id": "branch-r-1-0"},
        "branch-l-1-5": {"id": "branch-l-1-5"},
    }
    siblings = ["branch-r-1-0", "branch-l-1-5"]
    assert canvas_place_code("topic", by_id, "topic", siblings) == "center"
    assert canvas_place_code("branch-r-1-0", by_id, "topic", siblings) == "right"
    assert canvas_place_code("branch-l-1-5", by_id, "topic", siblings) == "left"


def test_canvas_place_code_from_positions() -> None:
    """With positions, name the quadrant relative to the topic."""
    by_id = {
        "topic": {"id": "topic", "position": {"x": 0, "y": 0}},
        "branch-r-1-0": {"id": "branch-r-1-0", "position": {"x": 200, "y": -80}},
        "branch-r-1-5": {"id": "branch-r-1-5", "position": {"x": 200, "y": 80}},
        "branch-l-1-5": {"id": "branch-l-1-5", "position": {"x": -200, "y": 80}},
        "branch-l-1-0": {"id": "branch-l-1-0", "position": {"x": -200, "y": -80}},
    }
    siblings = ["branch-r-1-0", "branch-r-1-5", "branch-l-1-5", "branch-l-1-0"]
    assert canvas_place_code("branch-r-1-0", by_id, "topic", siblings) == "right_top"
    assert canvas_place_code("branch-r-1-5", by_id, "topic", siblings) == "right_bottom"
    assert canvas_place_code("branch-l-1-0", by_id, "topic", siblings) == "left_top"
    assert canvas_place_code("branch-l-1-5", by_id, "topic", siblings) == "left_bottom"
