"""Unit tests for Showcase teaching-design AI copy helpers."""

from __future__ import annotations

import json

import pytest

from services.showcase.ai_copy import (
    extract_partial_ai_copy_fields,
    normalize_ai_copy_fields,
    parse_json_object,
    strip_code_fence,
)


def test_strip_code_fence_removes_json_fence() -> None:
    """Strip markdown JSON fences from model output."""
    raw = '```json\n{"description":"a"}\n```'
    assert strip_code_fence(raw) == '{"description":"a"}'


def test_parse_json_object_tolerates_noise() -> None:
    """Parse the first JSON object even when wrapped in prose."""
    raw = '以下是结果：\n{"description":"简介","design_highlights":"亮点"}\n完'
    parsed = parse_json_object(raw)
    assert parsed["description"] == "简介"
    assert parsed["design_highlights"] == "亮点"


def test_normalize_ai_copy_fields_accepts_chinese_keys() -> None:
    """Map Chinese keys and flatten bullet newlines in highlights."""
    fields = normalize_ai_copy_fields(
        {
            "教学设计简介": "本课引导学生辨日求真。",
            "设计亮点": "- 认知冲突\n- 思维可视化",
            "教学反思": "需加强变式训练。",
        }
    )
    assert "辨日" in fields["description"]
    assert "认知冲突" in fields["design_highlights"]
    assert "\n" not in fields["design_highlights"]
    # Reflection is teacher-authored; AI normalize always clears it.
    assert fields["teaching_reflection"] == ""


def test_normalize_ai_copy_fields_rejects_empty() -> None:
    """Reject blank normalized teaching-copy fields."""
    with pytest.raises(ValueError, match="empty_ai_copy_fields"):
        normalize_ai_copy_fields({"description": "  ", "design_highlights": "", "teaching_reflection": None})


def test_parse_json_object_roundtrip() -> None:
    """Round-trip a clean JSON payload through parse + normalize."""
    payload = {
        "description": "简介约四十字左右用于案例广场。",
        "design_highlights": "亮点一\n亮点二",
    }
    parsed = parse_json_object(json.dumps(payload, ensure_ascii=False))
    normalized = normalize_ai_copy_fields(parsed)
    assert normalized["description"] == payload["description"]
    assert normalized["teaching_reflection"] == ""


def test_extract_partial_ai_copy_fields_progressive() -> None:
    """Grow fields as JSON keys appear in a streaming buffer."""
    assert not extract_partial_ai_copy_fields("{")
    assert not extract_partial_ai_copy_fields('{"description": "')
    partial = extract_partial_ai_copy_fields('{"description": "本课用气泡图')
    assert partial["description"] == "本课用气泡图"
    assert "design_highlights" not in partial

    two = extract_partial_ai_copy_fields('{"description": "简介完成", "design_highlights": "亮点进行中')
    assert two["description"] == "简介完成"
    assert two["design_highlights"] == "亮点进行中"
    assert "teaching_reflection" not in two

    # Reflection key is ignored even if the model still emits it.
    full = extract_partial_ai_copy_fields('{"description":"a","design_highlights":"b","teaching_reflection":"c"}')
    assert full == {
        "description": "a",
        "design_highlights": "b",
    }


def test_extract_partial_ai_copy_fields_escapes_and_aliases() -> None:
    """Decode escapes and accept Chinese key aliases mid-stream."""
    escaped = extract_partial_ai_copy_fields('{"description": "说\\"清楚\\n再练')
    assert escaped["description"] == '说"清楚\n再练'

    chinese = extract_partial_ai_copy_fields('{"教学设计简介": "简介", "设计亮点": "亮点", "教学反思": "反思进行')
    assert chinese["description"] == "简介"
    assert chinese["design_highlights"] == "亮点"
    assert "teaching_reflection" not in chinese
