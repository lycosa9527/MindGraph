"""HTTP-level MindBot admin org-scope tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_school_admin_denied_mindbot_admin(client: TestClient) -> None:
    """School admins no longer have MindBot admin access (matrix alignment)."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/mindbot/admin/configs/1")
    assert response.status_code == 403


def test_school_admin_cross_org_mindbot_config_denied(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    async def _allow_feature(_user, _feature):
        return True

    async def _fake_config(_config_id, _db):
        return SimpleNamespace(organization_id=99)

    def _noop_feature():
        return None

    def _fake_response(row, school_manager_view=False):
        return {"id": 1, "organization_id": row.organization_id}

    monkeypatch.setattr(
        "routers.auth.dependencies.user_has_feature_access",
        _allow_feature,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._require_mindbot_feature",
        _noop_feature,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._get_config_or_404",
        _fake_config,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._to_response",
        _fake_response,
    )

    response = client.get("/api/mindbot/admin/configs/1")
    assert response.status_code == 403
