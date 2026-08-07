"""Branch-order tests: clockwise right top→bottom, then left bottom→top."""

from __future__ import annotations

import pytest

from services.zhihui.lesson_planner import reorder_develop_batches_to_outline
from services.zhihui.outline import (
    MindMapBranchOutline,
    MindMapOutline,
    extract_mindmap_outline,
    sort_topic_branch_ids_clockwise,
)


def _node(node_id: str, text: str, x: float, y: float, *, node_type: str = "branch") -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "text": text,
        "position": {"x": x, "y": y},
    }


def _sams_club_style_spec() -> dict:
    """
    Large mind map shaped like the user screenshot: 4 right + 4 left.

    Visual reading (clockwise):
      R1 竞争对手 (top-right) … R4 营销聚焦 (bottom-right)
      then L4 运营 (bottom-left) … L1 汇源 (top-left).
    Connection list is intentionally scrambled.
    """
    topic = _node("topic", "山姆会员商店", 0, 400, node_type="topic")
    right = [
        _node("branch-r-1-0", "竞争对手", 320, 80),
        _node("branch-r-1-1", "分布特点", 320, 220),
        _node("branch-r-1-2", "产品与货品策略", 320, 360),
        _node("branch-r-1-3", "营销聚焦", 320, 500),
    ]
    left = [
        # Canvas stores left stack top→bottom.
        _node("branch-l-1-0", "汇源汁商店", -320, 80),
        _node("branch-l-1-1", "Costco对比", -320, 220),
        _node("branch-l-1-2", "店内体验与多渠道", -320, 360),
        _node("branch-l-1-3", "运营与精益管理", -320, 500),
    ]
    nodes = [topic, *right, *left]
    # Scrambled connection order (not clockwise).
    targets = [
        "branch-l-1-2",
        "branch-r-1-3",
        "branch-l-1-0",
        "branch-r-1-0",
        "branch-l-1-3",
        "branch-r-1-1",
        "branch-l-1-1",
        "branch-r-1-2",
    ]
    connections = [{"source": "topic", "target": tid} for tid in targets]
    return {"nodes": nodes, "connections": connections}


EXPECTED_SAMS_CLOCKWISE = [
    "竞争对手",
    "分布特点",
    "产品与货品策略",
    "营销聚焦",
    "运营与精益管理",
    "店内体验与多渠道",
    "Costco对比",
    "汇源汁商店",
]


def test_sams_club_style_eight_branches_clockwise() -> None:
    """8 L1 branches: top-right first, down the right, then left bottom→up."""
    outline = extract_mindmap_outline(_sams_club_style_spec())
    assert [branch.text for branch in outline.branches] == EXPECTED_SAMS_CLOCKWISE
    assert [branch.id for branch in outline.branches] == [
        "branch-r-1-0",
        "branch-r-1-1",
        "branch-r-1-2",
        "branch-r-1-3",
        "branch-l-1-3",
        "branch-l-1-2",
        "branch-l-1-1",
        "branch-l-1-0",
    ]


def test_sams_club_style_without_side_id_prefixes() -> None:
    """Same layout with generic ids still uses geometric side-of-topic order."""
    spec = _sams_club_style_spec()
    rename = {
        "branch-r-1-0": "r0",
        "branch-r-1-1": "r1",
        "branch-r-1-2": "r2",
        "branch-r-1-3": "r3",
        "branch-l-1-0": "l0",
        "branch-l-1-1": "l1",
        "branch-l-1-2": "l2",
        "branch-l-1-3": "l3",
    }
    for node in spec["nodes"]:
        if node["id"] in rename:
            node["id"] = rename[node["id"]]
    for conn in spec["connections"]:
        conn["target"] = rename[conn["target"]]
    outline = extract_mindmap_outline(spec)
    assert [branch.text for branch in outline.branches] == EXPECTED_SAMS_CLOCKWISE


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, ["1"]),
        (2, ["1", "2"]),  # right:1 ; left bottom→up:2
        (3, ["1", "2", "3"]),  # right 1,2 ; left 3
        (4, ["1", "2", "3", "4"]),
        (5, ["1", "2", "3", "4", "5"]),
        (6, ["1", "2", "3", "4", "5", "6"]),
        (7, ["1", "2", "3", "4", "5", "6", "7"]),
        (8, ["1", "2", "3", "4", "5", "6", "7", "8"]),
    ],
)
def test_distribute_style_n_branches_clockwise(count: int, expected: list[str]) -> None:
    """
    Mirror canvas distributeBranchesClockwise: first ceil(n/2) on right top→bottom,
    remaining on left stored top→bottom so clockwise reads left bottom→top.
    """
    mid = (count + 1) // 2
    right_labels = [str(i) for i in range(1, mid + 1)]
    left_clockwise = [str(i) for i in range(mid + 1, count + 1)]  # bottom→top reading
    # Canvas left stack is top→bottom = reverse of left_clockwise.
    left_stack = list(reversed(left_clockwise))

    nodes = [_node("topic", "中心", 0, 200, node_type="topic")]
    connections: list[dict] = []
    for index, label in enumerate(right_labels):
        node_id = f"branch-r-1-{index}"
        nodes.append(_node(node_id, label, 200, 40 + index * 60))
        connections.append({"source": "topic", "target": node_id})
    for index, label in enumerate(left_stack):
        node_id = f"branch-l-1-{index}"
        nodes.append(_node(node_id, label, -200, 40 + index * 60))
        connections.append({"source": "topic", "target": node_id})

    # Scramble connections for N>1.
    if len(connections) > 1:
        connections = list(reversed(connections))

    outline = extract_mindmap_outline({"nodes": nodes, "connections": connections})
    assert [branch.text for branch in outline.branches] == expected


