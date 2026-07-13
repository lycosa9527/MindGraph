"""Unit tests for Kitty durable library draft specs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.kitty.diagram.library_draft import (
    build_kitty_library_draft_spec,
    draft_title_for_diagram,
    normalize_library_diagram_type,
)


def test_build_mindmap_draft_spec() -> None:
    """Mindmap draft is topic + empty children."""
    assert build_kitty_library_draft_spec("mindmap", topic="运动会") == {
        "topic": "运动会",
        "children": [],
    }


def test_build_double_bubble_draft_spec() -> None:
    """Double bubble uses left/right seeds."""
    spec = build_kitty_library_draft_spec(
        "double_bubble_map",
        left="苹果",
        right="梨",
    )
    assert spec["left"] == "苹果"
    assert spec["right"] == "梨"
    assert spec["similarities"] == []


def test_draft_title_prefers_topic() -> None:
    """Topic wins over localized default title."""
    assert draft_title_for_diagram("mindmap", topic="运动会", language="zh") == "运动会"
    assert draft_title_for_diagram("mindmap", language="en") == "New mind map"


def test_normalize_library_diagram_type() -> None:
    """mind_map slug collapses to mindmap storage form."""
    assert normalize_library_diagram_type("mind_map") == "mindmap"
    assert normalize_library_diagram_type("bubble_map") == "bubble_map"
