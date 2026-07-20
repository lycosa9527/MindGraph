"""Unit tests for vision mind-map detect/parse helpers."""

from services.knowledge.vision_mindmap import (
    MINDMAP_CONFIDENCE_THRESHOLD,
    parse_vision_mindmap_payload,
    sanitize_mindmap_spec,
)


def test_sanitize_mindmap_spec_requires_topic_and_children():
    """Reject empty trees; keep label→text children."""
    assert sanitize_mindmap_spec(None) is None
    assert sanitize_mindmap_spec({"topic": "X"}) is None
    assert sanitize_mindmap_spec({"topic": "X", "children": []}) is None
    spec = sanitize_mindmap_spec(
        {
            "topic": "Root",
            "children": [
                {"id": "a", "text": "Branch A", "children": [{"label": "Child"}]},
                {"text": ""},
            ],
        }
    )
    assert spec is not None
    assert spec["topic"] == "Root"
    assert len(spec["children"]) == 1
    assert spec["children"][0]["children"][0]["text"] == "Child"


def test_parse_vision_rejects_low_confidence_mindmap():
    """Below threshold must not auto-apply as a mind map."""
    low = MINDMAP_CONFIDENCE_THRESHOLD - 0.1
    payload = (
        '{"is_mindmap": true, "confidence": %s, "reason": "maybe", '
        '"spec": {"topic": "T", "children": [{"id": "1", "text": "A"}]}}'
    ) % low
    result = parse_vision_mindmap_payload(payload)
    assert result.is_mindmap is False
    assert result.spec is None


def test_parse_vision_accepts_clear_mindmap():
    """High-confidence radial map becomes a sanitized spec."""
    payload = """
    {
      "is_mindmap": true,
      "confidence": 0.91,
      "reason": "radial bubbles",
      "spec": {
        "topic": "Learning Skills",
        "children": [
          {"id": "b1", "text": "Read", "children": [{"id": "c1", "text": "notes"}]}
        ]
      }
    }
    """
    result = parse_vision_mindmap_payload(payload)
    assert result.is_mindmap is True
    assert result.spec is not None
    assert result.spec["topic"] == "Learning Skills"
    assert result.spec["children"][0]["text"] == "Read"


def test_parse_vision_document_photo():
    """Plain documents must stay on the OCR extract path."""
    payload = '{"is_mindmap": false, "confidence": 0.88, "reason": "meeting notes", "spec": null}'
    result = parse_vision_mindmap_payload(payload)
    assert result.is_mindmap is False
    assert result.spec is None
    assert "meeting" in result.reason
