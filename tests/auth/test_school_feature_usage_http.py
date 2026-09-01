"""HTTP gates for school feature-usage analytics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user

_PATH = "/api/auth/admin/stats/school/feature-usage"


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


def test_school_admin_forbidden_feature_usage(client: TestClient) -> None:
    """School managers cannot open the feature-usage analytics API."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("school_admin", 42)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get(_PATH, params={"organization_id": 42})
    assert response.status_code == 403


def test_platform_bd_forbidden_feature_usage(client: TestClient) -> None:
    """Teaching researchers cannot open the feature-usage analytics API."""
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
        "routers.auth.admin.school_feature_usage.resolve_school_dashboard_org_id_scoped",
        new=AsyncMock(return_value=42),
    ):
        with patch(
            "routers.auth.admin.school_feature_usage.build_school_feature_usage",
            new=AsyncMock(side_effect=ValueError("invalid_year")),
        ):
            with patch(
                "routers.auth.admin.school_feature_usage.apply_rls_context_async",
                new=AsyncMock(),
            ):
                response = client.get(_PATH, params={"organization_id": 42, "year": 4099})
    assert response.status_code == 400
    assert "Invalid year" in response.text


def test_superadmin_response_shape(client: TestClient) -> None:
    """Successful payload includes modules and judgement slots, not prose."""
    payload = {
        "year": 2026,
        "min_year": 2024,
        "generated_at": "2026-09-01T00:15:00Z",
        "enrolled": 2,
        "modules": [
            {
                "key": "canvas",
                "visits": 1,
                "uses": 3,
                "ops_per_visitor": 3.0,
                "completed": 3,
                "pass_rate": 100.0,
                "fail_rate": 12.5,
                "avg_duration_seconds": 2.4,
                "capacity": "ample",
                "monthly_uses": [{"date": "2026-01", "value": 3}],
            }
        ],
        "judgement": {
            "top5": [{"key": "canvas", "visits": 1, "uses": 3, "usage_rate": 50.0}],
            "high": [],
            "low": [],
            "idle": ["askonce"],
            "bottleneck_slots": {
                "lowest_pass_keys": [],
                "tense_keys": [],
                "slow_keys": [],
                "uniformly_high": True,
                "no_bottleneck": True,
            },
            "conclusion_slots": {
                "top_keys": ["canvas"],
                "idle_keys": ["askonce"],
                "concentrated": True,
            },
        },
    }
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    with patch(
        "routers.auth.admin.school_feature_usage.resolve_school_dashboard_org_id_scoped",
        new=AsyncMock(return_value=42),
    ):
        with patch(
            "routers.auth.admin.school_feature_usage.build_school_feature_usage",
            new=AsyncMock(return_value=payload),
        ):
            with patch(
                "routers.auth.admin.school_feature_usage.apply_rls_context_async",
                new=AsyncMock(),
            ):
                response = client.get(_PATH, params={"organization_id": 42})
    assert response.status_code == 200
    body = response.json()
    assert body["generated_at"] == "2026-09-01T00:15:00Z"
    assert body["modules"][0]["key"] == "canvas"
    assert body["modules"][0]["fail_rate"] == 12.5
    assert body["modules"][0]["avg_duration_seconds"] == 2.4
    assert "bottleneck_slots" in body["judgement"]
    assert "conclusion_slots" in body["judgement"]
    assert "研判" not in response.text
