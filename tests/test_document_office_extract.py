"""Tests for OOXML/CSV extraction helpers."""

from __future__ import annotations

from pathlib import Path

from services.knowledge.document_office_extract import extract_csv_markdown
from services.knowledge.document_processor import DocumentProcessor


def test_extract_csv_markdown(tmp_path: Path) -> None:
    """CSV files become markdown tables."""
    csv_path = tmp_path / "scores.csv"
    csv_path.write_text("name,score\nAda,10\nBob,8\n", encoding="utf-8")
    md = extract_csv_markdown(str(csv_path))
    assert "| name | score |" in md
    assert "| Ada | 10 |" in md


def test_processor_supports_new_mimes() -> None:
    """Document processor accepts legacy Office, CSV, and WEBP."""
    processor = DocumentProcessor()
    assert processor.is_supported("application/msword")
    assert processor.is_supported("application/vnd.ms-powerpoint")
    assert processor.is_supported("application/vnd.ms-excel")
    assert processor.is_supported("text/csv")
    assert processor.is_supported("image/webp")


def test_get_file_type_legacy_and_csv(tmp_path: Path) -> None:
    """Extension mapping covers legacy Office and CSV."""
    processor = DocumentProcessor()
    assert processor.get_file_type(str(tmp_path / "a.doc")) == "application/msword"
    assert processor.get_file_type(str(tmp_path / "a.ppt")) == "application/vnd.ms-powerpoint"
    assert processor.get_file_type(str(tmp_path / "a.xls")) == "application/vnd.ms-excel"
    assert processor.get_file_type(str(tmp_path / "a.csv")) == "text/csv"
    assert processor.get_file_type(str(tmp_path / "a.webp")) == "image/webp"
