"""Classroom outlines for concept maps use concepts, not mind-map migration."""

from __future__ import annotations

from services.mind_classroom.outline import extract_mindmap_outline


def test_concept_map_relationships_from_topic_are_branches() -> None:
    """Labeled links out of the topic become first-level classroom branches."""
    outline = extract_mindmap_outline(
        {
            "type": "concept_map",
            "nodes": [
                {"id": "topic", "text": "水", "type": "topic"},
                {"id": "concept-1", "text": "冰", "type": "branch"},
                {"id": "concept-2", "text": "蒸汽", "type": "branch"},
            ],
            "connections": [
                {"source": "topic", "target": "concept-1", "label": "凝固成"},
                {"source": "topic", "target": "concept-2", "label": "蒸发成"},
            ],
        },
        diagram_type="concept_map",
    )
    assert outline.diagram_type == "concept_map"
    assert outline.topic == "水"
    assert [branch.text for branch in outline.branches] == ["冰", "蒸汽"]


def test_concept_map_without_edges_lists_concepts() -> None:
    """Concepts still teach when the map has no topic-rooted relationships."""
    outline = extract_mindmap_outline(
        {
            "type": "concept_map",
            "nodes": [
                {"id": "topic", "text": "生态系统", "type": "topic"},
                {"id": "concept-1", "text": "生产者", "type": "branch"},
                {"id": "concept-2", "text": "消费者", "type": "branch"},
            ],
            "connections": [],
        },
        diagram_type="concept_map",
    )
    assert outline.topic == "生态系统"
    assert [branch.text for branch in outline.branches] == ["生产者", "消费者"]
