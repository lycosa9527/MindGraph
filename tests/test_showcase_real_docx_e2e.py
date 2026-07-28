"""Real teaching-design DOCX e2e: create → attach → thumb gates → withdraw.

Uses a local DOCX path (default: Desktop 阿Q正传 teaching design) when present.
Always withdraws so COS/local showcase objects are deleted after the run.
"""

from __future__ import annotations

import asyncio
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
from services.utils.error_types import DATABASE_ERRORS
from services.utils.tencent_cos_client import list_prefix
from utils.auth import get_current_user
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.db.rls_context import RlsContext, reset_rls_context, set_rls_context
from utils.db.session_open import system_rls_session

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

SMOKE_PHONE = "19900000661"
SMOKE_ORG_CODE = "showcase-cos-smoke"
SMOKE_COS_PREFIX = "showcase/mindgraph-e2e-smoke"

# Same file that failed in production logs (attachment ~1.14MB, then thumb 413).
_DEFAULT_REAL_DOCX = Path("/mnt/c/Users/roywa/Desktop/【3.0版本】2402-《阿Q正传》教学设计-陈玉华.docx")
_WIN_DEFAULT_REAL_DOCX = Path(r"C:\Users\roywa\Desktop\【3.0版本】2402-《阿Q正传》教学设计-陈玉华.docx")

THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024


def _resolve_real_docx() -> Path | None:
    override = os.environ.get("SHOWCASE_REAL_DOCX", "").strip()
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.extend((_DEFAULT_REAL_DOCX, _WIN_DEFAULT_REAL_DOCX))
    for path in candidates:
        if path.is_file():
            return path
    return None


def _showcase_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM case_square_posts LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_showcase_schema = pytest.mark.skipif(
    not _showcase_schema_ready(),
    reason="showcase schema not migrated",
)

requires_real_docx = pytest.mark.skipif(
    _resolve_real_docx() is None,
    reason="Set SHOWCASE_REAL_DOCX or place the Desktop 阿Q正传 DOCX",
)


def _make_user(user_id: int, organization_id: int) -> SimpleNamespace:
    org = SimpleNamespace(name="Smoke School")
    user = SimpleNamespace()
    user.id = user_id
    user.name = "Showcase Smoke"
    user.phone = SMOKE_PHONE
    user.avatar = None
    user.role = "teacher"
    user.organization_id = organization_id
    user.organization = org
    return user


async def _ensure_smoke_identity() -> tuple[int, int]:
    async with system_rls_session() as session:
        org = (
            await session.execute(
                text("SELECT id FROM organizations WHERE code = :code"),
                {"code": SMOKE_ORG_CODE},
            )
        ).fetchone()
        if org is None:
            org_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO organizations (code, name, school_tier, is_active, created_at)
                        VALUES (
                            :code, 'Showcase COS Smoke', 'trial', true,
                            now() AT TIME ZONE 'utc'
                        )
                        RETURNING id
                        """
                    ),
                    {"code": SMOKE_ORG_CODE},
                )
            ).scalar_one()
        else:
            org_id = int(org[0])

        user = (
            await session.execute(
                text("SELECT id FROM users WHERE phone = :phone"),
                {"phone": SMOKE_PHONE},
            )
        ).fetchone()
        if user is None:
            user_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO users (
                            phone, password_hash, name, organization_id, role,
                            created_at, login_password_set,
                            allows_simplified_chinese, email_login_whitelisted_from_cn,
                            match_prompt_to_ui
                        )
                        VALUES (
                            :phone, 'smoke-hash', 'Showcase COS Smoke', :org_id, 'teacher',
                            now() AT TIME ZONE 'utc', false,
                            true, false, true
                        )
                        RETURNING id
                        """
                    ),
                    {"phone": SMOKE_PHONE, "org_id": org_id},
                )
            ).scalar_one()
        else:
            user_id = int(user[0])
        await session.commit()
        return int(user_id), int(org_id)


@pytest.fixture(name="smoke_identity")
def fixture_smoke_identity() -> tuple[int, int]:
    """Ensure a real DB user exists for Showcase FK + RLS."""
    return asyncio.run(_ensure_smoke_identity())


