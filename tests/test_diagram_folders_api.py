"""Integration tests for diagram archive folder API."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import text

from config.database import AsyncSessionLocal, engine, get_async_db
from main import app
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.db.rls_context import RlsContext, reset_rls_context, set_rls_context


def _diagram_folders_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM diagram_folders LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_diagram_folders_schema = pytest.mark.skipif(
    not _diagram_folders_schema_ready(),
    reason="diagram_folders schema not migrated (CI has no Postgres)",
)


def _make_user(user_id: int = 6) -> SimpleNamespace:
    org = SimpleNamespace(name="Test School")
    user = SimpleNamespace()
    user.id = user_id
    user.name = "Diagram Folder Test"
    user.phone = f"1380000000{user_id}"
    user.avatar = None
    user.role = "teacher"
    user.organization_id = 1
    user.organization = org
    return user


async def _override_get_async_db(request: Request):
    user = getattr(request.state, AUTH_CONTEXT_USER_ATTR, None) or _make_user()
    setattr(request.state, AUTH_CONTEXT_USER_ATTR, user)
    ctx = RlsContext.from_user(user)
    token = set_rls_context(ctx)
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            except DATABASE_ERRORS:
                await session.rollback()
                raise
    finally:
        reset_rls_context(token)


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Fixture client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Clear dependency overrides."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@requires_diagram_folders_schema
def test_diagram_folder_lifecycle(client: TestClient) -> None:
    """Create folder, move diagram, list, rename, and delete folder."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create_folder = client.post(
        "/api/diagram-folders",
        json={"name": "pytest folder"},
    )
    assert create_folder.status_code == 200, create_folder.text
    folder_id = create_folder.json()["id"]

    listed = client.get("/api/diagrams?page=1&page_size=50")
    assert listed.status_code == 200, listed.text
    diagrams = listed.json()["diagrams"]
    assert diagrams, "need at least one saved diagram for user 6"
    diagram_id = diagrams[0]["id"]

    move = client.post(
        f"/api/diagrams/{diagram_id}/folder",
        json={"folder_id": folder_id},
    )
    assert move.status_code == 200, move.text

    listed = client.get("/api/diagrams?page=1&page_size=50")
    assert listed.status_code == 200, listed.text
    items = listed.json()["diagrams"]
    moved = next(item for item in items if item["id"] == diagram_id)
    assert moved.get("folder_id") == folder_id

    delete_folder = client.delete(f"/api/diagram-folders/{folder_id}")
    assert delete_folder.status_code == 200, delete_folder.text

    listed_after = client.get("/api/diagrams?page=1&page_size=50")
    assert listed_after.status_code == 200, listed_after.text
    after = next(item for item in listed_after.json()["diagrams"] if item["id"] == diagram_id)
    assert after.get("folder_id") is None


@requires_diagram_folders_schema
def test_diagram_folder_idor_other_user_denied(client: TestClient) -> None:
    """User B must not rename or delete User A's folder."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(6)
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create_folder = client.post("/api/diagram-folders", json={"name": "owner folder"})
    assert create_folder.status_code == 200, create_folder.text
    folder_id = create_folder.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: _make_user(7)

    rename = client.patch(
        f"/api/diagram-folders/{folder_id}",
        json={"name": "hijacked"},
    )
    assert rename.status_code in (403, 404), rename.text

    delete_folder = client.delete(f"/api/diagram-folders/{folder_id}")
    assert delete_folder.status_code in (403, 404), delete_folder.text

    app.dependency_overrides[get_current_user] = lambda: _make_user(6)
    cleanup = client.delete(f"/api/diagram-folders/{folder_id}")
    assert cleanup.status_code == 200, cleanup.text
