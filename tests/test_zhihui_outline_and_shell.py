"""Tests for ZhiHui mind-map outline extract and Wan prompt shell."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.zhihui.focus import resolve_frame_focus_node_ids
from services.zhihui.lesson_deck import next_slide_index
from services.zhihui.lesson_planner import parse_lesson_plan_json
from services.zhihui.outline import MindMapBranchOutline, MindMapOutline, extract_mindmap_outline
from services.zhihui.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_SYSTEM,
    build_lesson_planner_user_message,
)
from services.zhihui.wan_prompt_shell import build_wan_batch_prompt, plan_batches_to_wan_jobs


def test_extract_hierarchical_outline() -> None:
    """Extract topic/branches from nested children mind-map JSON."""
    outline = extract_mindmap_outline(
        {
            "topic": "光合作用",
            "children": [
                {"text": "光反应", "children": [{"text": "叶绿体"}]},
                {"text": "暗反应", "children": []},
            ],
        }
    )
    assert outline.topic == "光合作用"
    assert len(outline.branches) == 2
    assert outline.branches[0].children == ["叶绿体"]


def test_extract_nodes_outline() -> None:
    """Extract outline from nodes/connections canvas shape."""
    outline = extract_mindmap_outline(
        {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "中心"},
                {"id": "b1", "type": "branch", "text": "分支一"},
                {"id": "c1", "type": "branch", "text": "子点"},
            ],
            "connections": [
                {"source": "topic", "target": "b1"},
                {"source": "b1", "target": "c1"},
            ],
        }
    )
    assert outline.topic == "中心"
    assert outline.branches[0].text == "分支一"
    assert outline.branches[0].children == ["子点"]


def test_extract_requires_branches() -> None:
    """Topic-only mind maps are rejected."""
    with pytest.raises(ValueError):
        extract_mindmap_outline({"topic": "只有主题"})


def test_next_slide_index_resume() -> None:
    """Resume after the highest persisted slide index."""
    assert next_slide_index([]) == 0
    assert next_slide_index([SimpleNamespace(slide_index=0), SimpleNamespace(slide_index=2)]) == 3
    assert next_slide_index([SimpleNamespace(slide_index=None)]) == 1


def test_resolve_frame_focus_topic_and_branch() -> None:
    """Slide 0 is whole-map; later frames resolve outline branch ids."""
    outline = MindMapOutline(
        topic="中心",
        branches=[
            MindMapBranchOutline(id="b1", text="分支一", children=["子点"]),
            MindMapBranchOutline(id="b2", text="分支二", children=[]),
        ],
    )
    assert not resolve_frame_focus_node_ids(outline, slide_index=0, focus_branch="b1")
    assert resolve_frame_focus_node_ids(outline, slide_index=1, batch_role="develop", focus_branch="分支二") == ["b2"]
    assert resolve_frame_focus_node_ids(outline, slide_index=2, batch_role="develop", focus_branch="b1") == ["b1"]
    assert not resolve_frame_focus_node_ids(outline, slide_index=3, batch_role="close", focus_branch="")


def test_parse_lesson_plan_json_ok() -> None:
    """Parse fenced JSON lesson plans and keep style/frame fields."""
    plan = parse_lesson_plan_json(
        """
        ```json
        {
          "style_seed": "课堂水彩",
          "batches": [
            {"batch_role": "open", "frames": [{"title": "导入", "lesson_beat": "好奇"}]}
          ]
        }
        ```
        """
    )
    assert plan["style_seed"] == "课堂水彩"
    assert plan["batches"][0]["frames"][0]["title"] == "导入"


def test_parse_lesson_plan_json_defaults_style() -> None:
    """Fill a default style seed when the planner omits it."""
    plan = parse_lesson_plan_json('{"batches":[{"frames":[{"title":"A","lesson_beat":"b"}]}]}')
    assert plan["style_seed"]


def test_parse_lesson_plan_json_rejects_empty() -> None:
    """Empty batch lists are invalid."""
    with pytest.raises(ValueError):
        parse_lesson_plan_json('{"batches":[]}')


def test_wan_shell_and_jobs() -> None:
    """Build Wan batch prompt shell and expand plan batches into jobs."""
    plan = {
        "style_seed": "水彩课堂风",
        "batches": [
            {
                "batch_role": "open",
                "frames": [
                    {
                        "title": "导入",
                        "frame_role": "topic_overview",
                        "lesson_beat": "引起好奇",
                        "learning_point": "光合作用把光能变成化学能",
                        "manifestation": "阳光照进叶片，气泡从水草升起",
                        "visual_subjects": ["阳光", "叶子"],
                    }
                ],
            },
            {
                "batch_role": "develop",
                "frames": [
                    {
                        "title": "真的只用光吗",
                        "frame_role": "cognitive_conflict",
                        "cognitive_conflict": True,
                        "lesson_beat": "挑战常见误解",
                        "learning_point": "暗反应不直接依赖光照但仍属光合整体",
                        "manifestation": "白天叶片 vs 夜间仍进行的碳固定对比",
                        "think_prompt": "没有光，植物还能「制造食物」吗？",
                        "visual_subjects": ["白天叶片", "夜间实验室"],
                        "focus_branch": "暗反应",
                    }
                ],
            },
        ],
    }
    jobs = plan_batches_to_wan_jobs(plan)
    assert len(jobs) == 2
    prompt = build_wan_batch_prompt(
        style_seed=plan["style_seed"],
        frames=jobs[0]["frames"],
        batch_role=jobs[0].get("batch_role", ""),
    )
    assert "水彩课堂风" in prompt
    assert "导入" in prompt
    assert "直接具象" in prompt
    assert "水彩课堂风" in jobs[0]["prompt"]
    conflict_prompt = jobs[1]["prompt"]
    assert "认知冲突" in conflict_prompt
    assert "思考问句" in conflict_prompt


def test_lesson_planner_user_message_has_pedagogy() -> None:
    """Planner user payload reinforces topic→branch→conflict pedagogy."""
    assert "topic_overview" in LESSON_PLANNER_SYSTEM
    assert "cognitive_conflict" in LESSON_PLANNER_SYSTEM
    assert "批判性思维" in LESSON_PLANNER_SYSTEM
    message = build_lesson_planner_user_message(
        {"topic": "中心", "branches": [{"id": "b1", "text": "分支", "children": ["子"]}]},
        language="zh",
        diagram_title="示例",
    )
    assert "branch_intro" in message
    assert "cognitive_conflict" in message
