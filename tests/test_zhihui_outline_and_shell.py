"""Tests for ZhiHui mind-map outline extract and Wan prompt shell."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.zhihui import lesson_planner as planner_mod
from services.zhihui.focus import resolve_frame_focus_node_ids
from services.zhihui.lesson_deck import iter_batch_resume_ranges, next_slide_index
from services.zhihui.lesson_planner import (
    parse_lesson_plan_json,
    plan_lesson_from_outline,
    planner_max_tokens,
    reorder_develop_batches_to_outline,
)
from services.zhihui.outline import MindMapBranchOutline, MindMapOutline, extract_mindmap_outline
from services.zhihui.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_SYSTEM,
    build_branch_planner_message,
    build_close_planner_message,
    build_lesson_planner_user_message,
    build_open_planner_message,
)
from services.zhihui.prompts.wan_image_shell import WAN_IMAGE_SHELL
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


def test_extract_nodes_outline_clockwise() -> None:
    """First-level branches follow canvas clockwise: right top→bottom, left bottom→top."""
    outline = extract_mindmap_outline(
        {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "中心", "position": {"x": 0, "y": 100}},
                {
                    "id": "branch-r-1-0",
                    "type": "branch",
                    "text": "右下",
                    "position": {"x": 200, "y": 200},
                },
                {
                    "id": "branch-r-1-1",
                    "type": "branch",
                    "text": "右上",
                    "position": {"x": 200, "y": 40},
                },
                {
                    "id": "branch-l-1-0",
                    "type": "branch",
                    "text": "左下",
                    "position": {"x": -200, "y": 220},
                },
                {
                    "id": "branch-l-1-1",
                    "type": "branch",
                    "text": "左上",
                    "position": {"x": -200, "y": 50},
                },
            ],
            # Connection order intentionally not clockwise.
            "connections": [
                {"source": "topic", "target": "branch-r-1-0"},
                {"source": "topic", "target": "branch-r-1-1"},
                {"source": "topic", "target": "branch-l-1-0"},
                {"source": "topic", "target": "branch-l-1-1"},
            ],
        }
    )
    assert [branch.text for branch in outline.branches] == ["右上", "右下", "左下", "左上"]
    assert outline.to_planner_payload()["branch_order"] == "clockwise"


def test_extract_nodes_outline_clockwise_without_side_prefixes() -> None:
    """Geometric side-of-topic order works without branch-r/l id prefixes."""
    outline = extract_mindmap_outline(
        {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "中心", "position": {"x": 0, "y": 100}},
                {"id": "a", "type": "branch", "text": "右下", "position": {"x": 200, "y": 200}},
                {"id": "b", "type": "branch", "text": "右上", "position": {"x": 200, "y": 40}},
                {"id": "c", "type": "branch", "text": "左下", "position": {"x": -200, "y": 220}},
                {"id": "d", "type": "branch", "text": "左上", "position": {"x": -200, "y": 50}},
            ],
            "connections": [
                {"source": "topic", "target": "a"},
                {"source": "topic", "target": "b"},
                {"source": "topic", "target": "c"},
                {"source": "topic", "target": "d"},
            ],
        }
    )
    assert [branch.text for branch in outline.branches] == ["右上", "右下", "左下", "左上"]


def test_extract_left_right_hierarchical_clockwise() -> None:
    """leftBranches are stored top→bottom; outline reverses them for clockwise."""
    outline = extract_mindmap_outline(
        {
            "topic": "中心",
            "rightBranches": [{"text": "1"}, {"text": "2"}],
            "leftBranches": [{"text": "4"}, {"text": "3"}],  # top→bottom on canvas
        }
    )
    assert [branch.text for branch in outline.branches] == ["1", "2", "3", "4"]


def test_extract_requires_branches() -> None:
    """Topic-only mind maps are rejected."""
    with pytest.raises(ValueError):
        extract_mindmap_outline({"topic": "只有主题"})


def test_next_slide_index_resume() -> None:
    """Resume at first missing index; backfill holes before max+1."""
    assert next_slide_index([]) == 0
    assert next_slide_index([SimpleNamespace(slide_index=0), SimpleNamespace(slide_index=2)]) == 1
    assert next_slide_index([SimpleNamespace(slide_index=0), SimpleNamespace(slide_index=1)]) == 2
    assert next_slide_index([SimpleNamespace(slide_index=None)]) == 1
    assert (
        next_slide_index(
            [
                SimpleNamespace(slide_index=0),
                SimpleNamespace(slide_index=1),
                SimpleNamespace(slide_index=3),
            ]
        )
        == 2
    )


def test_iter_batch_resume_ranges_mid_deck() -> None:
    """Resume slide 5 with batches [4,4,3] skips batch 0 and one frame of batch 1."""
    ranges = iter_batch_resume_ranges([4, 4, 3], resume_slide=5)
    assert ranges == [
        (0, 4, 4, 4),
        (4, 8, 1, 4),
        (8, 11, 0, 3),
    ]
    # Fully done: every batch skipped.
    done = iter_batch_resume_ranges([4, 4, 3], resume_slide=11)
    assert all(skip == count for _, _, skip, count in done)
    # Fresh run: no skips.
    fresh = iter_batch_resume_ranges([4, 4, 3], resume_slide=0)
    assert all(skip == 0 for _, _, skip, _ in fresh)


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


def test_parse_lesson_plan_json_flags_truncated() -> None:
    """Truncated mid-string JSON surfaces a clearer decode error."""
    truncated = (
        '{"style_seed":"课堂水彩","batches":[{"batch_role":"open","frames":'
        '[{"title":"导入","lesson_beat":"好奇","manifestation":"半截'
    )
    with pytest.raises(json.JSONDecodeError, match="likely truncated"):
        parse_lesson_plan_json(truncated)


def test_planner_max_tokens_default() -> None:
    """Per-phase planner budget stays modest (full deck is multi-call)."""
    assert planner_max_tokens() == 2500


@pytest.mark.asyncio
async def test_plan_lesson_from_outline_is_branch_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Open + one call per branch + close; merged plan stays clockwise."""
    outline = MindMapOutline(
        topic="中心",
        branches=[
            MindMapBranchOutline(id="b1", text="分支一", children=["子点"]),
            MindMapBranchOutline(id="b2", text="分支二", children=[]),
        ],
    )
    calls: list[str] = []
    progress_events: list[dict] = []

    async def fake_chat(**kwargs):
        prompt = str(kwargs.get("prompt") or "")
        calls.append(prompt)
        if "阶段：开场" in prompt:
            body = {
                "style_seed": "课堂水彩",
                "batches": [
                    {
                        "batch_role": "open",
                        "frames": [
                            {
                                "title": "钩子",
                                "frame_role": "topic_overview",
                                "focus_branch": "",
                                "focus_child": "",
                                "lesson_beat": "好奇",
                                "learning_point": "点",
                                "manifestation": "场景",
                                "think_prompt": "为什么？",
                                "teacher_script": "今天我们一起聊聊这个主题，先抛个问题。",
                                "visual_subjects": ["a", "b", "c"],
                                "cognitive_conflict": False,
                            }
                        ],
                    }
                ],
            }
        elif "阶段：单分支展开" in prompt:
            focus = "b1" if "分支一" in prompt else "b2"
            body = {
                "batches": [
                    {
                        "batch_role": "develop",
                        "frames": [
                            {
                                "title": f"{focus}-intro",
                                "frame_role": "branch_intro",
                                "focus_branch": focus,
                                "focus_child": "",
                                "lesson_beat": "画像",
                                "learning_point": "点",
                                "manifestation": "类比",
                                "think_prompt": "",
                                "teacher_script": f"接下来我们聚焦{focus}这条线。",
                                "visual_subjects": ["a", "b", "c"],
                                "cognitive_conflict": False,
                            }
                        ],
                    }
                ],
            }
        else:
            body = {
                "batches": [
                    {
                        "batch_role": "close",
                        "frames": [
                            {
                                "title": "收束",
                                "frame_role": "synthesis",
                                "focus_branch": "",
                                "focus_child": "",
                                "lesson_beat": "金句",
                                "learning_point": "收获",
                                "manifestation": "大图",
                                "think_prompt": "",
                                "teacher_script": "最后用一句金句把今天的主线收住。",
                                "visual_subjects": ["a", "b", "c"],
                                "cognitive_conflict": False,
                            }
                        ],
                    }
                ],
            }
        return json.dumps(body, ensure_ascii=False), {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }

    async def on_progress(payload: dict) -> None:
        progress_events.append(payload)

    monkeypatch.setattr(planner_mod.llm_service, "chat_with_usage", fake_chat)
    plan, usage = await plan_lesson_from_outline(outline, on_progress=on_progress)
    assert len(calls) == 4
    assert [batch["batch_role"] for batch in plan["batches"]] == ["open", "develop", "develop", "close"]
    assert plan["batches"][1]["frames"][0]["focus_branch"] == "b1"
    assert plan["batches"][2]["frames"][0]["focus_branch"] == "b2"
    assert plan["style_seed"] == "课堂水彩"
    assert usage is not None
    assert usage["total_tokens"] == 120
    assert any(event.get("planning_stage") == "develop" for event in progress_events)
    assert any(event.get("branch_index") == 2 for event in progress_events)


