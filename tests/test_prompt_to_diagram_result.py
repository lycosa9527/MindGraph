"""prompt_to_diagram_result normalization."""

from __future__ import annotations

from agents.core.prompt_to_diagram_result import normalize_prompt_to_diagram_result


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
