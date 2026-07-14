"""Live Showcase COS matrix — all storage/sync paths against real Tencent auth.

Requires COS_SHOWCASE_SMOKE=1 and credentials from .env (TENCENT_SMS_SECRET_*,
COS_BUCKET, COS_SHOWCASE_ENABLED). Uses an isolated prefix so prod/test objects
are not touched.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import text

from config.database import engine
from config.settings import config
from services.showcase import storage
from services.showcase.storage import backend as storage_backend
from services.showcase.sync.inventory import list_cos_logical_keys
from services.showcase.sync.reconcile import (
    build_storage_status,
    purge_orphan_cos_objects,
    reconcile_showcase_storage,
)
from services.showcase.sync.report import diff_key_sets
from services.showcase.storage.keys import is_scoped_post_object_key
from services.utils.error_types import DATABASE_ERRORS
from services.utils.tencent_cos_client import (
    delete_object,
    generate_presigned_get_url,
    generate_presigned_put_url,
    get_object_bytes,
    head_object,
    list_prefix,
    object_exists,
    upload_bytes,
)
from utils.db.session_open import system_rls_session
from tests.test_showcase_e2e_smoke import _ensure_smoke_identity

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MATRIX_PREFIX = "showcase/mindgraph-e2e-matrix"


def _showcase_schema_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM case_square_posts LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


requires_schema = pytest.mark.skipif(
    not _showcase_schema_ready(),
    reason="showcase schema not migrated",
)

requires_live_cos = pytest.mark.skipif(
    os.environ.get("COS_SHOWCASE_SMOKE", "").strip() not in ("1", "true", "yes"),
    reason="Set COS_SHOWCASE_SMOKE=1 with live COS credentials",
)


@pytest.fixture(autouse=True)
def isolate_matrix_prefix(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Keep matrix objects under a dedicated COS prefix."""
    monkeypatch.setenv("FEATURE_SHOWCASE", "true")
    monkeypatch.setenv("COS_SHOWCASE_PREFIX", MATRIX_PREFIX)
    monkeypatch.setenv("COS_SHOWCASE_ENABLED", "true")
    config.refresh_env_cache()
    yield
    config.refresh_env_cache()


@requires_live_cos
def test_live_storage_status_probe() -> None:
    """Admin status path: credentials + bucket reachability."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")
    status = build_storage_status()
    assert status.cos_enabled is True
    assert status.credentials_configured is True
    assert status.connection_ok is True
    assert status.backend == "cos"
    assert status.prefix == MATRIX_PREFIX
    assert status.bucket


@requires_live_cos
@pytest.mark.asyncio
async def test_live_put_head_get_presign_delete_matrix() -> None:
    """Exercise put/head/get/presign/delete for thumbnail + attachment roles."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")

    post_id = str(uuid.uuid4())
    thumb_key = storage.build_object_key(post_id, "thumbnail", ".png")
    pdf_key = storage.build_object_key(post_id, "attachment", ".pdf")
    gallery_key = storage.build_object_key(post_id, "gallery_0", ".png")

    await storage.put_bytes(thumb_key, PNG_BYTES)
    await storage.put_bytes(pdf_key, PDF_BYTES)
    await storage.put_bytes(gallery_key, PNG_BYTES)

    thumb_meta = await storage.head_object_async(thumb_key)
    assert thumb_meta is not None
    assert int(thumb_meta.get("Content-Length") or thumb_meta.get("content-length") or 0) == len(PNG_BYTES)

    sample = await storage.get_bytes(thumb_key, max_bytes=16)
    assert sample is not None
    assert sample.startswith(b"\x89PNG")

    get_url = storage.create_presigned_get(thumb_key, filename="thumb.png")
    assert get_url
    assert "http" in get_url

    put_info = storage.create_presigned_put(thumb_key, content_type="image/png")
    assert put_info is not None
    assert put_info["put_url"]
    assert put_info["storage"] == "cos"

    # Direct client helpers still work through the same prefix.
    full_thumb = storage.full_cos_key(thumb_key)
    assert object_exists(full_thumb)
    assert head_object(full_thumb) is not None
    assert get_object_bytes(full_thumb, max_bytes=8) is not None
    assert generate_presigned_get_url(full_thumb, expired=60)
    assert generate_presigned_put_url(full_thumb, expired=60, content_type="image/png")

    deleted = await storage.delete_post_assets(
        post_id=post_id,
        thumbnail_path=thumb_key,
        spec={
            "attachment_path": pdf_key,
            "gallery": [{"kind": "image", "path": gallery_key}],
        },
    )
    assert deleted >= 3
    leftovers = list_prefix(storage.full_cos_key(f"showcase/posts/{post_id}/"))
    assert not leftovers


