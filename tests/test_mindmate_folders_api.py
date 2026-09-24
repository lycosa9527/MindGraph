"""Integration tests for MindMate conversation folder API."""

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


def _mindmate_folders_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM mindmate_folders LIMIT 0"))
            conn.execute(text("SELECT 1 FROM mindmate_conversation_folders LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_mindmate_folders_schema = pytest.mark.skipif(
    not _mindmate_folders_schema_ready(),
    reason="mindmate_folders schema not migrated (CI has no Postgres)",
)


def _make_user(user_id: int = 6) -> SimpleNamespace:
    org = SimpleNamespace(name="Test School")
    user = SimpleNamespace()
    user.id = user_id
    user.name = "MindMate Folder Test"
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


@requires_mindmate_folders_schema
def test_mindmate_folder_lifecycle(client: TestClient) -> None:
    """Create folder, move conversation, rename, and delete folder."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create_folder = client.post("/api/mindmate-folders", json={"name": "pytest mindmate"})
    assert create_folder.status_code == 200, create_folder.text
    folder_id = create_folder.json()["id"]
    conversation_id = "11111111-1111-4111-8111-111111111111"

    move = client.put(
        f"/api/mindmate-folders/conversations/{conversation_id}",
        json={"folder_id": folder_id},
    )
    assert move.status_code == 200, move.text
    assert move.json()["folder_id"] == folder_id

    listed = client.get("/api/mindmate-folders")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert any(folder["id"] == folder_id for folder in body["folders"])
    assert {"conversation_id": conversation_id, "folder_id": folder_id} in body["assignments"]

    renamed = client.patch(f"/api/mindmate-folders/{folder_id}", json={"name": "renamed mindmate"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "renamed mindmate"

    deleted = client.delete(f"/api/mindmate-folders/{folder_id}")
    assert deleted.status_code == 200, deleted.text

    listed_after = client.get("/api/mindmate-folders")
    assert listed_after.status_code == 200, listed_after.text
    after = listed_after.json()
    assert all(folder["id"] != folder_id for folder in after["folders"])
    assert all(row["conversation_id"] != conversation_id for row in after["assignments"])


@requires_mindmate_folders_schema
def test_mindmate_folder_idor_other_user_denied(client: TestClient) -> None:
    """User B must not rename, delete, or receive User A's folder."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(6)
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create_folder = client.post("/api/mindmate-folders", json={"name": "owner mindmate"})
    assert create_folder.status_code == 200, create_folder.text
    folder_id = create_folder.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: _make_user(7)

    rename = client.patch(f"/api/mindmate-folders/{folder_id}", json={"name": "hijacked"})
    assert rename.status_code in (403, 404), rename.text

    move = client.put(
        "/api/mindmate-folders/conversations/22222222-2222-4222-8222-222222222222",
        json={"folder_id": folder_id},
    )
    assert move.status_code in (403, 404), move.text

    delete_folder = client.delete(f"/api/mindmate-folders/{folder_id}")
    assert delete_folder.status_code in (403, 404), delete_folder.text

    app.dependency_overrides[get_current_user] = lambda: _make_user(6)
    cleanup = client.delete(f"/api/mindmate-folders/{folder_id}")
    assert cleanup.status_code == 200, cleanup.text
