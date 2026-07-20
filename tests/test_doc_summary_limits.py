"""Tests for Document Summary model input hard caps."""

from __future__ import annotations

from services.knowledge.doc_summary_limits import (
    DOC_SUMMARY_CONTENT_TOO_LONG_CODE,
    DOC_SUMMARY_MAX_INPUT_CHARS,
    content_exceeds_model_input,
    content_too_long_detail,
)


def test_content_exceeds_model_input_boundary() -> None:
    """Exactly at the cap is allowed; one over is rejected."""
    assert content_exceeds_model_input(DOC_SUMMARY_MAX_INPUT_CHARS) is False
    assert content_exceeds_model_input(DOC_SUMMARY_MAX_INPUT_CHARS + 1) is True


def test_content_too_long_detail_payload() -> None:
    """API detail carries a stable code for the frontend toast."""
    detail = content_too_long_detail(char_count=DOC_SUMMARY_MAX_INPUT_CHARS + 50)
    assert detail["code"] == DOC_SUMMARY_CONTENT_TOO_LONG_CODE
    assert detail["char_count"] == DOC_SUMMARY_MAX_INPUT_CHARS + 50
    assert detail["max_chars"] == DOC_SUMMARY_MAX_INPUT_CHARS
