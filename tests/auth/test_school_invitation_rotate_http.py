"""School-dashboard invitation-code rotation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from models.domain.auth import Organization
from routers.auth.dependencies import get_async_db_with_request_rls, get_language_dependency
from services.auth.rotate_invitation_code import rotate_organization_invitation_code
from utils.auth import get_current_user
from utils.invitations import invitation_code_is_valid

_PATH = "/api/auth/admin/school/invitation-code/rotate"


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


def test_teacher_cannot_rotate_invitation_code(client: TestClient) -> None:
    """Teachers have no school-member edit capability."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("teacher", 42)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.post(_PATH, params={"organization_id": 42})
    assert response.status_code == 403


async def _db_session_without_postgres():
    """Yield a session stand-in so the capability check does not open Postgres."""
    yield AsyncMock()


def test_platform_bd_cannot_rotate_invitation_code(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read-only panel roles cannot retire a school's invitation code."""
    monkeypatch.setattr(
        "utils.auth.admin_scope.load_expert_invited_org_ids",
        AsyncMock(return_value=frozenset()),
    )
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db_with_request_rls] = _db_session_without_postgres
    response = client.post(_PATH, params={"organization_id": 42})
    assert response.status_code == 403


def test_school_admin_cannot_rotate_another_school(client: TestClient) -> None:
    """A school manager is locked to their own organization."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("school_admin", 42)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.post(_PATH, params={"organization_id": 99})
    assert response.status_code == 403


def _org() -> SimpleNamespace:
    """Organization stand-in with the fields rotation reads."""
    return SimpleNamespace(id=7, invitation_code="ABC-DEF", name="School", code="SCH")


def _db_without_collision() -> AsyncMock:
    """Session that reports no invitation-code collision."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_rotate_persists_a_new_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """A free code is saved and the previous code is dropped from the org cache."""
    org = _org()

    async def _no_cache(_code: str) -> None:
        return None

    async def _write_through(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(
        "services.auth.rotate_invitation_code.org_cache.get_by_invitation_code",
        _no_cache,
    )
    monkeypatch.setattr(
        "services.auth.rotate_invitation_code.org_cache.write_through",
        _write_through,
    )

    code = await rotate_organization_invitation_code(_db_without_collision(), cast(Organization, org), "en")
    assert code != "ABC-DEF"
    assert invitation_code_is_valid(code)
    assert org.invitation_code == code


@pytest.mark.asyncio
async def test_rotate_stops_when_every_code_collides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated collisions leave the current code in place."""
    org = _org()

    async def _taken(_code: str) -> SimpleNamespace:
        return SimpleNamespace(id=99)

    monkeypatch.setattr(
        "services.auth.rotate_invitation_code.generate_invitation_code",
        lambda *_args, **_kwargs: "AAA-BBB",
    )
    monkeypatch.setattr(
        "services.auth.rotate_invitation_code.org_cache.get_by_invitation_code",
        _taken,
    )

    with pytest.raises(HTTPException) as raised:
        await rotate_organization_invitation_code(_db_without_collision(), cast(Organization, org), "en")
    assert raised.value.status_code == 500
    assert org.invitation_code == "ABC-DEF"