def test_reorder_develop_batches_to_outline() -> None:
    """Develop batches are permuted to match outline clockwise order."""
    outline = MindMapOutline(
        topic="中心",
        branches=[
            MindMapBranchOutline(id="b1", text="分支一"),
            MindMapBranchOutline(id="b2", text="分支二"),
            MindMapBranchOutline(id="b3", text="分支三"),
        ],
    )
    plan = {
        "style_seed": "课堂",
        "batches": [
            {"batch_role": "open", "frames": [{"title": "开场", "focus_branch": ""}]},
            {
                "batch_role": "develop",
                "frames": [{"title": "三", "focus_branch": "b3"}],
            },
            {
                "batch_role": "develop",
                "frames": [{"title": "一", "focus_branch": "分支一"}],
            },
            {
                "batch_role": "develop",
                "frames": [{"title": "二", "focus_branch": "b2"}],
            },
            {"batch_role": "close", "frames": [{"title": "收束", "focus_branch": ""}]},
        ],
    }
    reordered = reorder_develop_batches_to_outline(plan, outline)
    develop_titles = [
        batch["frames"][0]["title"] for batch in reordered["batches"] if batch.get("batch_role") == "develop"
    ]
    assert develop_titles == ["一", "二", "三"]
    assert reordered["batches"][0]["batch_role"] == "open"
    assert reordered["batches"][-1]["batch_role"] == "close"
    # Already correct order is a no-op.
    same = reorder_develop_batches_to_outline(reordered, outline)
    assert [
        batch["frames"][0]["title"] for batch in same["batches"] if batch.get("batch_role") == "develop"
    ] == develop_titles