def test_equal_x_counts_as_right_column() -> None:
    """Nodes with x == topic.x are treated as right-side (x >= topic.x)."""
    outline = extract_mindmap_outline(
        {
            "nodes": [
                _node("topic", "中心", 0, 100, node_type="topic"),
                _node("mid-top", "轴上上", 0, 20),
                _node("mid-bot", "轴上下", 0, 180),
                _node("left", "左侧", -100, 100),
            ],
            "connections": [
                {"source": "topic", "target": "left"},
                {"source": "topic", "target": "mid-bot"},
                {"source": "topic", "target": "mid-top"},
            ],
        }
    )
    assert [branch.text for branch in outline.branches] == ["轴上上", "轴上下", "左侧"]


def test_prefix_order_without_positions() -> None:
    """Without positions, branch-r/l prefixes still yield right then reversed left."""
    outline = extract_mindmap_outline(
        {
            "nodes": [
                {"id": "topic", "type": "topic", "text": "中心"},
                {"id": "branch-r-1-0", "type": "branch", "text": "R1"},
                {"id": "branch-r-1-1", "type": "branch", "text": "R2"},
                {"id": "branch-l-1-0", "type": "branch", "text": "L_top"},
                {"id": "branch-l-1-1", "type": "branch", "text": "L_bot"},
            ],
            # Connection order = canvas storage: right top→bottom, left top→bottom.
            "connections": [
                {"source": "topic", "target": "branch-r-1-0"},
                {"source": "topic", "target": "branch-r-1-1"},
                {"source": "topic", "target": "branch-l-1-0"},
                {"source": "topic", "target": "branch-l-1-1"},
            ],
        }
    )
    # Left stack top→bottom reversed for clockwise continuation.
    assert [branch.text for branch in outline.branches] == ["R1", "R2", "L_bot", "L_top"]


def test_sort_topic_branch_ids_clockwise_direct() -> None:
    """Unit helper: geometric path ignores scrambled child_ids list order."""
    by_id = {
        "topic": _node("topic", "T", 0, 0, node_type="topic"),
        "a": _node("a", "右下", 10, 10),
        "b": _node("b", "右上", 10, -10),
        "c": _node("c", "左下", -10, 10),
        "d": _node("d", "左上", -10, -10),
    }
    ordered = sort_topic_branch_ids_clockwise(["c", "a", "d", "b"], by_id, "topic")
    assert ordered == ["b", "a", "c", "d"]


def test_planner_reorder_follows_outline_clockwise() -> None:
    """Develop batches are sorted to the outline clockwise branch list."""
    outline = MindMapOutline(
        topic="山姆会员商店",
        branches=[MindMapBranchOutline(id=f"b{i}", text=text) for i, text in enumerate(EXPECTED_SAMS_CLOCKWISE)],
    )
    # Planner emitted branches out of order (left first, then right reversed).
    shuffled = list(reversed(EXPECTED_SAMS_CLOCKWISE))
    plan = {
        "style_seed": "课堂",
        "batches": [{"batch_role": "open", "frames": [{"title": "开场", "focus_branch": ""}]}]
        + [
            {
                "batch_role": "develop",
                "frames": [{"title": text, "focus_branch": text}],
            }
            for text in shuffled
        ]
        + [{"batch_role": "close", "frames": [{"title": "收束", "focus_branch": ""}]}],
    }
    reordered = reorder_develop_batches_to_outline(plan, outline)
    develop_titles = [
        batch["frames"][0]["title"] for batch in reordered["batches"] if batch.get("batch_role") == "develop"
    ]
    assert develop_titles == EXPECTED_SAMS_CLOCKWISE
