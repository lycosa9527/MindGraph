"""HTTP smoke: school_admin denied on superadmin-only settings panel routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Build a minimal user object for dependency overrides."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    user.phone = "13800138001"
    return user


@pytest.fixture(name="client")
def fixture_client():
    """HTTP client against the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear FastAPI dependency overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/admin/api_keys",
        "/api/auth/admin/admins",
    ],
)
def test_school_admin_denied_settings_panel_routes(client: TestClient, path: str) -> None:
    """School managers lack CAP_SETTINGS_* — migrated routes return 403."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get(path)
    assert response.status_code == 403
