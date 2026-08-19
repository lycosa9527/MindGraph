"""prompt_to_diagram_result normalization."""

from __future__ import annotations

from agents.core.prompt_to_diagram_result import (
    coerce_prompt_to_diagram_spec,
    normalize_prompt_to_diagram_result,
)
from tests.smoke.mindmap_smoke_helpers import mindmap_spec_to_canvas


def test_normalize_wraps_bare_flow_map_spec() -> None:
    """Bare spec dict without diagram_type wrapper is normalized."""
    bare = {
        "title": "Process",
        "steps": ["A", "B"],
        "substeps": [],
    }
    result = normalize_prompt_to_diagram_result(bare)
    assert result is not None
    assert result["diagram_type"] == "flow_map"
    assert result["spec"] == bare


def test_normalize_preserves_wrapped_result() -> None:
    """Already-wrapped {diagram_type, spec} passes through."""
    wrapped = {
        "diagram_type": "mind_map",
        "spec": {"topic": "T", "children": []},
    }
    result = normalize_prompt_to_diagram_result(wrapped)
    assert result == wrapped


def test_coerce_numeric_topic_and_attributes_to_strings() -> None:
    """Vue Flow ``.trim`` requires string labels — numbers must be coerced."""
    coerced = coerce_prompt_to_diagram_spec(
        {
            "topic": 42,
            "attributes": [1, None, "ok"],
            "children": [{"text": 7, "children": [{"text": None}]}],
        },
        "mind_map",
    )
    assert coerced["topic"] == "42"
    assert coerced["attributes"] == ["1", "", "ok"]
    assert coerced["children"][0]["text"] == "7"
    assert coerced["children"][0]["children"][0]["text"] == ""


def test_coerce_string_children_to_text_objects() -> None:
    """LLM specs may emit a bare string child; wrap so canvas hydrate can assign uid."""
    coerced = coerce_prompt_to_diagram_spec(
        {
            "topic": "全息投影是什么",
            "children": [
                {
                    "text": "光学原理",
                    "children": ["光场重建与相位编码", {"text": "干涉记录"}],
                }
            ],
        },
        "mind_map",
    )
    children = coerced["children"][0]["children"]
    assert children[0] == {"text": "光场重建与相位编码"}
    assert children[1]["text"] == "干涉记录"


def test_coerce_holography_mind_map_and_side_arrays() -> None:
    """Real autocomplete shape plus saved left/right branch arrays stay objects."""
    coerced = coerce_prompt_to_diagram_spec(
        {
            "topic": "全息投影是什么",
            "children": [
                {
                    "text": "光学原理",
                    "children": ["光场重建与相位编码", {"text": "干涉记录", "children": ["参考光"]}],
                }
            ],
            "leftBranches": [{"text": "应用场景", "children": ["教学演示"]}],
            "right": [{"text": "技术挑战", "children": ["散斑噪声"]}],
        },
        "mind_map",
    )
    assert coerced["children"][0]["children"][0] == {"text": "光场重建与相位编码"}
    assert coerced["children"][0]["children"][1]["children"][0]["text"] == "参考光"
    assert coerced["leftBranches"][0]["children"][0] == {"text": "教学演示"}
    assert coerced["right"][0]["text"] == "技术挑战"
    assert coerced["right"][0]["children"][0] == {"text": "散斑噪声"}


def test_coerce_doubao_like_scalar_and_l1_string_edges() -> None:
    """Numbers and L1 strings wrap the same way Doubao's nested string did."""
    coerced = coerce_prompt_to_diagram_spec(
        {
            "topic": "全息投影是什么",
            "children": ["光学原理", {"text": "记录", "children": [7, "数字全息", ""]}],
        },
        "mind_map",
    )
    assert coerced["children"][0] == {"text": "光学原理"}
    nested = coerced["children"][1]["children"]
    assert {"text": "7"} in nested
    assert {"text": "数字全息"} in nested
    assert {"text": ""} in nested


def test_smoke_canvas_keeps_doubao_string_child() -> None:
    """Smoke materializer must not drop the holography string child."""
    canvas = mindmap_spec_to_canvas(
        {
            "topic": "全息投影是什么",
            "children": [{"text": "光学原理", "children": ["光场重建与相位编码"]}],
        }
    )
    labels = [node["text"] for node in canvas["nodes"] if node.get("type") == "branch"]
    assert "光场重建与相位编码" in labels


def test_coerce_double_bubble_sides() -> None:
    """Left/right/similarities scalar lists coerce like mind-map labels."""
    coerced = coerce_prompt_to_diagram_spec(
        {"left": 1, "right": None, "similarities": [2]},
        "double_bubble_map",
    )
    assert coerced["left"] == "1"
    assert coerced["right"] == ""
    assert coerced["similarities"] == ["2"]
