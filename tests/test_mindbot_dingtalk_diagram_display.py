"""Tests for DingTalk diagram display adapter."""

from __future__ import annotations

from services.mindbot.diagram.dingtalk_diagram_display import (
    dingtalk_answer_contains_diagram_preview,
    format_dingtalk_outbound_markdown,
    rewrite_dingtalk_diagram_markdown_alt,
    should_skip_ai_card_for_dingtalk_diagram,
)

_URL = "https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=abc&exp=999"
_UUID = "12eed5a2-6489-4c25-a4d3-f76e9f1aa9ef"
_DIFY_ANSWER = (
    f"![mg:{_UUID}]({_URL}&mgdid={_UUID})\n"
    f"<!-- mg-diagram-id:{_UUID} -->"
)


def test_format_dingtalk_outbound_markdown_keeps_inline_image() -> None:
    """DingTalk bubble shows ![](url); mg alt and HTML comment are display-only edits."""
    wire = format_dingtalk_outbound_markdown(_DIFY_ANSWER)
    assert wire == f"![]({_URL}&mgdid={_UUID})"
    assert "mg-diagram-id" not in wire
    assert _DIFY_ANSWER != wire


def test_format_dingtalk_outbound_markdown_mixed_prose_and_image() -> None:
    """Prose stays with the inline preview image in one markdown message."""
    text = f"说明文字\n\n![mg:uuid]({_URL})\n<!-- mg-diagram-id:uuid -->"
    wire = format_dingtalk_outbound_markdown(text)
    assert wire.startswith("说明文字")
    assert f"![]({_URL})" in wire


def test_rewrite_dingtalk_diagram_markdown_alt() -> None:
    """Empty alt avoids DingTalk markdown colon issues."""
    text = f"![mg:uuid]({_URL})"
    assert rewrite_dingtalk_diagram_markdown_alt(text) == f"![]({_URL})"


def test_dingtalk_answer_contains_diagram_preview() -> None:
    """Detect generate_dingtalk preview markdown in assistant answers."""
    assert dingtalk_answer_contains_diagram_preview(_DIFY_ANSWER) is True
    assert dingtalk_answer_contains_diagram_preview("plain text") is False


def test_should_skip_ai_card_for_dingtalk_diagram() -> None:
    """Skip AI card for diagram markdown (complete or streaming partial)."""
    assert should_skip_ai_card_for_dingtalk_diagram(_DIFY_ANSWER) is True
    assert should_skip_ai_card_for_dingtalk_diagram("![mg:partial") is True
    assert should_skip_ai_card_for_dingtalk_diagram("说明文字") is False