def test_reorder_develop_batches_mixed_branch_uses_earliest() -> None:
    """Mixed-branch develop batches sort by the earliest outline branch they cover."""
    outline = MindMapOutline(
        topic="中心",
        branches=[
            MindMapBranchOutline(id="b1", text="分支一"),
            MindMapBranchOutline(id="b2", text="分支二"),
            MindMapBranchOutline(id="b3", text="分支三"),
        ],
    )
    plan = {
        "style_seed": "课堂",
        "batches": [
            {"batch_role": "open", "frames": [{"title": "开场"}]},
            {
                "batch_role": "develop",
                "frames": [
                    {"title": "三", "focus_branch": "b3"},
                    {"title": "一-late", "focus_branch": "b1"},
                ],
            },
            {
                "batch_role": "develop",
                "frames": [{"title": "二", "focus_branch": "b2"}],
            },
            {"batch_role": "close", "frames": [{"title": "收束"}]},
        ],
    }
    reordered = reorder_develop_batches_to_outline(plan, outline)
    develop = [batch for batch in reordered["batches"] if batch.get("batch_role") == "develop"]
    # Mixed batch covers b1+b3 → earliest is b1, so it sorts before pure b2.
    # Frames inside the mixed batch are also stable-sorted by branch rank.
    assert [frame["title"] for frame in develop[0]["frames"]] == ["一-late", "三"]
    assert develop[1]["frames"][0]["title"] == "二"


