"""JSON parser — control characters inside string literals."""

from __future__ import annotations

from agents.core.json_parser import extract_json_from_response


def test_extract_json_escapes_tabs_inside_string_values() -> None:
    """Tab-separated table text in a JSON string value must parse (production flow_map case)."""
    raw = (
        '{\n'
        ' "title": "环节\t时长\t核心任务",\n'
        ' "steps": ["冲突启思", "可视建构"],\n'
        ' "substeps": []\n'
        "}"
    )
    parsed = extract_json_from_response(raw)
    assert parsed is not None
    assert parsed["title"] == "环节\t时长\t核心任务"
    assert parsed["steps"] == ["冲突启思", "可视建构"]


def test_extract_json_escapes_newlines_inside_string_values() -> None:
    """Raw newlines inside JSON strings are escaped before json.loads."""
    raw = '{\n "topic": "line1\nline2",\n "children": []\n}'
    parsed = extract_json_from_response(raw)
    assert parsed is not None
    assert parsed["topic"] == "line1\nline2"
