"""Shared lecture step validation and canvas-tour JSON repair."""

from __future__ import annotations

from services.mind_classroom.canvas_tour import parse_canvas_tour_json
from services.mind_classroom.canvas_tour_chunks import merge_usage, split_each_node_families
from services.mind_classroom.enqueue import TASK_SCRIPT, TASK_SLIDES, _task_name
from services.mind_classroom.steps import MAX_STEPS_DEFAULT, normalize_steps


def test_normalize_steps_caps_and_drops_unknown_ids() -> None:
    """Cap the step list and drop focus ids that are not in the spec."""
    spec = {"nodes": [{"id": "topic"}, {"id": "b1"}]}
    raw = [
        {
            "kind": "overview",
            "title": "Open",
            "caption": "Hello",
            "focus_node_ids": ["topic", "ghost"],
        }
    ] + [
        {"kind": "branch", "title": f"N{index}", "caption": f"C{index}", "focus_node_ids": ["b1"]}
        for index in range(50)
    ]
    steps = normalize_steps(raw, spec=spec, max_steps=MAX_STEPS_DEFAULT)
    assert len(steps) == MAX_STEPS_DEFAULT
    assert steps[0]["focus_node_ids"] == ["topic"]


def test_parse_canvas_tour_json_strips_fence() -> None:
    """Accept fenced JSON from the canvas-tour LLM."""
    raw = """```json
{"steps": [{"kind": "overview", "title": "Hi", "caption": "Welcome"}]}
```"""
    steps = parse_canvas_tour_json(raw)
    assert steps[0]["caption"] == "Welcome"


def test_split_each_node_families_groups_leaves_under_trunk() -> None:
    """Deep walk is chunked as one trunk plus its leaves."""
    nodes = [
        {"id": "topic", "kind": "topic", "stop": "trunk"},
        {"id": "b1", "kind": "branch", "stop": "trunk"},
        {"id": "b1c1", "kind": "branch", "stop": "leaf"},
        {"id": "b1c2", "kind": "branch", "stop": "leaf"},
        {"id": "b2", "kind": "branch", "stop": "trunk"},
        {"id": "b2c1", "kind": "branch", "stop": "leaf"},
    ]
    families = split_each_node_families(nodes)
    assert [[node["id"] for node in family] for family in families] == [
        ["b1", "b1c1", "b1c2"],
        ["b2", "b2c1"],
    ]
    merged = merge_usage({"prompt_tokens": 2, "total_tokens": 5}, {"prompt_tokens": 3, "total_tokens": 4})
    assert merged == {"prompt_tokens": 5, "total_tokens": 9}


def test_script_and_slides_use_separate_task_names() -> None:
    """Voice and slides must not share one long Celery task name."""
    assert _task_name("canvas_tour") == TASK_SCRIPT
    assert _task_name("slide_deck") == TASK_SLIDES
    assert TASK_SCRIPT != TASK_SLIDES
