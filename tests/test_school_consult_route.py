"""HTTP tests for school consultation route."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from services.integrations.wecom.types import WeComNotifyResult
from utils.auth import get_current_user


def _make_user(user_id: int = 42) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = None
    user.phone = "13800000001"
    user.display_name = "Test User"
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """FastAPI test client for school consultation routes."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset auth overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(name="authed_user")
def fixture_authed_user() -> SimpleNamespace:
    """Authenticated teacher user with dependency override."""
    user = _make_user()
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def test_school_consultation_requires_auth(client: TestClient) -> None:
    """Unauthenticated requests are rejected."""
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={"name": "A", "phone": "1", "organization": "School"},
    )
    assert response.status_code == 401


def test_school_consultation_validation(client: TestClient, authed_user: SimpleNamespace) -> None:
    """Missing required fields return 422."""
    _ = authed_user
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={"name": "", "phone": "1", "organization": "School"},
    )
    assert response.status_code == 422


def test_school_consultation_rejects_invalid_phone(
    client: TestClient,
    authed_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tampered phone values are rejected before WeCom send."""

    async def _no_rate_limit(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "routers.auth.thinking_coins.check_endpoint_rate_limit",
        _no_rate_limit,
    )

    _ = authed_user
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={"name": "张三", "phone": "not-a-phone", "organization": "测试学校"},
    )
    assert response.status_code == 422


def test_school_consultation_not_configured(
    client: TestClient,
    authed_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """503 when WeCom profile is not configured."""

    async def _no_rate_limit(*_args, **_kwargs) -> None:
        return None

    async def _not_configured(*_args, **_kwargs) -> WeComNotifyResult:
        return WeComNotifyResult(profile_id="school_consult", ok=False, not_configured=True)

    monkeypatch.setattr(
        "routers.auth.thinking_coins.check_endpoint_rate_limit",
        _no_rate_limit,
    )
    monkeypatch.setattr(
        "routers.auth.thinking_coins.send_school_consult_notification",
        _not_configured,
    )

    _ = authed_user
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={"name": "张三", "phone": "13800000000", "organization": "测试学校"},
    )
    assert response.status_code == 503


def test_school_consultation_delivery_failed(
    client: TestClient,
    authed_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """502 when all WeCom channels fail."""

    async def _no_rate_limit(*_args, **_kwargs) -> None:
        return None

    async def _failed(*_args, **_kwargs) -> WeComNotifyResult:
        return WeComNotifyResult(profile_id="school_consult", ok=False, not_configured=False)

    monkeypatch.setattr(
        "routers.auth.thinking_coins.check_endpoint_rate_limit",
        _no_rate_limit,
    )
    monkeypatch.setattr(
        "routers.auth.thinking_coins.send_school_consult_notification",
        _failed,
    )

    _ = authed_user
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={"name": "张三", "phone": "13800000000", "organization": "测试学校"},
    )
    assert response.status_code == 502


def test_school_consultation_success(
    client: TestClient,
    authed_user: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 ok when notification delivery succeeds."""

    async def _no_rate_limit(*_args, **_kwargs) -> None:
        return None

    async def _ok(*_args, **_kwargs) -> WeComNotifyResult:
        return WeComNotifyResult(profile_id="school_consult", ok=True)

    monkeypatch.setattr(
        "routers.auth.thinking_coins.check_endpoint_rate_limit",
        _no_rate_limit,
    )
    monkeypatch.setattr(
        "routers.auth.thinking_coins.send_school_consult_notification",
        _ok,
    )

    _ = authed_user
    response = client.post(
        "/api/auth/thinking-coins/school-consultation",
        json={
            "name": "张三",
            "phone": "13800000000",
            "organization": "测试学校",
            "note": "需要私有化部署",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
