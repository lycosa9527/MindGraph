"""Seminar shared-file PDF preview cache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from services.features.mindmate_seminar.background_file_preview import (
    _ensure_preview_pdf_sync,
    _load_preview_bytes_sync,
    preview_cache_path,
)
from services.showcase.covers.office_to_pdf import (
    build_office_pdf_convert_to,
    office_suffix_needs_pdf,
)


def test_office_suffixes_include_seminar_spreadsheets_and_legacy_slides() -> None:
    """Seminar uploads cover Writer, Impress, and Calc families."""
    assert office_suffix_needs_pdf(".docx")
    assert office_suffix_needs_pdf(".ppt")
    assert office_suffix_needs_pdf(".xlsx")
    assert not office_suffix_needs_pdf(".pdf")
    assert build_office_pdf_convert_to(".ppt").startswith("pdf:impress_pdf_Export:")
    assert build_office_pdf_convert_to(".xlsx").startswith("pdf:calc_pdf_Export:")


def test_preview_cache_path_keeps_source_basename(tmp_path: Path) -> None:
    """Cache lives next to the uploaded blob with a stable suffix."""
    source = tmp_path / "notes.docx"
    assert preview_cache_path(source) == tmp_path / "notes.docx.preview.pdf"


def test_ensure_preview_pdf_sync_returns_native_pdf(tmp_path: Path) -> None:
    """Native PDFs skip LibreOffice."""
    source = tmp_path / "handout.pdf"
    source.write_bytes(b"%PDF-1.7")
    assert _ensure_preview_pdf_sync(source, "handout.pdf", "2026/10/handout.pdf") == source


def test_ensure_preview_pdf_sync_converts_office_once(tmp_path: Path) -> None:
    """Office files convert to a cached PDF and reuse it on the next open."""
    source = tmp_path / "plan.docx"
    source.write_bytes(b"PK fake")
    produced = tmp_path / "made.pdf"
    produced.write_bytes(b"%PDF-1.7 converted")

    with (
        patch(
            "services.features.mindmate_seminar.background_file_preview.convert_office_to_pdf",
            return_value=produced,
        ) as convert_mock,
        patch(
            "services.features.mindmate_seminar.background_file_preview.pull_preview_pdf_sync",
            return_value=False,
        ),
        patch(
            "services.features.mindmate_seminar.background_file_preview.put_preview_pdf_sync",
        ) as put_mock,
        patch(
            "services.features.mindmate_seminar.background_file_preview.mirror_cached_preview_pdf_sync",
        ),
    ):
        first = _ensure_preview_pdf_sync(source, "plan.docx", "2026/10/plan.docx")
        second = _ensure_preview_pdf_sync(source, "plan.docx", "2026/10/plan.docx")

    assert first == preview_cache_path(source)
    assert first.read_bytes() == b"%PDF-1.7 converted"
    assert second == first
    assert convert_mock.call_count == 1
    put_mock.assert_called_once()


def test_load_preview_bytes_drops_scratch_when_convert_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed convert still removes the work dir and the partial PDF."""
    source = tmp_path / "plan.docx"
    source.write_bytes(b"PK fake")
    scratch = tmp_path / "plan.docx.preview.pdf.tmp"
    work = tmp_path / ".preview-work-plan"
    scratch.write_bytes(b"partial")
    work.mkdir()
    monkeypatch.setattr(
        "services.features.mindmate_seminar.background_file_preview._materialize_source",
        lambda _storage_key: source,
    )

    def _fail(_source: Path, _filename: str, _storage_key: str) -> Path:
        raise ValueError("preview_failed")

    monkeypatch.setattr(
        "services.features.mindmate_seminar.background_file_preview._ensure_preview_pdf_sync",
        _fail,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: False,
    )

    with pytest.raises(ValueError, match="preview_failed"):
        _load_preview_bytes_sync("2026/10/plan.docx", "plan.docx")

    assert source.is_file()
    assert not scratch.exists()
    assert not work.exists()


def test_load_preview_bytes_drops_locals_once_cos_has_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """After the PDF is read, disk copies go away when the bucket has both objects."""
    source = tmp_path / "plan.docx"
    source.write_bytes(b"PK fake")
    preview = preview_cache_path(source)
    preview.write_bytes(b"%PDF-1.7 converted")
    monkeypatch.setattr(
        "services.features.mindmate_seminar.background_file_preview._materialize_source",
        lambda _storage_key: source,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.background_file_preview._ensure_preview_pdf_sync",
        lambda _source, _filename, _storage_key: preview,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage._cos_has_logical_key",
        lambda key: key in {"2026/10/plan.docx", "2026/10/plan.docx.preview.pdf"},
    )

    data = _load_preview_bytes_sync("2026/10/plan.docx", "plan.docx")

    assert data == b"%PDF-1.7 converted"
    assert not source.exists()
    assert not preview.exists()


def test_ensure_preview_pdf_sync_rejects_images() -> None:
    """Images stay on the image preview path, not PDF conversion."""
    with pytest.raises(ValueError, match="preview_unsupported"):
        _ensure_preview_pdf_sync(Path("photo.png"), "photo.png", "2026/10/photo.png")
