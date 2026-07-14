"""Case Square create endpoint must return JSON-serializable responses."""

from __future__ import annotations

import io
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
from routers.features.case_square import _format_gallery_items
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.db.rls_context import RlsContext, reset_rls_context, set_rls_context


def _case_square_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM case_square_posts LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_case_square_schema = pytest.mark.skipif(
    not _case_square_schema_ready(),
    reason="case_square schema not migrated (CI has no Postgres)",
)


def _make_user(user_id: int = 6) -> SimpleNamespace:
    org = SimpleNamespace(name="Test School")
    user = SimpleNamespace()
    user.id = user_id
    user.name = "Case Square Test"
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
    """Fixture client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Clear dependency overrides."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def enable_case_square(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable FEATURE_CASE_SQUARE for every test in this module."""
    monkeypatch.setenv("FEATURE_CASE_SQUARE", "true")
    config.refresh_env_cache()


@requires_case_square_schema
def test_create_teaching_design_response_is_json(client: TestClient) -> None:
    """Create teaching_design post returns JSON-serializable response."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    response = client.post(
        "/api/case-square/posts",
        data={
            "title": "integration test case",
            "description": "",
            "tags": "[]",
            "case_type": "teaching_design",
            "subject": "数学",
            "grade": "一年级",
        },
        files={"attachment": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"]
    post = body["post"]
    assert post["id"]
    assert post["title"] == "integration test case"
    assert isinstance(post["can_withdraw"], bool)
    assert isinstance(post["can_delist"], bool)
    assert isinstance(post["can_resubmit"], bool)


@requires_case_square_schema
def test_create_diagram_case_without_thumbnail_response_is_json(client: TestClient) -> None:
    """Create diagram_case without thumbnail returns JSON-serializable response."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    response = client.post(
        "/api/case-square/posts",
        data={
            "title": "diagram case without thumb",
            "description": "test",
            "tags": "[]",
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "一年级",
            "diagram_type": "mind_map",
            "spec": '{"type":"mind_map","topic":"test"}',
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    post = body["post"]
    assert post["title"] == "diagram case without thumb"
    assert post["thumbnail_url"] is None


@requires_case_square_schema
def test_create_diagram_case_gallery_images_persist(client: TestClient) -> None:
    """Gallery images uploaded at create time persist on the post."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    spec = (
        '{"type":"diagram_case","source":"gallery","gallery":['
        '{"kind":"image","filename":"a.png","pending":true},'
        '{"kind":"image","filename":"b.png","pending":true}'
        "]}"
    )
    response = client.post(
        "/api/case-square/posts",
        data={
            "title": "gallery case",
            "description": "",
            "tags": "[]",
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "一年级",
            "diagram_type": "mind_map",
            "spec": spec,
        },
        files=[
            ("gallery_images", ("a.png", io.BytesIO(png), "image/png")),
            ("gallery_images", ("b.png", io.BytesIO(png), "image/png")),
        ],
    )

    assert response.status_code == 200, response.text
    post = response.json()["post"]
    assert len(post["gallery_items"]) == 2
    assert all(item["kind"] == "image" for item in post["gallery_items"])
    assert all(item["url"].endswith(".png") for item in post["gallery_items"])


@requires_case_square_schema
def test_upload_post_gallery_images_endpoint(client: TestClient) -> None:
    """Deferred gallery upload endpoint attaches images to pending slots."""
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_async_db] = _override_get_async_db

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    spec = (
        '{"type":"diagram_case","source":"gallery","gallery":['
        '{"kind":"image","filename":"a.png","pending":true},'
        '{"kind":"image","filename":"b.png","pending":true}'
        "]}"
    )
    create = client.post(
        "/api/case-square/posts",
        data={
            "title": "gallery deferred upload",
            "description": "",
            "tags": "[]",
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "一年级",
            "diagram_type": "mind_map",
            "spec": spec,
        },
    )
    assert create.status_code == 200, create.text
    post_id = create.json()["post"]["id"]

    upload = client.post(
        f"/api/case-square/posts/{post_id}/gallery-images",
        files=[
            ("gallery_images", ("a.png", io.BytesIO(png), "image/png")),
            ("gallery_images", ("b.png", io.BytesIO(png), "image/png")),
        ],
    )
    assert upload.status_code == 200, upload.text
    items = upload.json()["post"]["gallery_items"]
    assert len(items) == 2
    assert all(item.get("url") for item in items)


def test_format_gallery_items_preserves_slot_alignment() -> None:
    """Gallery formatter keeps slot order and marks missing image files."""
    post_id = "post-123"
    spec = {
        "gallery": [
            {"kind": "image", "filename": "missing.png", "pending": True},
            {
                "kind": "image",
                "filename": "ok.png",
                "path": f"case_square/{post_id}_gallery_1.png",
            },
            {"kind": "diagram", "diagram_id": "d1", "title": "Diagram"},
        ]
    }
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    target = Path("static/case_square") / f"{post_id}_gallery_1.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    try:
        items = _format_gallery_items(spec, post_id)
        assert len(items) == 3
        assert items[0]["kind"] == "image"
        assert items[0].get("missing") is True
        assert items[0].get("url") is None
        assert items[1]["kind"] == "image"
        assert items[1]["url"] == (f"/api/case-square/assets/case_square/{post_id}_gallery_1.png")
        assert items[2]["kind"] == "diagram"
    finally:
        if target.exists():
            target.unlink()
