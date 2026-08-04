"""Unit tests for Showcase diagram AI copy helpers."""

from __future__ import annotations

import pytest

from services.showcase.diagram_ai_copy import (
    extract_diagram_text,
    extract_diagram_texts,
    extract_partial_diagram_ai_copy_fields,
    normalize_diagram_ai_copy_fields,
)


def test_extract_diagram_text_from_nodes() -> None:
    """Collect unique node texts from a nodes-array mind map."""
    spec = {
        "nodes": [
            {"id": "1", "text": "光合作用"},
            {"id": "2", "text": "叶绿体"},
            {"id": "3", "text": "叶绿体"},
            {"id": "4", "text": "  "},
        ]
    }
    text = extract_diagram_text(spec, "mind_map")
    assert "光合作用" in text
    assert text.count("叶绿体") == 1


def test_extract_diagram_text_from_native_mind_map() -> None:
    """Fall back to native mind-map branches when nodes are absent."""
    spec = {
        "topic": "智能硬件",
        "branches": [
            {"text": "传感器", "children": [{"text": "摄像头"}]},
            {"text": "芯片"},
        ],
    }
    text = extract_diagram_text(spec, "mind_map")
    assert "智能硬件" in text
    assert "传感器" in text
    assert "摄像头" in text
    assert "芯片" in text


def test_extract_diagram_text_rejects_empty() -> None:
    """Raise when no usable text exists."""
    with pytest.raises(ValueError, match="no_text_extracted"):
        extract_diagram_text({"nodes": []}, "mind_map")


def test_extract_diagram_texts_joins_gallery() -> None:
    """Join multiple specs with section headers."""
    specs = [
        {"nodes": [{"id": "a", "text": "图一主题"}]},
        {"nodes": [{"id": "b", "text": "图二主题"}]},
    ]
    text = extract_diagram_texts(specs, "mind_map")
    assert "【图示 1】" in text
    assert "图一主题" in text
    assert "【图示 2】" in text
    assert "图二主题" in text


def test_normalize_diagram_ai_copy_fields_accepts_chinese_keys() -> None:
    """Map Chinese keys and flatten hard newlines."""
    fields = normalize_diagram_ai_copy_fields(
        {
            "图示简介": "本图用思维导图梳理智能硬件。",
            "课堂应用": "- 导入\n- 小组讨论",
        }
    )
    assert "思维导图" in fields["description"]
    assert "导入" in fields["classroom_application"]
    assert "\n" not in fields["classroom_application"]


def test_normalize_diagram_ai_copy_fields_rejects_empty() -> None:
    """Reject blank normalized diagram-copy fields."""
    with pytest.raises(ValueError, match="empty_ai_copy_fields"):
        normalize_diagram_ai_copy_fields({"description": "  ", "classroom_application": ""})


def test_extract_partial_diagram_ai_copy_fields_progressive() -> None:
    """Grow fields as JSON keys appear in a streaming buffer."""
    assert not extract_partial_diagram_ai_copy_fields("{")
    partial = extract_partial_diagram_ai_copy_fields('{"description": "本图用气泡图')
    assert partial["description"] == "本图用气泡图"
    assert "classroom_application" not in partial

    two = extract_partial_diagram_ai_copy_fields('{"description": "简介完成", "classroom_application": "课堂进行中')
    assert two["description"] == "简介完成"
    assert two["classroom_application"] == "课堂进行中"
