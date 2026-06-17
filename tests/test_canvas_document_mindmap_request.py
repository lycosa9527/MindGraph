"""Validation tests for CanvasDocumentMindmapRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.requests.requests_diagram import CanvasDocumentMindmapRequest


def test_canvas_document_mindmap_accepts_pasted_content() -> None:
    """Accept non-empty pasted document text."""
    req = CanvasDocumentMindmapRequest(page_content="Chapter one summary", language="en")
    assert req.page_content == "Chapter one summary"
    assert req.page_url is None


def test_canvas_document_mindmap_accepts_url_only() -> None:
    """Accept a fetch URL when page_content is empty."""
    req = CanvasDocumentMindmapRequest(
        page_url="https://example.com/article",
        language="zh",
    )
    assert req.page_url == "https://example.com/article"
    assert req.page_content == ""


def test_canvas_document_mindmap_requires_content_or_url() -> None:
    """Reject requests with neither content nor URL."""
    with pytest.raises(ValidationError) as exc_info:
        CanvasDocumentMindmapRequest(page_content="   ", page_url="  ")
    assert "page_content or page_url is required" in str(exc_info.value)


def test_canvas_document_mindmap_rejects_unknown_language() -> None:
    """Reject unknown prompt output language codes."""
    with pytest.raises(ValidationError):
        CanvasDocumentMindmapRequest(page_content="text", language="not-a-locale")