def test_iter_batch_resume_ranges_partial_skip_math() -> None:
    """skip_in_batch < frame_count means remaining frames must still run."""
    ranges = iter_batch_resume_ranges([4, 4, 3], resume_slide=5)
    assert ranges[0][2] == 4  # fully skipped
    assert ranges[1][2] == 1  # one frame already done
    remaining = ranges[1][3] - ranges[1][2]
    assert remaining == 3
    assert ranges[2][2] == 0


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
                        "teacher_script": "同学们今天先别急着下结论——暗反应真的完全不需要光吗？",
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
    # Teacher narration is UI-only — must not consume Wan's 5000-char budget.
    assert "同学们今天" not in conflict_prompt


def test_wan_prompt_excludes_teacher_script() -> None:
    """teacher_script is for the deck caption, not the Wan image prompt."""
    frames = [
        {
            "title": "导入",
            "frame_role": "topic_overview",
            "lesson_beat": "引起好奇",
            "learning_point": "核心点",
            "manifestation": "阳光场景",
            "teacher_script": "同学们，今天我们一起来聊聊光合作用。",
            "visual_subjects": ["阳光"],
        }
    ]
    prompt = build_wan_batch_prompt(style_seed="课堂", frames=frames, batch_role="open")
    assert "引起好奇" in prompt
    assert "同学们，今天我们一起来聊聊光合作用。" not in prompt
    assert "teacher_script" not in prompt


def test_lesson_planner_user_message_has_pedagogy() -> None:
    """Phase prompts keep mindmap-first craft; system keeps shared frame rules."""
    assert "topic_overview" in LESSON_PLANNER_SYSTEM
    assert "cognitive_conflict" in LESSON_PLANNER_SYSTEM
    assert "批判性思维" in LESSON_PLANNER_SYSTEM
    assert "teacher_script" in LESSON_PLANNER_SYSTEM
    open_msg = build_open_planner_message(
        {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]},
        language="zh",
        diagram_title="光合作用",
    )
    assert "反直觉" in open_msg
    assert "style_seed" in open_msg
    branch_msg = build_branch_planner_message(
        {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]},
        {"id": "b1", "text": "光反应", "children": []},
        style_seed="课堂水彩",
        branch_index=1,
        branch_total=1,
    )
    assert "branch_intro" in branch_msg
    assert "develop" in branch_msg
    close_msg = build_close_planner_message(
        {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]},
        style_seed="课堂水彩",
    )
    assert "金句" in close_msg
    # Compatibility alias still returns open-phase prompt.
    msg = build_lesson_planner_user_message(
        {"topic": "光合作用", "branches": [{"id": "b1", "text": "光反应", "children": []}]},
        language="zh",
        diagram_title="光合作用",
    )
    assert "开场" in msg or "open" in msg


def test_wan_shell_follows_mindmap_and_craft() -> None:
    """Wan shell keeps mindmap fidelity cues and anti-textbook craft."""
    assert "导图" in WAN_IMAGE_SHELL or "知识点" in WAN_IMAGE_SHELL
    assert "教科书" in WAN_IMAGE_SHELL
    assert "认知冲突" in WAN_IMAGE_SHELL
    assert "少字" in WAN_IMAGE_SHELL or "短标题" in WAN_IMAGE_SHELL
    message = build_branch_planner_message(
        {"topic": "中心", "branches": [{"id": "b1", "text": "分支", "children": ["子"]}]},
        {"id": "b1", "text": "分支", "children": ["子"]},
        style_seed="课堂",
        branch_index=1,
        branch_total=1,
    )
    assert "branch_intro" in message
    assert "cognitive_conflict" in message
