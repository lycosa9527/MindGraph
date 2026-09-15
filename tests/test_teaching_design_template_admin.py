"""HTTP tests for the admin teaching-design template endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.auth.admin.teaching_design_template import router
from routers.auth.dependencies import (
    require_organizations_read,
    require_settings_teaching_design,
    require_tab_settings_edit,
)
from services.mindmate.teaching_design_template_store import BUNDLED_TEMPLATE_PATH
from utils.auth.admin_panel_permissions import (
    CAP_SETTINGS_TEACHING_DESIGN,
    CAP_TAB_SETTINGS_EDIT,
)
from utils.auth.admin_scope import AdminScope

app = FastAPI()
app.include_router(router, prefix="/api/auth")


def _super_scope() -> AdminScope:
    """Super-admin actor used as a FastAPI dependency override."""
    return AdminScope(
        actor=SimpleNamespace(id=1, name="管理员"),
        role="superadmin",
        capabilities=frozenset({CAP_SETTINGS_TEACHING_DESIGN, CAP_TAB_SETTINGS_EDIT}),
        org_ids=None,
        effective_org_id=None,
        read_only=False,
    )


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the teaching-design template admin router."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides_and_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Isolate catalog files and FastAPI dependencies per test."""
    monkeypatch.setattr(
        "services.mindmate.teaching_design_template_paths.override_dir",
        lambda: tmp_path,
    )
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_template_options_for_school_modal(client: TestClient) -> None:
    """School editors can list selectable template keys."""
    app.dependency_overrides[require_organizations_read] = _super_scope
    response = client.get("/api/auth/admin/teaching-design-template/options")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["options"]}
    assert keys == {"system", "bundled"}


def test_template_catalog_lists_bundled_row(client: TestClient) -> None:
    """The landing table always includes the built-in form."""
    app.dependency_overrides[require_settings_teaching_design] = _super_scope
    response = client.get("/api/auth/admin/teaching-design-template")
    assert response.status_code == 200
    body = response.json()
    assert body["default_id"] == "bundled"
    assert body["templates"][0]["id"] == "bundled"
    assert body["templates"][0]["index"] == 1


def test_upload_rename_and_restore_round_trip(client: TestClient) -> None:
    """Upload adds a named row; restore only resets the system default."""
    app.dependency_overrides[require_settings_teaching_design] = _super_scope
    app.dependency_overrides[require_tab_settings_edit] = _super_scope
    payload = BUNDLED_TEMPLATE_PATH.read_bytes()
    uploaded = client.post(
        "/api/auth/admin/teaching-design-template",
        files={
            "file": (
                "custom.docx",
                payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert uploaded.status_code == 200
    rows = uploaded.json()["templates"]
    custom = next(row for row in rows if row["source"] == "uploaded")
    patched = client.patch(
        f"/api/auth/admin/teaching-design-template/{custom['id']}",
        json={"name": "模板 1", "is_default": True},
    )
    assert patched.status_code == 200
    renamed = next(row for row in patched.json()["templates"] if row["id"] == custom["id"])
    assert renamed["name"] == "模板 1"
    assert patched.json()["default_id"] == custom["id"]
    restored = client.post("/api/auth/admin/teaching-design-template/restore")
    assert restored.status_code == 200
    assert restored.json()["default_id"] == "bundled"
    assert any(row["id"] == custom["id"] for row in restored.json()["templates"])


def test_preview_returns_cached_pdf(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Name-click preview serves a PDF converted from the Word template."""
    app.dependency_overrides[require_settings_teaching_design] = _super_scope

    def fake_convert(source_path: Path, output_dir: Path) -> Path:
        pdf = output_dir / f"{source_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    monkeypatch.setattr(
        "services.mindmate.teaching_design_template_preview.convert_office_to_pdf",
        fake_convert,
    )
    response = client.get("/api/auth/admin/teaching-design-template/bundled/preview")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    assert "pdf" in (response.headers.get("content-type") or "")
