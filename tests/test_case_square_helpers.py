"""Unit tests for Case Square helpers (no database required)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from routers.features.case_square_helpers import (
    _validate_magic_bytes,
    case_square_public_asset_url,
    post_id_from_case_square_filename,
    resolve_case_square_disk_path,
)


def test_case_square_public_asset_url() -> None:
    """Build public asset URL for a case_square relative path."""
    assert case_square_public_asset_url("case_square/abc.png") == ("/api/case-square/assets/case_square/abc.png")


def test_case_square_public_asset_url_rejects_other_prefixes() -> None:
    """Reject asset URLs for paths outside case_square/."""
    with pytest.raises(ValueError, match="Not a case_square path"):
        case_square_public_asset_url("chat/abc.png")


def test_post_id_from_case_square_filename() -> None:
    """Extract post UUID from standard case_square asset filenames."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    assert post_id_from_case_square_filename(f"{post_id}.png") == post_id
    assert post_id_from_case_square_filename(f"{post_id}_doc.pdf") == post_id
    assert post_id_from_case_square_filename("not-a-uuid.png") is None


def test_validate_magic_bytes_pdf_and_png() -> None:
    """Accept valid PDF/PNG magic bytes and reject mismatched content."""
    _validate_magic_bytes(b"%PDF-1.4\n", ".pdf")
    _validate_magic_bytes(b"\x89PNG\r\n\x1a\nxxxx", ".png")
    with pytest.raises(HTTPException) as exc:
        _validate_magic_bytes(b"not-a-pdf", ".pdf")
    assert exc.value.status_code == 400


def test_resolve_case_square_disk_path_rejects_traversal(tmp_path: Path, monkeypatch) -> None:
    """Reject path traversal when resolving case_square disk paths."""
    monkeypatch.chdir(tmp_path)
    case_dir = tmp_path / "static" / "case_square"
    case_dir.mkdir(parents=True)
    (case_dir / "ok.txt").write_text("x", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        resolve_case_square_disk_path("case_square/../secrets.txt")
    assert exc.value.status_code == 404
