"""Seminar Office text fallback when LibreOffice is not installed."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pptx import Presentation

from services.features.mindmate_seminar.office_text_preview import office_text_preview


def test_office_text_preview_docx(tmp_path: Path) -> None:
    """Word files yield paragraph text."""
    path = tmp_path / "notes.docx"
    document = Document()
    document.add_paragraph("资源预览正文")
    document.save(str(path))
    assert "资源预览正文" in office_text_preview(path, "notes.docx")


def test_office_text_preview_pptx(tmp_path: Path) -> None:
    """PowerPoint files yield slide text."""
    path = tmp_path / "deck.pptx"
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    title = slide.shapes.title
    assert title is not None
    title.text = "第一页标题"
    deck.save(str(path))
    assert "第一页标题" in office_text_preview(path, "deck.pptx")


def test_office_text_preview_xlsx(tmp_path: Path) -> None:
    """Spreadsheets yield cell values."""
    path = tmp_path / "sheet.xlsx"
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet["A1"] = "指标"
    sheet["B1"] = "分值"
    sheet["A2"] = "课堂"
    sheet["B2"] = 12
    book.save(path)
    text = office_text_preview(path, "sheet.xlsx")
    assert "指标" in text
    assert "课堂" in text


def test_office_text_preview_rejects_garbage(tmp_path: Path) -> None:
    """Corrupt OOXML does not raise out of the fallback."""
    path = tmp_path / "broken.docx"
    path.write_bytes(b"PK fake")
    assert office_text_preview(path, "broken.docx") == ""


def test_office_text_preview_skips_legacy_doc(tmp_path: Path) -> None:
    """Legacy .doc stays on the LibreOffice path."""
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 32)
    assert office_text_preview(path, "legacy.doc") == ""
