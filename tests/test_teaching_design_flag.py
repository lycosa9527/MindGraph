"""Tests for teaching-instruction reply markers and workflow outputs."""

from __future__ import annotations

from services.diagram.assistant_markdown import strip_diagram_id_html_comments
from services.mindmate.teaching_design_flag import (
    is_teaching_instruction_text,
    mindmate_meta_from_workflow_chunk,
    parse_reply_kind_from_outputs,
    parse_reply_kind_from_text,
    strip_reply_kind_markers,
    teaching_instruction_from_request,
)


def test_parse_comment_and_bracket_markers() -> None:
    """HTML comment and bracket fallback both identify teaching_instruction."""
    comment = "正文\n<!-- mg-reply-kind:teaching_instruction -->"
    bracket = "正文\n[mg-reply-kind:teaching_instruction]"
    assert parse_reply_kind_from_text(comment) == "teaching_instruction"
    assert parse_reply_kind_from_text(bracket) == "teaching_instruction"
    assert is_teaching_instruction_text(comment) is True
    assert is_teaching_instruction_text("普通问答") is False


def test_strip_hides_markers_from_display_and_dingtalk() -> None:
    """Web/DingTalk display paths must not show either marker."""
    raw = "课例正文\n<!-- mg-reply-kind:teaching_instruction -->\n[mg-reply-kind:teaching_instruction]"
    stripped = strip_reply_kind_markers(raw)
    assert "mg-reply-kind" not in stripped
    assert "课例正文" in stripped
    outbound = strip_diagram_id_html_comments(raw)
    assert "mg-reply-kind" not in outbound


def test_workflow_outputs_and_request_gate() -> None:
    """Workflow outputs and request reply_kind both authorize export."""
    assert parse_reply_kind_from_outputs({"mg_reply_kind": "teaching_instruction"})
    assert parse_reply_kind_from_outputs({"export_word_template": True})
    assert parse_reply_kind_from_outputs({"export_word_template": "true"})
    assert parse_reply_kind_from_outputs({"other": 1}) is None
    assert teaching_instruction_from_request("teaching_instruction", "no marker") is True
    assert teaching_instruction_from_request(None, "plain") is False
    meta = mindmate_meta_from_workflow_chunk(
        {"event": "workflow_finished", "data": {"outputs": {"mg_reply_kind": "teaching_instruction"}}}
    )
    assert meta is not None
    assert meta["event"] == "mindmate_meta"
    assert mindmate_meta_from_workflow_chunk({"event": "node_finished"}) is None
