"""Showcase end-to-end smoke: create → init → complete → download → withdraw."""

from __future__ import annotations

import io
import os
import urllib.request
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import text

from config.database import AsyncSessionLocal, engine, get_async_db
from config.settings import config
from main import app
from services.showcase import storage
from services.showcase.storage import backend as storage_backend
from services.utils.error_types import DATABASE_ERRORS
from services.utils.tencent_cos_client import list_prefix
from utils.auth import get_current_user
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.db.rls_context import RlsContext, reset_rls_context, set_rls_context

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _showcase_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM case_square_posts LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_showcase_schema = pytest.mark.skipif(
    not _showcase_schema_ready(),
    reason="showcase schema not migrated (CI has no Postgres)",
)

requires_cos_smoke = pytest.mark.skipif(
    os.environ.get("COS_SHOWCASE_SMOKE", "").strip() not in ("1", "true", "yes"),
    reason="Set COS_SHOWCASE_SMOKE=1 with live COS credentials",
)


def _make_user(user_id: int = 61) -> SimpleNamespace:
    org = SimpleNamespace(name="Smoke School")
    user = SimpleNamespace()
    user.id = user_id
    user.name = "Showcase Smoke"
    user.phone = None
    user.avatar = None
    user.role = "teacher"
    user.organization_id = 1
    user.organization = org
    return user


async def _override_get_async_db(request: Request):
    user = _make_user()
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
    """HTTP test client for Showcase smoke routes."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def enable_showcase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable FEATURE_SHOWCASE for every test in this module."""
    monkeypatch.setenv("FEATURE_SHOWCASE", "true")
    config.refresh_env_cache()


@requires_showcase_schema
def test_local_e2e_create_upload_download_withdraw(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local backend: metadata create → init → complete → GET asset → withdraw."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage_backend, "cos_showcase_enabled", lambda: False)
    monkeypatch.setattr(
        "routers.features.showcase_routes_uploads.cos_showcase_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "routers.features.showcase_routes_feed.cos_showcase_enabled",
        lambda: False,
    )

    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create = client.post(
        "/api/showcase/posts",
        data={
            "title": "smoke local case",
            "description": "e2e",
            "tags": "[]",
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "一年级",
            "diagram_type": "mind_map",
            "spec": '{"type":"mind_map","topic":"smoke"}',
        },
    )
    assert create.status_code == 200, create.text
    post_id = create.json()["post"]["id"]

    init = client.post(
        f"/api/showcase/posts/{post_id}/uploads/init",
        json={
            "role": "thumbnail",
            "filename": "thumbnail.png",
            "content_type": "image/png",
            "size_bytes": len(PNG_BYTES),
        },
    )
    assert init.status_code == 200, init.text
    init_body = init.json()
    assert init_body["put_url"] is None
    key = init_body["key"]
    assert key.startswith(f"showcase/posts/{post_id}/")

    complete = client.post(
        f"/api/showcase/posts/{post_id}/uploads/complete",
        data={"role": "thumbnail", "key": key, "filename": "thumbnail.png"},
        files={"file": ("thumbnail.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["key"] == key

    disk = storage.local_path_for_key(key)
    assert disk.is_file()

    download = client.get(f"/api/showcase/assets/{key}")
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"\x89PNG")

    withdraw = client.post(f"/api/showcase/posts/{post_id}/withdraw")
    assert withdraw.status_code == 200, withdraw.text
    assert not disk.exists()


@requires_showcase_schema
@requires_cos_smoke
def test_cos_e2e_presign_put_complete_and_cleanup(client: TestClient) -> None:
    """Live COS: init → PUT → complete → withdraw leaves no post prefix objects."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled / credentials missing")

    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    create = client.post(
        "/api/showcase/posts",
        data={
            "title": "smoke cos case",
            "description": "e2e cos",
            "tags": "[]",
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "一年级",
            "diagram_type": "mind_map",
            "spec": '{"type":"mind_map","topic":"smoke-cos"}',
        },
    )
    assert create.status_code == 200, create.text
    post_id = create.json()["post"]["id"]

    init = client.post(
        f"/api/showcase/posts/{post_id}/uploads/init",
        json={
            "role": "thumbnail",
            "filename": "thumbnail.png",
            "content_type": "image/png",
            "size_bytes": len(PNG_BYTES),
        },
    )
    assert init.status_code == 200, init.text
    init_body = init.json()
    put_url = init_body.get("put_url")
    key = init_body["key"]
    assert put_url
    headers = init_body.get("headers") or {"Content-Type": "image/png"}

    req = urllib.request.Request(
        put_url,
        data=PNG_BYTES,
        method="PUT",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        assert 200 <= resp.status < 300

    complete = client.post(
        f"/api/showcase/posts/{post_id}/uploads/complete",
        json={"role": "thumbnail", "key": key, "filename": "thumbnail.png"},
    )
    assert complete.status_code == 200, complete.text

    download = client.get(f"/api/showcase/assets/{key}", follow_redirects=False)
    assert download.status_code in (200, 302), download.text

    withdraw = client.post(f"/api/showcase/posts/{post_id}/withdraw")
    assert withdraw.status_code == 200, withdraw.text

    leftovers = list_prefix(storage.full_cos_key(f"showcase/posts/{post_id}/"))
    assert not leftovers
