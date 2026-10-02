"""思维讲堂 prompts follow the diagram type and its node roles."""

from __future__ import annotations

from services.mind_classroom.deep_outline import build_tour_nodes
from services.mind_classroom.node_roles import lecture_role
from services.mind_classroom.prompts.canvas_tour_prompts import (
    build_canvas_tour_system_message,
    build_canvas_tour_user_message,
)
from services.mind_classroom.prompts.diagram_prompts import diagram_brief
from services.mind_classroom.prompts.lesson_planner_prompts import (
    build_branch_planner_message,
    build_close_planner_message,
    build_open_planner_message,
)
from services.mind_classroom.prompts.lesson_writers import lesson_writer
from services.mind_classroom.prompts.tour_scope_prompts import tour_scope_brief


def test_circle_brief_teaches_association_not_branches() -> None:
    """Circle map lecture names context associations, not mind-map branches."""
    brief = diagram_brief("circle_map", "zh")
    system = build_canvas_tour_system_message(
        {"diagram_type": "circle_map", "language": "zh", "mastery": "first_look", "tone": "classroom"}
    )
    assert "联想" in brief
    assert "没有上下级" in brief
    assert "图示：圆圈图" in system
    assert "思维导图" not in brief


def test_each_diagram_brief_names_its_own_focus() -> None:
    """The ten lecture diagrams do not share one thinking focus."""
    marks = {
        "mind_map": "放射",
        "circle_map": "联想",
        "bubble_map": "属性",
        "double_bubble_map": "比较",
        "tree_map": "分类维度",
        "brace_map": "整体与部分",
        "flow_map": "顺序",
        "multi_flow_map": "原因和结果",
        "bridge_map": "类比",
        "concept_map": "概念之间的关系",
    }
    briefs = [diagram_brief(diagram_type, "zh") for diagram_type in marks]
    assert len(set(briefs)) == len(briefs)
    for diagram_type, mark in marks.items():
        assert mark in diagram_brief(diagram_type, "zh")


def test_circle_tour_nodes_are_context_roles() -> None:
    """A circle map with no edges still tours each association as context."""
    spec = {
        "type": "circle_map",
        "nodes": [
            {"id": "topic", "type": "center", "text": "水", "position": {"x": 0, "y": 0}},
            {"id": "outer-boundary", "type": "boundary", "text": "", "position": {"x": 0, "y": 0}},
            {"id": "ctx-1", "type": "bubble", "text": "蒸发", "position": {"x": 40, "y": 0}},
            {"id": "ctx-2", "type": "bubble", "text": "降雨", "position": {"x": -40, "y": 0}},
        ],
        "connections": [],
    }
    nodes = build_tour_nodes(spec, deep=False)
    roles = {node["text"]: node["role"] for node in nodes}
    assert roles["水"] == "topic"
    assert roles["蒸发"] == "context"
    assert roles["降雨"] == "context"
    assert "" not in roles
    user = build_canvas_tour_user_message(
        nodes,
        settings={"diagram_type": "circle_map", "language": "zh"},
        max_steps=12,
    )
    assert "diagram_brief" in user
    assert "圆圈图" in user
    assert '"role": "context"' in user
    system = build_canvas_tour_system_message({"diagram_type": "circle_map", "language": "zh"})
    assert "按本图示的主节点" not in system
    assert "主分支不拆子步" not in system


def test_circle_tour_starts_at_the_top_and_goes_clockwise() -> None:
    """Satellites are listed from 12 o'clock, then clockwise, not node-list order."""
    spec = {
        "type": "circle_map",
        "nodes": [
            {"id": "topic", "type": "center", "text": "水", "position": {"x": 0, "y": 0}},
            {"id": "bottom", "type": "bubble", "text": "下", "position": {"x": 0, "y": 80}},
            {"id": "left", "type": "bubble", "text": "左", "position": {"x": -80, "y": 0}},
            {"id": "top", "type": "bubble", "text": "上", "position": {"x": 0, "y": -80}},
            {"id": "right", "type": "bubble", "text": "右", "position": {"x": 80, "y": 0}},
        ],
        "connections": [],
    }
    texts = [node["text"] for node in build_tour_nodes(spec, deep=False)]
    assert texts == ["水", "上", "右", "下", "左"]


