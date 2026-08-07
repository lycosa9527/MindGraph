"""prompt_to_diagram_result normalization."""

from __future__ import annotations

from agents.core.prompt_to_diagram_result import (
    coerce_prompt_to_diagram_spec,
    normalize_prompt_to_diagram_result,
)


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


def test_coerce_double_bubble_sides() -> None:
    """Left/right/similarities scalar lists coerce like mind-map labels."""
    coerced = coerce_prompt_to_diagram_spec(
        {"left": 1, "right": None, "similarities": [2]},
        "double_bubble_map",
    )
    assert coerced["left"] == "1"
    assert coerced["right"] == ""
    assert coerced["similarities"] == ["2"]
