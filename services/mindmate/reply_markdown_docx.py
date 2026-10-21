"""Turn a plain MindMate reply into a Word document."""

from __future__ import annotations

import io
import re

from docx import Document as create_document
from docx.text.paragraph import Paragraph

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBER_RE = re.compile(r"^\d+\.\s+(.+)$")
_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")
_SAFE_NAME = re.compile(r"[^\w\-.\u4e00-\u9fff]+", re.UNICODE)


def sanitize_docx_stem(name: str, fallback: str) -> str:
    """Keep a short filename stem that is safe on disk and in headers."""
    cleaned = _SAFE_NAME.sub("-", (name or "").strip())[:80].strip("-.")
    return cleaned or fallback


def reply_docx_filename(markdown: str, fallback: str) -> str:
    """Name the file from the first heading, then the first line of text."""
    for line in (markdown or "").splitlines():
        heading = _HEADING_RE.match(line.strip())
        if heading:
            return f"{sanitize_docx_stem(heading.group(2), fallback)}.docx"
    for line in (markdown or "").splitlines():
        text = line.strip()
        if text:
            return f"{sanitize_docx_stem(text, fallback)}.docx"
    return f"{fallback}.docx"


def _add_inline(paragraph: Paragraph, text: str) -> None:
    parts = _INLINE_RE.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            continue
        if part.startswith("*") and part.endswith("*") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
            continue
        paragraph.add_run(part)


def build_markdown_docx(markdown: str) -> bytes:
    """Write headings, lists, and paragraphs into a new docx."""
    document = create_document()
    wrote = False
    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            level = min(len(heading.group(1)), 3)
            document.add_heading(heading.group(2).strip(), level=level)
            wrote = True
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            document.add_paragraph(bullet.group(1).strip(), style="List Bullet")
            wrote = True
            continue
        numbered = _NUMBER_RE.match(line)
        if numbered:
            document.add_paragraph(numbered.group(1).strip(), style="List Number")
            wrote = True
            continue
        paragraph = document.add_paragraph()
        _add_inline(paragraph, line)
        wrote = True
    if not wrote:
        raise ValueError("empty_reply")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