def test_multi_flow_tour_includes_causes_before_effects() -> None:
    """Causes point at the event, so a child-only walk used to drop them."""
    spec = {
        "type": "multi_flow_map",
        "nodes": [
            {"id": "event", "type": "topic", "text": "迟到", "position": {"x": 0, "y": 0}},
            {
                "id": "cause-1",
                "type": "flow",
                "text": "堵车",
                "position": {"x": -80, "y": 0},
                "data": {"multiFlowRole": "cause"},
            },
            {
                "id": "effect-1",
                "type": "flow",
                "text": "错过课",
                "position": {"x": 80, "y": 0},
                "data": {"multiFlowRole": "effect"},
            },
        ],
        "connections": [
            {"source": "cause-1", "target": "event"},
            {"source": "event", "target": "effect-1"},
        ],
    }
    texts = [node["text"] for node in build_tour_nodes(spec, deep=False)]
    assert texts.index("堵车") < texts.index("错过课")
    roles = {node["text"]: node["role"] for node in build_tour_nodes(spec, deep=False)}
    assert roles["迟到"] == "event"
    assert roles["堵车"] == "cause"
    assert roles["错过课"] == "effect"


def test_double_bubble_tour_keeps_both_sides() -> None:
    """Right-side differences are not children of the left topic."""
    spec = {
        "type": "double_bubble_map",
        "nodes": [
            {"id": "left-topic", "type": "topic", "text": "猫", "position": {"x": 0, "y": 0}},
            {"id": "right-topic", "type": "topic", "text": "狗", "position": {"x": 200, "y": 0}},
            {
                "id": "sim-1",
                "type": "bubble",
                "text": "宠物",
                "data": {"doubleBubbleRole": "similarity"},
                "position": {"x": 100, "y": 0},
            },
            {
                "id": "ld-1",
                "type": "bubble",
                "text": "喵",
                "data": {"doubleBubbleRole": "leftDiff"},
                "position": {"x": -40, "y": 0},
            },
            {
                "id": "rd-1",
                "type": "bubble",
                "text": "汪",
                "data": {"doubleBubbleRole": "rightDiff"},
                "position": {"x": 240, "y": 0},
            },
        ],
        "connections": [
            {"source": "left-topic", "target": "sim-1"},
            {"source": "right-topic", "target": "sim-1"},
            {"source": "left-topic", "target": "ld-1"},
            {"source": "right-topic", "target": "rd-1"},
        ],
    }
    roles = {node["text"]: node["role"] for node in build_tour_nodes(spec, deep=False)}
    assert roles["猫"] == "left_topic"
    assert roles["狗"] == "right_topic"
    assert roles["宠物"] == "similarity"
    assert roles["喵"] == "left_diff"
    assert roles["汪"] == "right_diff"
    right = next(node for node in build_tour_nodes(spec, deep=False) if node["text"] == "狗")
    assert right["walk"] == "opening"


def test_tree_dimension_is_a_lecture_node() -> None:
    """The classification dimension is content, not a skipped label."""
    spec = {
        "type": "tree_map",
        "nodes": [
            {"id": "tree-topic", "type": "topic", "text": "动物", "position": {"x": 0, "y": 0}},
            {"id": "dimension-label", "type": "label", "text": "食性", "position": {"x": 0, "y": 40}},
            {"id": "cat-1", "type": "branch", "text": "肉食", "position": {"x": 80, "y": 0}},
            {"id": "item-1", "type": "branch", "text": "虎", "position": {"x": 140, "y": 0}},
        ],
        "connections": [
            {"source": "tree-topic", "target": "cat-1"},
            {"source": "cat-1", "target": "item-1"},
        ],
    }
    roles = {node["text"]: node["role"] for node in build_tour_nodes(spec, deep=True)}
    assert roles["动物"] == "topic"
    assert roles["食性"] == "dimension"
    assert roles["肉食"] == "category"
    assert roles["虎"] == "item"


