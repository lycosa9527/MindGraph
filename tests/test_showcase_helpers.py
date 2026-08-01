"""Unit tests for Showcase helpers (no database required)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException

from models.domain.showcase import ShowcasePost
from routers.features.showcase.author_payload import author_payload
from routers.features.showcase.helpers import (
    ALLOWED_DOC_SUFFIXES,
    _validate_magic_bytes,
    showcase_public_asset_url,
    post_id_from_showcase_filename,
    resolve_showcase_disk_path,
)
from services.showcase.uploads.roles import assert_content_type_allowed


def _minimal_ooxml_zip(*member_names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in member_names:
            archive.writestr(name, "<?xml version='1.0'?><root/>")
    return buffer.getvalue()


def test_showcase_public_asset_url() -> None:
    """Build public asset URL for a showcase relative path."""
    assert showcase_public_asset_url("case_square/abc.png") == ("/api/showcase/assets/case_square/abc.png")
    post_id = "12345678-1234-4234-8234-123456789abc"
    key = f"showcase/posts/{post_id}/thumbnail.png"
    assert showcase_public_asset_url(key) == f"/api/showcase/assets/{key}"


def test_showcase_public_asset_url_rejects_other_prefixes() -> None:
    """Reject asset URLs for paths outside showcase prefixes."""
    with pytest.raises(ValueError, match="Not a showcase path"):
        showcase_public_asset_url("chat/abc.png")
    with pytest.raises(ValueError, match="Not a showcase path"):
        showcase_public_asset_url("https://bucket.cos.ap-guangzhou.myqcloud.com/x.png")


def test_post_id_from_showcase_filename() -> None:
    """Extract post UUID from standard showcase asset filenames."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    assert post_id_from_showcase_filename(f"{post_id}.png") == post_id
    assert post_id_from_showcase_filename(f"{post_id}_doc.pdf") == post_id
    assert post_id_from_showcase_filename("not-a-uuid.png") is None


def test_validate_magic_bytes_pdf_and_png() -> None:
    """Accept valid PDF/PNG magic bytes and reject mismatched content."""
    _validate_magic_bytes(b"%PDF-1.4\n", ".pdf")
    _validate_magic_bytes(b"\x89PNG\r\n\x1a\nxxxx", ".png")
    with pytest.raises(HTTPException) as exc:
        _validate_magic_bytes(b"not-a-pdf", ".pdf")
    assert exc.value.status_code == 400


def test_allowed_doc_suffixes_include_pptx() -> None:
    """Teaching-design allowlist accepts PPTX."""
    assert ".pptx" in ALLOWED_DOC_SUFFIXES


def test_validate_magic_bytes_pptx_accepts_presentation_xml() -> None:
    """Accept OOXML ZIP that contains ppt/presentation.xml."""
    payload = _minimal_ooxml_zip("[Content_Types].xml", "ppt/presentation.xml")
    _validate_magic_bytes(payload, ".pptx")


def test_validate_magic_bytes_pptx_rejects_docx_zip() -> None:
    """Reject a DOCX-shaped ZIP when the declared suffix is .pptx."""
    payload = _minimal_ooxml_zip("[Content_Types].xml", "word/document.xml")
    with pytest.raises(HTTPException) as exc:
        _validate_magic_bytes(payload, ".pptx")
    assert exc.value.status_code == 400


def test_content_type_allows_octet_stream_for_docs() -> None:
    """Browsers often send octet-stream for Office/PDF uploads."""
    assert_content_type_allowed(".pdf", "application/octet-stream")
    assert_content_type_allowed(".docx", "application/octet-stream")
    assert_content_type_allowed(".pptx", "application/octet-stream")
    assert_content_type_allowed(
        ".pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    with pytest.raises(ValueError):
        assert_content_type_allowed(".pptx", "image/png")


def test_resolve_showcase_disk_path_rejects_traversal(tmp_path: Path, monkeypatch) -> None:
    """Reject path traversal when resolving showcase disk paths."""
    monkeypatch.chdir(tmp_path)
    case_dir = tmp_path / "static" / "case_square"
    case_dir.mkdir(parents=True)
    (case_dir / "ok.txt").write_text("x", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        resolve_showcase_disk_path("case_square/../secrets.txt")
    assert exc.value.status_code == 404


def test_author_payload_missing_author_uses_profile_or_anonymous() -> None:
    """Cross-org RLS / deleted authors must not crash list formatting."""
    post = cast(
        ShowcasePost,
        SimpleNamespace(
            author_id=42,
            author=None,
            publish_source="self",
            attribution=None,
        ),
    )
    anonymous = author_payload(post)
    assert anonymous["id"] == 42
    assert anonymous["name"] == "Anonymous"
    assert anonymous["avatar"] == "👤"
    assert anonymous["organization"] is None
    assert anonymous["is_proxy"] is False

    profiled = author_payload(
        post,
        {
            "name": "李老师",
            "avatar": "👩‍🏫",
            "organization": "示例学校",
        },
    )
    assert profiled["name"] == "李老师"
    assert profiled["avatar"] == "👩‍🏫"
    assert profiled["organization"] == "示例学校"


def test_author_payload_proxy_works_without_author_row() -> None:
    """Proxy attribution still formats when author relationship is missing."""
    post = cast(
        ShowcasePost,
        SimpleNamespace(
            author_id=7,
            author=None,
            publish_source="proxy",
            attribution={"display_name": "代理教师", "organization": "外校"},
        ),
    )
    payload = author_payload(post)
    assert payload["name"] == "代理教师"
    assert payload["organization"] == "外校"
    assert payload["is_proxy"] is True
    assert payload["avatar"] == "👤"
