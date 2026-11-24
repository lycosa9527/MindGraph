"""Parse the diagram-type vision JSON used by the manual import dialog."""

from services.knowledge.vision_diagram import parse_vision_diagram_payload


def test_parse_double_bubble_from_probe_shape():
    """2.4g / 5g layout stays a double bubble with both sides."""
    payload = """
    {
      "diagram_type": "double_bubble_map",
      "confidence": 1.0,
      "reason": "two topics",
      "spec": {
        "left": "2.4g",
        "right": "5g",
        "similarities": ["无线频段", "用于Wi-Fi"],
        "left_differences": ["频率较低"],
        "right_differences": ["频率较高"]
      }
    }
    """
    result = parse_vision_diagram_payload(payload)
    assert result.recognized is True
    assert result.diagram_type == "double_bubble_map"
    assert result.spec is not None
    assert result.spec["left"] == "2.4g"
    assert result.spec["right"] == "5g"
    assert result.spec["similarities"] == ["无线频段", "用于Wi-Fi"]


def test_parse_flow_nested_steps():
    """Nested step objects become title, step labels, and indexed substeps."""
    payload = """
    {
      "diagram_type": "flow_map",
      "confidence": 0.9,
      "reason": "chain",
      "spec": {
        "title": "接收SSTV",
        "steps": [
          {"text": "准备阶段", "substeps": ["确认频率与模式", "调整天线与增益"]}
        ]
      }
    }
    """
    result = parse_vision_diagram_payload(payload)
    assert result.recognized is True
    assert result.spec is not None
    assert result.spec["title"] == "接收SSTV"
    assert result.spec["steps"] == ["准备阶段"]
    assert result.spec["substeps"][0]["substeps"] == ["确认频率与模式", "调整天线与增益"]
    assert result.spec["substeps"][0]["stepIndex"] == 0


def test_parse_mindmap_children():
    """A radial map keeps topic and nested branch text."""
    payload = """
    {
      "diagram_type": "mindmap",
      "confidence": 0.8,
      "reason": "center with branches",
      "spec": {
        "topic": "露和霜",
        "children": [
          {"text": "课程定位", "children": [{"text": "学科：科学（五年级上册）"}]}
        ]
      }
    }
    """
    result = parse_vision_diagram_payload(payload)
    assert result.recognized is True
    assert result.topic == "露和霜"
    assert result.spec is not None
    assert result.spec["children"][0]["children"][0]["text"] == "学科：科学（五年级上册）"


def test_parse_rejects_low_confidence_and_plain_photo():
    """A weak guess and a non-diagram stay out of the confirm dialog."""
    low = """
    {
      "diagram_type": "circle_map",
      "confidence": 0.2,
      "reason": "maybe",
      "spec": {"topic": "猫", "context": ["软"]}
    }
    """
    blank = '{"diagram_type": null, "confidence": 0.9, "reason": "portrait", "spec": null}'
    assert parse_vision_diagram_payload(low).recognized is False
    assert parse_vision_diagram_payload(blank).recognized is False
    assert parse_vision_diagram_payload(blank).spec is None