def test_tree_tour_walks_the_left_group_before_the_right() -> None:
    """Categories are groups. The leftmost group, then its items, then the next group."""
    spec = {
        "type": "tree_map",
        "nodes": [
            {"id": "tree-topic", "type": "topic", "text": "动物", "position": {"x": 0, "y": 0}},
            {"id": "dimension-label", "type": "label", "text": "食性", "position": {"x": 0, "y": 40}},
            {"id": "cat-right", "type": "branch", "text": "草食", "position": {"x": 200, "y": 80}},
            {"id": "item-right", "type": "branch", "text": "牛", "position": {"x": 200, "y": 140}},
            {"id": "cat-left", "type": "branch", "text": "肉食", "position": {"x": -80, "y": 80}},
            {"id": "item-left", "type": "branch", "text": "虎", "position": {"x": -80, "y": 140}},
        ],
        "connections": [
            {"source": "tree-topic", "target": "cat-right"},
            {"source": "cat-right", "target": "item-right"},
            {"source": "tree-topic", "target": "cat-left"},
            {"source": "cat-left", "target": "item-left"},
        ],
    }
    nodes = build_tour_nodes(spec, deep=True)
    texts = [node["text"] for node in nodes]
    assert texts == ["动物", "食性", "肉食", "虎", "草食", "牛"]
    dimension = next(node for node in nodes if node["text"] == "食性")
    assert dimension["walk"] == "opening"
    assert lecture_role("concept_map", {"id": "c1", "type": "branch", "text": "冰"}, topic_id="topic") == "concept"


def test_bridge_tour_is_one_node_per_pair() -> None:
    """A pair is one step. The right side is named on the left node, and the factor opens the tour."""
    spec = {
        "type": "bridge_map",
        "nodes": [
            {"id": "dimension-label", "type": "label", "text": "如同", "position": {"x": 0, "y": 0}},
            {
                "id": "l1",
                "type": "bridge",
                "text": "鞋",
                "position": {"x": 0, "y": 40},
                "data": {"pairIndex": 0, "position": "left"},
            },
            {
                "id": "r1",
                "type": "bridge",
                "text": "脚",
                "position": {"x": 80, "y": 40},
                "data": {"pairIndex": 0, "position": "right"},
            },
            {
                "id": "l2",
                "type": "bridge",
                "text": "帽",
                "position": {"x": 0, "y": 120},
                "data": {"pairIndex": 1, "position": "left"},
            },
            {
                "id": "r2",
                "type": "bridge",
                "text": "头",
                "position": {"x": 80, "y": 120},
                "data": {"pairIndex": 1, "position": "right"},
            },
        ],
        "connections": [],
    }
    nodes = build_tour_nodes(spec, deep=False)
    texts = [node["text"] for node in nodes]
    assert texts == ["如同", "鞋", "帽"]
    shoe = next(node for node in nodes if node["text"] == "鞋")
    assert shoe["child_texts"] == ["脚"]
    assert "r1" in shoe["descendant_ids"]
    assert next(node for node in nodes if node["text"] == "如同")["walk"] == "opening"


def test_each_diagram_writer_splits_overview_step_and_closing() -> None:
    """Opening, a step, and closing are different instructions on every diagram."""
    for diagram_type in (
        "mind_map",
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "concept_map",
    ):
        parts = lesson_writer(diagram_type, "zh")
        assert parts.overview != parts.step
        assert parts.step != parts.closing
        assert parts.planner_open != parts.planner_develop
        assert parts.planner_develop != parts.planner_close


def test_circle_writer_is_what_the_canvas_and_planner_use() -> None:
    """Circle map prompts take the circle writer, not the mind-map branch script."""
    settings = {"diagram_type": "circle_map", "language": "zh", "tour_scope": "main_branch"}
    user = build_canvas_tour_user_message(
        [{"id": "topic", "text": "水", "role": "topic"}],
        settings=settings,
        max_steps=8,
    )
    assert "lesson_overview" in user
    assert "一条联想" in user
    assert "全部一级主分支" not in user
    scope = tour_scope_brief("main_branch", "zh", "circle_map")
    assert "一条联想" in scope
    assert "子点不拆步" not in scope
    outline = {"topic": "水", "branches": [{"id": "ctx-1", "text": "蒸发", "children": []}]}
    develop = build_branch_planner_message(
        outline,
        outline["branches"][0],
        style_seed="flat",
        branch_index=1,
        branch_total=1,
        settings=settings,
    )
    opened = build_open_planner_message(outline, settings=settings)
    closed = build_close_planner_message(outline, style_seed="flat", settings=settings)
    assert "一条联想" in develop
    assert "按 children 顺序" not in develop
    assert "联想到什么" in opened
    assert "所处的情境" in closed
    mind = build_branch_planner_message(
        outline,
        outline["branches"][0],
        style_seed="flat",
        branch_index=1,
        branch_total=1,
        settings={"diagram_type": "mind_map", "language": "zh"},
    )
    assert "branch_intro" in mind
    assert develop != mind