def _override_get_async_db_factory(user: SimpleNamespace):
    """Bind TestClient DB sessions to the smoke user RLS context."""

    async def _override_get_async_db(request: Request):
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

    return _override_get_async_db


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """HTTP client for Showcase upload routes."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def enable_showcase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable FEATURE_SHOWCASE for this module."""
    monkeypatch.setenv("FEATURE_SHOWCASE", "true")
    config.refresh_env_cache()


def _put_presigned(put_url: str, data: bytes, headers: dict[str, str]) -> None:
    """PUT bytes to a COS presigned URL."""
    req = urllib.request.Request(put_url, data=data, method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        assert 200 <= resp.status < 300


@requires_showcase_schema
@requires_real_docx
def test_real_teaching_docx_upload_then_withdraw(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    smoke_identity: tuple[int, int],
) -> None:
    """Reproduce teaching_design attach flow with the real DOCX, then delete assets."""
    docx_path = _resolve_real_docx()
    assert docx_path is not None
    docx_bytes = docx_path.read_bytes()
    # Production failure: ~1.14MB attachment OK, then cover PNG >2MB → 413/rollback.
    assert 100_000 < len(docx_bytes) <= ATTACHMENT_MAX_BYTES

    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled / credentials missing")

    user_id, org_id = smoke_identity
    user = _make_user(user_id, org_id)

    monkeypatch.setenv("COS_SHOWCASE_PREFIX", SMOKE_COS_PREFIX)
    config.refresh_env_cache()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_async_db] = _override_get_async_db_factory(user)

    post_id: str | None = None
    try:
        create = client.post(
            "/api/showcase/posts",
            data={
                "title": "阿Q正传教学设计（e2e）",
                "description": "real docx smoke",
                "tags": '["语文教学"]',
                "case_type": "teaching_design",
                "subject": "语文",
                "grade": "九年级",
            },
        )
        assert create.status_code == 200, create.text
        post_id = create.json()["post"]["id"]

        # 1) Attachment (20MB cap) — this succeeded in production logs.
        init_att = client.post(
            f"/api/showcase/posts/{post_id}/uploads/init",
            json={
                "role": "attachment",
                "filename": docx_path.name,
                "content_type": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "size_bytes": len(docx_bytes),
            },
        )
        assert init_att.status_code == 200, init_att.text
        att_body = init_att.json()
        assert att_body.get("put_url")
        _put_presigned(
            att_body["put_url"],
            docx_bytes,
            att_body.get("headers")
            or {"Content-Type": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        complete_att = client.post(
            f"/api/showcase/posts/{post_id}/uploads/complete",
            json={
                "role": "attachment",
                "key": att_body["key"],
                "filename": docx_path.name,
            },
        )
        assert complete_att.status_code == 200, complete_att.text

        # 2) Oversized cover (pre-fix production failure mode).
        huge_thumb = client.post(
            f"/api/showcase/posts/{post_id}/uploads/init",
            json={
                "role": "thumbnail",
                "filename": "thumbnail.png",
                "content_type": "image/png",
                "size_bytes": THUMBNAIL_MAX_BYTES + 1,
            },
        )
        assert huge_thumb.status_code == 413, huge_thumb.text
        assert "2MB" in huge_thumb.text

        # 3) Valid cover under 2MB — publish path after client-side compress.
        init_thumb = client.post(
            f"/api/showcase/posts/{post_id}/uploads/init",
            json={
                "role": "thumbnail",
                "filename": "thumbnail.png",
                "content_type": "image/png",
                "size_bytes": len(PNG_BYTES),
            },
        )
        assert init_thumb.status_code == 200, init_thumb.text
        thumb_body = init_thumb.json()
        assert thumb_body.get("put_url")
        _put_presigned(
            thumb_body["put_url"],
            PNG_BYTES,
            thumb_body.get("headers") or {"Content-Type": "image/png"},
        )
        complete_thumb = client.post(
            f"/api/showcase/posts/{post_id}/uploads/complete",
            json={
                "role": "thumbnail",
                "key": thumb_body["key"],
                "filename": "thumbnail.png",
            },
        )
        assert complete_thumb.status_code == 200, complete_thumb.text
    finally:
        if post_id:
            withdraw = client.post(f"/api/showcase/posts/{post_id}/withdraw")
            assert withdraw.status_code == 200, withdraw.text
            leftovers = list_prefix(storage.full_cos_key(f"showcase/posts/{post_id}/"))
            assert not leftovers, leftovers
