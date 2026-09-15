"""Disk catalog for MindMate teaching-design Word templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.mindmate.teaching_design_template_preview import (
    ensure_template_preview_pdf,
    preview_cache_path,
)
from services.mindmate.teaching_design_template_store import (
    BUNDLED_TEMPLATE_PATH,
    describe_active_template,
    describe_template_catalog,
    list_template_options,
    normalize_template_key,
    resolve_template_path,
    restore_bundled_template,
    save_uploaded_template,
    update_named_template,
    validate_docx_bytes,
)


@pytest.fixture(name="override_root", autouse=True)
def fixture_override_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point catalog files at a temp directory."""
    monkeypatch.setattr(
        "services.mindmate.teaching_design_template_paths.override_dir",
        lambda: tmp_path,
    )
    return tmp_path


def test_describe_bundled_lists_form_tables() -> None:
    """The committed BNU form is row 1 and the system default."""
    assert BUNDLED_TEMPLATE_PATH.is_file()
    catalog = describe_template_catalog()
    assert catalog["default_id"] == "bundled"
    assert catalog["templates"][0]["id"] == "bundled"
    assert catalog["templates"][0]["is_default"] is True
    status = describe_active_template()
    assert status["source"] == "bundled"
    assert len(status["tables"]) >= 1


def test_upload_adds_named_row_without_replacing_bundled() -> None:
    """Upload appends a catalog row; restore only moves the system default."""
    payload = BUNDLED_TEMPLATE_PATH.read_bytes()
    saved = save_uploaded_template(
        payload,
        original_filename="自定义教学设计.docx",
        uploaded_by_user_id=7,
        uploaded_by_name="王老师",
    )
    uploaded_rows = [row for row in saved["templates"] if row["source"] == "uploaded"]
    assert len(uploaded_rows) == 1
    assert uploaded_rows[0]["name"] == "自定义教学设计"
    assert uploaded_rows[0]["is_default"] is False
    assert saved["default_id"] == "bundled"
    uploaded_id = str(uploaded_rows[0]["id"])
    assert resolve_template_path(uploaded_id) != BUNDLED_TEMPLATE_PATH
    restored = restore_bundled_template(user_id=7)
    assert restored["default_id"] == "bundled"
    assert any(row["id"] == uploaded_id for row in restored["templates"])


def test_rename_and_pin_uploaded_template() -> None:
    """Admins can rename a row and make it the system default."""
    payload = BUNDLED_TEMPLATE_PATH.read_bytes()
    saved = save_uploaded_template(
        payload,
        original_filename="校级模板.docx",
        uploaded_by_user_id=1,
        uploaded_by_name="管理员",
    )
    uploaded_id = next(row["id"] for row in saved["templates"] if row["source"] == "uploaded")
    updated = update_named_template(uploaded_id, name="一年级模板", is_default=True)
    row = next(item for item in updated["templates"] if item["id"] == uploaded_id)
    assert row["name"] == "一年级模板"
    assert row["is_default"] is True
    assert updated["default_id"] == uploaded_id
    assert resolve_template_path(None) == resolve_template_path(uploaded_id)
    assert normalize_template_key(uploaded_id) == uploaded_id


def test_validate_rejects_non_docx() -> None:
    """Plain text cannot replace the official form."""
    with pytest.raises(ValueError, match="teaching_design_template_invalid"):
        validate_docx_bytes(b"not a word file")


def test_school_template_key_follows_system_or_pin() -> None:
    """Schools can follow the live system file or pin bundled / uploaded."""
    assert normalize_template_key("system") is None
    assert normalize_template_key("") is None
    assert normalize_template_key("bundled") == "bundled"
    with pytest.raises(ValueError, match="teaching_design_template_invalid_key"):
        normalize_template_key("uploaded")
    keys = {item["key"] for item in list_template_options()}
    assert keys == {"system", "bundled"}
    payload = BUNDLED_TEMPLATE_PATH.read_bytes()
    saved = save_uploaded_template(
        payload,
        original_filename="校级模板.docx",
        uploaded_by_user_id=1,
        uploaded_by_name="管理员",
    )
    uploaded_id = next(row["id"] for row in saved["templates"] if row["source"] == "uploaded")
    assert normalize_template_key(uploaded_id) == uploaded_id
    option_keys = {item["key"] for item in list_template_options()}
    assert uploaded_id in option_keys
    named = next(item for item in list_template_options() if item["key"] == uploaded_id)
    assert named["name"] == "校级模板"


def test_preview_pdf_is_cached_until_file_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """LibreOffice conversion runs once while the Word file is unchanged."""
    calls = {"count": 0}

    def fake_convert(source_path: Path, output_dir: Path) -> Path:
        calls["count"] += 1
        pdf = output_dir / f"{source_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    monkeypatch.setattr(
        "services.mindmate.teaching_design_template_preview.convert_office_to_pdf",
        fake_convert,
    )
    first = ensure_template_preview_pdf("bundled")
    second = ensure_template_preview_pdf("bundled")
    assert first == second
    assert first == preview_cache_path("bundled")
    assert first.read_bytes().startswith(b"%PDF-")
    assert calls["count"] == 1
