"""Tests for canonical generate_dingtalk assistant markdown helpers."""

from __future__ import annotations

from services.diagram.assistant_markdown import (
    answer_contains_diagram_preview,
    answer_has_library_diagram_uuid,
    extract_generate_dingtalk_preview_url,
    extract_preview_unique_id,
    parse_assistant_diagram_library_id,
    should_buffer_diagram_markdown_reply,
    strip_diagram_id_html_comments,
)

_URL = "https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=abc"
_UUID = "12eed5a2-6489-4c25-a4d3-f76e9f1aa9ef"
_DIFY_ANSWER = f"![mg:{_UUID}]({_URL}&mgdid={_UUID})\n<!-- mg-diagram-id:{_UUID} -->"


def test_parse_assistant_diagram_library_id_from_comment() -> None:
    """Parse library uuid from HTML comment."""
    assert parse_assistant_diagram_library_id(_DIFY_ANSWER) == _UUID


def test_parse_assistant_diagram_library_id_from_mg_alt() -> None:
    """Parse library uuid from mg alt text."""
    text = f"![mg:{_UUID}]({_URL})"
    assert parse_assistant_diagram_library_id(text) == _UUID


def test_extract_generate_dingtalk_preview_url() -> None:
    """Extract HTTPS preview URL from markdown."""
    assert extract_generate_dingtalk_preview_url(_DIFY_ANSWER) == f"{_URL}&mgdid={_UUID}"


def test_extract_preview_unique_id() -> None:
    """Extract temp PNG id from preview URL."""
    assert extract_preview_unique_id(_DIFY_ANSWER) == "deadbeef"


def test_should_buffer_diagram_markdown_reply() -> None:
    """Buffer diagram markdown for one-shot send (with or without AI card)."""
    assert should_buffer_diagram_markdown_reply(_DIFY_ANSWER) is True
    assert should_buffer_diagram_markdown_reply("![mg:partial") is True
    assert should_buffer_diagram_markdown_reply("plain text") is False


def test_strip_diagram_id_html_comments() -> None:
    """Strip HTML comments without removing image markdown."""
    stripped = strip_diagram_id_html_comments(_DIFY_ANSWER)
    assert "mg-diagram-id" not in stripped
    assert f"![mg:{_UUID}]" in stripped
    assert answer_has_library_diagram_uuid(_DIFY_ANSWER) is True
    assert answer_contains_diagram_preview(_DIFY_ANSWER) is True
