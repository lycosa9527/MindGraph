"""Adapt lesson frames to the shared classroom step schema."""

from __future__ import annotations

from types import SimpleNamespace

from services.mind_classroom.outline import extract_mindmap_outline
from services.mind_classroom.slide_adapter import frames_to_steps


def test_frames_to_steps_uses_teacher_script_as_caption() -> None:
    """Shared steps take caption from teacher_script and attach the slide image."""
    spec = {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "text": "Topic", "type": "topic", "position": {"x": 0, "y": 0}},
            {"id": "b1", "text": "Branch", "type": "branch", "position": {"x": 80, "y": 0}},
        ],
        "connections": [{"source": "topic", "target": "b1"}],
    }
    outline = extract_mindmap_outline(spec)
    plan = {
        "batches": [
            {
                "batch_role": "open",
                "frames": [
                    {
                        "title": "Opening",
                        "teacher_script": "Welcome to the map",
                        "frame_role": "topic_overview",
                        "visual_subjects": ["Topic"],
                    }
                ],
            }
        ]
    }
    slides = [
        SimpleNamespace(
            slide_index=0,
            title="Opening",
            teacher_script="Welcome to the map",
            focus_node_ids=["topic"],
            cos_logical_key="mind_classroom/generations/11111111-1111-1111-1111-111111111111.png",
        )
    ]
    steps = frames_to_steps(plan, outline=outline, spec=spec, slides=slides, max_steps=40)
    assert steps
    assert steps[0]["kind"] == "overview"
    assert steps[0]["caption"] == "Welcome to the map"
    assert steps[0]["image_url"]