@requires_live_cos
@pytest.mark.asyncio
async def test_live_orphan_reconcile_and_purge() -> None:
    """Orphan object is classified then removed by dry_run + real purge."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")

    post_id = str(uuid.uuid4())
    orphan_key = storage.build_object_key(post_id, "thumbnail", ".png")
    await storage.put_bytes(orphan_key, PNG_BYTES)
    assert orphan_key in list_cos_logical_keys()

    # No DB row references this key → orphan_cos.
    async with system_rls_session() as db:
        report = await reconcile_showcase_storage(db)
    assert orphan_key in report.orphan_cos

    dry = purge_orphan_cos_objects([orphan_key], dry_run=True)
    assert dry["dry_run"] is True
    assert orphan_key in dry["planned"]
    assert dry["deleted_count"] == 0
    assert object_exists(storage.full_cos_key(orphan_key))

    applied = purge_orphan_cos_objects([orphan_key], dry_run=False)
    assert applied["deleted_count"] == 1
    assert orphan_key in applied["deleted"]
    assert not object_exists(storage.full_cos_key(orphan_key))


@requires_live_cos
def test_live_unscoped_vs_orphan_classification() -> None:
    """Unscoped junk under posts/ is reported separately from scoped orphans."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")

    junk_full = storage.full_cos_key("showcase/posts/readme.txt")
    assert upload_bytes(b"not-a-scoped-object", junk_full, log_prefix="[Showcase/COS-matrix]")

    cos_keys = list_cos_logical_keys()
    matched, orphan, missing, unscoped = diff_key_sets(
        db_logical_keys=set(),
        cos_logical_keys=cos_keys,
        scoped_check=is_scoped_post_object_key,
    )
    assert not matched
    assert not missing
    assert "showcase/posts/readme.txt" in unscoped
    assert "showcase/posts/readme.txt" not in orphan

    assert delete_object(junk_full)


@requires_schema
@requires_live_cos
@pytest.mark.asyncio
async def test_live_missing_in_cos_when_db_key_absent_from_bucket() -> None:
    """DB-referenced keys that are not on COS show up as missing_in_cos."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")

    await _ensure_smoke_identity()

    post_id = str(uuid.uuid4())
    missing_key = storage.build_object_key(post_id, "thumbnail", ".png")

    async with system_rls_session() as db:
        inserted = await db.execute(
            text(
                """
                INSERT INTO case_square_posts (
                    id, title, tags, case_type, status, publish_source,
                    author_id, submitted_by_id, thumbnail_path, likes_count, views_count,
                    created_at, updated_at, is_expert_recommended
                )
                SELECT
                    :id, 'matrix missing', '[]'::jsonb, 'diagram_case', 'pending', 'self',
                    u.id, u.id, :thumb, 0, 0,
                    now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc', false
                FROM users u
                WHERE u.phone = '19900000661'
                LIMIT 1
                RETURNING id
                """
            ),
            {"id": post_id, "thumb": missing_key},
        )
        if inserted.first() is None:
            pytest.skip("smoke user phone 19900000661 not available")
        await db.commit()

        try:
            report = await reconcile_showcase_storage(db)
            assert missing_key in report.missing_in_cos
            assert missing_key not in report.matched
        finally:
            await db.execute(
                text("DELETE FROM case_square_posts WHERE id = :id"),
                {"id": post_id},
            )
            await db.commit()


@requires_live_cos
@pytest.mark.asyncio
async def test_live_delete_post_prefix_clears_abandoned_puts() -> None:
    """Abandoned browser PUT leftovers under a post prefix are wiped."""
    if not storage.cos_showcase_enabled():
        pytest.skip("COS showcase not enabled")

    post_id = str(uuid.uuid4())
    abandoned = storage.build_object_key(post_id, "thumbnail", ".png")
    await storage.put_bytes(abandoned, PNG_BYTES)
    assert list_prefix(storage.full_cos_key(f"showcase/posts/{post_id}/"))

    deleted = await storage_backend.delete_post_prefix(post_id)
    assert deleted >= 1
    assert not list_prefix(storage.full_cos_key(f"showcase/posts/{post_id}/"))
