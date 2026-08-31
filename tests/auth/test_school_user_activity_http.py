"""HTTP gates for school user-activity analytics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user

_PATH = "/api/auth/admin/stats/school/user-activity"


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Make a lightweight actor for dependency overrides."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    user.phone = "13800000000"
    return user


@pytest.fixture(name="client")
def fixture_client():
    """HTTP client bound to the app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear FastAPI overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_school_admin_forbidden_user_activity(client: TestClient) -> None:
    """School managers cannot open the activity analytics API."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("school_admin", 42)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get(_PATH, params={"organization_id": 42})
    assert response.status_code == 403


def test_platform_bd_forbidden_user_activity(client: TestClient) -> None:
    """Teaching researchers cannot open the activity analytics API."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get(_PATH, params={"organization_id": 42})
    assert response.status_code == 403


def test_superadmin_requires_organization_id(client: TestClient) -> None:
    """Superadmin must pick a school."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get(_PATH)
    assert response.status_code == 400


def test_superadmin_future_year_rejected(client: TestClient) -> None:
    """Future years are rejected."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    with patch(
        "routers.auth.admin.school_user_activity.resolve_school_dashboard_org_id_scoped",
        new=AsyncMock(return_value=42),
    ):
        with patch(
            "routers.auth.admin.school_user_activity.build_school_user_activity",
            new=AsyncMock(side_effect=ValueError("invalid_year")),
        ):
            with patch(
                "routers.auth.admin.school_user_activity.apply_rls_context_async",
                new=AsyncMock(),
            ):
                response = client.get(_PATH, params={"organization_id": 42, "year": 4099})
    assert response.status_code == 400
    assert "Invalid year" in response.text


def test_superadmin_response_shape(client: TestClient) -> None:
    """Successful payload includes snapshot metadata and three sections."""
    payload = {
        "year": 2026,
        "min_year": 2024,
        "generated_at": "2026-09-01T00:15:00Z",
        "totals": {
            "cumulative_registered": 1,
            "year_new_users": 0,
            "churn_available": False,
            "enrolled_today": 1,
            "cumulative_series": [],
            "year_new_series": [],
            "enrolled_series": [],
        },
        "activity": {
            "daily_active": [],
            "monthly_active": [],
            "quarterly_active": [],
            "avg_daily_active": 0.0,
            "avg_monthly_active": 0.0,
        },
        "frequency": {
            "login_count_buckets": [],
            "high_freq_count": 0,
            "high_freq_share": 0.0,
            "low_freq_count": 0,
            "low_freq_share": 0.0,
            "hour_of_day": [],
        },
    }
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    with patch(
        "routers.auth.admin.school_user_activity.resolve_school_dashboard_org_id_scoped",
        new=AsyncMock(return_value=42),
    ):
        with patch(
            "routers.auth.admin.school_user_activity.build_school_user_activity",
            new=AsyncMock(return_value=payload),
        ):
            with patch(
                "routers.auth.admin.school_user_activity.apply_rls_context_async",
                new=AsyncMock(),
            ):
                response = client.get(_PATH, params={"organization_id": 42})
    assert response.status_code == 200
    body = response.json()
    assert body["generated_at"] == "2026-09-01T00:15:00Z"
    assert body["min_year"] == 2024
    assert body["totals"]["churn_available"] is False
    assert "daily_active" in body["activity"]
    assert "hour_of_day" in body["frequency"]
