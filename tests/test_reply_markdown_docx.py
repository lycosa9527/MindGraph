"""Plain MindMate replies become readable Word files."""

from __future__ import annotations

import io

from docx import Document

from services.mindmate.reply_markdown_docx import (
    build_markdown_docx,
    reply_docx_filename,
)


def test_markdown_docx_keeps_heading_and_paragraph() -> None:
    """Headings and body text survive the round trip."""
    payload = build_markdown_docx("# 研讨纪要\n\n先看**问题**，再看证据。\n- 一条")
    document = Document(io.BytesIO(payload))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "研讨纪要" in text
    assert "问题" in text
    assert "一条" in text
    assert "**" not in text


def test_reply_docx_filename_uses_heading() -> None:
    """The artifact name comes from the first heading."""
    assert reply_docx_filename("# 分数的意义\n正文", "研讨文档") == "分数的意义.docx"
    assert reply_docx_filename("   ", "研讨文档") == "研讨文档.docx"


def test_empty_markdown_is_rejected() -> None:
    """A blank reply is not archived as an empty document."""
    try:
        build_markdown_docx("\n\n")
    except ValueError as exc:
        assert str(exc) == "empty_reply"
    else:
        raise AssertionError("expected empty_reply")
