"""Unit tests for Showcase diagram AI copy helpers."""

from __future__ import annotations

import pytest

from services.showcase.diagram_ai_copy import (
    extract_diagram_text,
    extract_diagram_text_from_images,
    extract_diagram_texts,
    extract_partial_diagram_ai_copy_fields,
    normalize_diagram_ai_copy_fields,
)


def test_extract_diagram_text_from_nodes_tree() -> None:
    """Preserve mind-map hierarchy from nodes + connections."""
    spec = {
        "type": "mindmap",
        "nodes": [
            {"id": "topic", "text": "光合作用", "type": "topic"},
            {"id": "b1", "text": "叶绿体", "type": "branch"},
            {"id": "b2", "text": "光反应", "type": "branch"},
            {"id": "b1a", "text": "类囊体", "type": "branch"},
            {"id": "x", "text": "  "},
        ],
        "connections": [
            {"source": "topic", "target": "b1"},
            {"source": "topic", "target": "b2"},
            {"source": "b1", "target": "b1a"},
        ],
    }
    text = extract_diagram_text(spec, "mind_map")
    assert "图示类型：思维导图" in text
    assert "中心主题：光合作用" in text
    assert "分支结构：" in text
    assert "- 叶绿体" in text
    assert "  - 类囊体" in text
    assert "- 光反应" in text
    # Flat bag-of-words dump should not be the only signal.
    assert text.index("中心主题") < text.index("叶绿体")


def test_extract_diagram_text_dedupes_without_connections() -> None:
    """Fall back to role grouping when connections are absent."""
    spec = {
        "nodes": [
            {"id": "1", "text": "光合作用", "type": "topic"},
            {"id": "2", "text": "叶绿体", "type": "branch"},
            {"id": "3", "text": "叶绿体", "type": "branch"},
        ]
    }
    text = extract_diagram_text(spec, "mind_map")
    assert "图示类型：思维导图" in text
    assert "中心主题：光合作用" in text
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
    assert "图示类型：思维导图" in text
    assert "中心主题：智能硬件" in text
    assert "- 传感器" in text
    assert "  - 摄像头" in text
    assert "- 芯片" in text


def test_extract_diagram_text_double_bubble_roles() -> None:
    """Keep double-bubble role sections for comparison structure."""
    spec = {
        "type": "double_bubble_map",
        "left": "猫",
        "right": "狗",
        "similarities": ["哺乳动物"],
        "leftDifferences": ["喜欢爬高"],
        "rightDifferences": ["需要遛"],
    }
    text = extract_diagram_text(spec, "double_bubble_map")
    assert "图示类型：双气泡图" in text
    assert "左侧主题：猫" in text
    assert "右侧主题：狗" in text
    assert "相同点：" in text
    assert "左侧不同点：" in text
    assert "右侧不同点：" in text


def test_extract_diagram_text_concept_map_relations() -> None:
    """Keep labeled concept-map propositions."""
    spec = {
        "type": "concept_map",
        "nodes": [
            {"id": "a", "text": "水", "type": "concept"},
            {"id": "b", "text": "冰", "type": "concept"},
        ],
        "connections": [
            {"source": "a", "target": "b", "label": "凝固成"},
        ],
    }
    text = extract_diagram_text(spec, "concept_map")
    assert "图示类型：概念图" in text
    assert "水 —凝固成→ 冰" in text


def test_extract_diagram_text_rejects_empty() -> None:
    """Raise when no usable text exists."""
    with pytest.raises(ValueError, match="no_text_extracted"):
        extract_diagram_text({"nodes": []}, "mind_map")


def test_extract_diagram_texts_joins_gallery() -> None:
    """Join multiple specs with section headers."""
    specs = [
        {"nodes": [{"id": "a", "text": "图一主题", "type": "topic"}]},
        {
            "type": "bubble_map",
            "nodes": [
                {"id": "topic", "text": "图二主题", "type": "topic"},
                {"id": "b1", "text": "特征甲", "type": "bubble"},
            ],
        },
    ]
    text = extract_diagram_texts(specs, "mind_map")
    assert "【图示 1】" in text
    assert "图一主题" in text
    assert "【图示 2】" in text
    assert "图示类型：气泡图" in text
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


def test_extract_diagram_text_from_images_uses_vision_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gallery images become OCR prompt text for diagram AI copy."""
    calls: list[tuple[bytes, str]] = []

    def fake_ocr(image_bytes: bytes, mime_type: str = "image/png", prompt: str | None = None) -> str:
        del prompt
        calls.append((image_bytes, mime_type))
        return "中心：光合作用\n分支：叶绿体"

    monkeypatch.setattr(
        "services.showcase.diagram_ai_copy.dashscope_vision_ocr",
        fake_ocr,
    )
    text = extract_diagram_text_from_images([(b"fakepng", "image/png")])
    assert "【图片 OCR】" in text
    assert "光合作用" in text
    assert calls == [(b"fakepng", "image/png")]


def test_extract_diagram_text_from_images_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise when OCR yields no usable text."""
    monkeypatch.setattr(
        "services.showcase.diagram_ai_copy.dashscope_vision_ocr",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "services.showcase.diagram_ai_copy.ocr_image_bytes",
        lambda *_args, **_kwargs: "",
    )
    with pytest.raises(ValueError, match="no_text_extracted"):
        extract_diagram_text_from_images([(b"x", "image/jpeg")])
