"""Unit tests for Showcase teaching-design AI copy helpers."""

from __future__ import annotations

import json

import pytest

from services.showcase.ai_copy import (
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
    raw = '以下是结果：\n{"description":"简介","design_highlights":"亮点","teaching_reflection":"反思"}\n完'
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
    assert "变式" in fields["teaching_reflection"]


def test_normalize_ai_copy_fields_rejects_empty() -> None:
    """Reject blank normalized teaching-copy fields."""
    with pytest.raises(ValueError, match="empty_ai_copy_fields"):
        normalize_ai_copy_fields({"description": "  ", "design_highlights": "", "teaching_reflection": None})


def test_parse_json_object_roundtrip() -> None:
    """Round-trip a clean JSON payload through parse + normalize."""
    payload = {
        "description": "简介约四十字左右用于案例广场。",
        "design_highlights": "亮点一\n亮点二",
        "teaching_reflection": "课后反思一句。",
    }
    parsed = parse_json_object(json.dumps(payload, ensure_ascii=False))
    assert normalize_ai_copy_fields(parsed)["description"] == payload["description"]
