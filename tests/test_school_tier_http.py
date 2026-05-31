"""HTTP-level school tier feature gating tests."""

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
    user.phone = "13800000001"
    return user


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(name="trial_org_user")
def fixture_trial_org_user(monkeypatch: pytest.MonkeyPatch):
    user = _make_user("teacher", organization_id=8)

    async def _trial_org(_db, _user):
        return SimpleNamespace(id=8, school_tier="trial")

    monkeypatch.setattr(
        "utils.auth.school_tier.is_superadmin",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _trial_org,
    )
    return user


@pytest.fixture(name="lite_org_user")
def fixture_lite_org_user(monkeypatch: pytest.MonkeyPatch):
    user = _make_user("teacher", organization_id=7)

    async def _lite_org(_db, _user):
        return SimpleNamespace(id=7, school_tier="lite")

    monkeypatch.setattr(
        "utils.auth.school_tier.is_superadmin",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _lite_org,
    )
    return user


def test_lite_tier_denied_workshop_start(
    client: TestClient,
    lite_org_user: SimpleNamespace,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: lite_org_user
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    response = client.post("/api/diagrams/diag-1/workshop/start")
    assert response.status_code == 403


def test_lite_tier_denied_api_token_mint(
    client: TestClient,
    lite_org_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: lite_org_user
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    async def _no_rate_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "routers.auth.personal_token.check_endpoint_rate_limit",
        _no_rate_limit,
    )

    response = client.post("/api/auth/api-token")
    assert response.status_code == 403


def test_trial_tier_denied_workshop_start(
    client: TestClient,
    trial_org_user: SimpleNamespace,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: trial_org_user
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    response = client.post("/api/diagrams/diag-1/workshop/start")
    assert response.status_code == 403


def test_trial_tier_denied_api_token_mint(
    client: TestClient,
    trial_org_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: trial_org_user
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    async def _no_rate_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "routers.auth.personal_token.check_endpoint_rate_limit",
        _no_rate_limit,
    )

    response = client.post("/api/auth/api-token")
    assert response.status_code == 403
