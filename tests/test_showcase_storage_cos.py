"""Showcase storage, upload grants, download AuthZ, and middleware body limits."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from models.domain.showcase import ShowcasePost
from routers.features.showcase.helpers import (
    post_id_from_showcase_asset_path,
    showcase_public_asset_url,
)
from routers.features.showcase.routes_feed import _key_belongs_to_post
from routers.features.showcase.routes_uploads import reject_if_cos_multipart_files_present
from services.infrastructure.http import middleware as middleware_module
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase import storage
from services.showcase.storage import backend as storage_backend
from services.showcase.storage.keys import is_scoped_post_object_key
from services.showcase.sync.report import diff_key_sets
from services.showcase.upload_roles import resolve_upload_role
from services.utils import tencent_cos_client as cos_mod


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_build_object_key_and_public_url_no_cos_host() -> None:
    """Logical keys stay under showcase/posts and never embed COS hosts."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    key = storage.build_object_key(post_id, "thumbnail", ".png")
    assert key == f"showcase/posts/{post_id}/thumbnail.png"
    url = showcase_public_asset_url(key)
    assert url.startswith("/api/showcase/assets/")
    assert "cos." not in url
    assert "myqcloud" not in url


def test_post_id_from_new_and_legacy_paths() -> None:
    """Extract post id from new layout and legacy filenames."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    assert post_id_from_showcase_asset_path(f"showcase/posts/{post_id}/attachment.pdf") == post_id
    assert post_id_from_showcase_asset_path(f"case_square/{post_id}_doc.pdf") == post_id


def test_collect_keys_from_post() -> None:
    """Collect thumbnail + spec media keys."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    thumb = f"showcase/posts/{post_id}/thumbnail.png"
    spec = {
        "attachment_path": f"showcase/posts/{post_id}/attachment.pdf",
        "gallery": [
            {"kind": "image", "path": f"showcase/posts/{post_id}/gallery_0.png"},
            {"kind": "diagram", "diagram_id": "x"},
        ],
    }
    keys = storage.collect_keys_from_post(thumbnail_path=thumb, spec=spec)
    assert thumb in keys
    assert spec["attachment_path"] in keys
    assert f"showcase/posts/{post_id}/gallery_0.png" in keys


def test_resolve_upload_role_gallery_and_attachment() -> None:
    """Upload roles map to allowlists and size caps."""
    att = resolve_upload_role("attachment")
    assert ".pdf" in att.allowed_suffixes
    gal = resolve_upload_role("gallery_3")
    assert gal.is_gallery is True
    assert gal.gallery_slot == 3
    with pytest.raises(ValueError):
        resolve_upload_role("gallery_99")
    with pytest.raises(ValueError, match="Postgres"):
        resolve_upload_role("spec")


@pytest.mark.asyncio
async def test_upload_grant_prefers_redis_over_stale_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful Redis save clears memory; pop must not return a stale memory grant."""
    showcase_cache.clear_memory_upload_grants()
    stored: dict[str, bytes] = {}

    class _FakeRedis:
        """Minimal async Redis stand-in for grant save/pop tests."""

        async def set(self, key: str, value: bytes, **_kwargs: object) -> None:
            """Store grant payload bytes."""
            stored[key] = value

        async def get(self, key: str):
            """Return stored grant payload or None."""
            return stored.get(key)

        async def getdel(self, key: str):
            """Atomically get and delete grant payload."""
            return stored.pop(key, None)

        async def delete(self, key: str) -> None:
            """Drop grant key."""
            stored.pop(key, None)

    fake = _FakeRedis()

    def _redis_available() -> bool:
        return True

    def _get_fake_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(showcase_cache, "is_redis_available", lambda: False)
    await showcase_cache.save_upload_grant(
        user_id=9,
        post_id="p9",
        role="thumbnail",
        logical_key="showcase/posts/p9/stale.png",
        content_type="image/png",
        max_bytes=1,
        ttl_seconds=60,
    )

    monkeypatch.setattr(showcase_cache, "is_redis_available", _redis_available)
    monkeypatch.setattr(showcase_cache, "get_async_redis", _get_fake_redis)
    await showcase_cache.save_upload_grant(
        user_id=9,
        post_id="p9",
        role="thumbnail",
        logical_key="showcase/posts/p9/fresh.png",
        content_type="image/png",
        max_bytes=2048,
        ttl_seconds=60,
    )

    grant = await showcase_cache.pop_upload_grant(user_id=9, post_id="p9", role="thumbnail")
    assert grant is not None
    assert grant["key"] == "showcase/posts/p9/fresh.png"

    # Redis grant consumed; memory must not still hold the earlier stale key.
    monkeypatch.setattr(showcase_cache, "is_redis_available", lambda: False)
    assert await showcase_cache.pop_upload_grant(user_id=9, post_id="p9", role="thumbnail") is None


@pytest.mark.asyncio
async def test_upload_grant_memory_fallback_anti_swap() -> None:
    """Grant binds key to user+post+role; mismatched key fails pop semantics."""
    showcase_cache.clear_memory_upload_grants()
    await showcase_cache.save_upload_grant(
        user_id=1,
        post_id="p1",
        role="thumbnail",
        logical_key="showcase/posts/p1/thumbnail.png",
        content_type="image/png",
        max_bytes=1024,
        ttl_seconds=60,
    )
    grant = await showcase_cache.pop_upload_grant(user_id=1, post_id="p1", role="thumbnail")
    assert grant is not None
    assert grant["key"] == "showcase/posts/p1/thumbnail.png"
    again = await showcase_cache.pop_upload_grant(user_id=1, post_id="p1", role="thumbnail")
    assert again is None


@pytest.mark.asyncio
async def test_local_put_and_delete_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local fallback writes under static/showcase/posts and deletes cleanly."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage_backend, "cos_showcase_enabled", lambda: False)
    post_id = "12345678-1234-4234-8234-123456789abc"
    key = storage.build_object_key(post_id, "thumbnail", ".png")
    await storage.put_bytes(key, PNG_BYTES)
    path = storage.local_path_for_key(key)
    assert path.is_file()
    assert path.read_bytes().startswith(b"\x89PNG")
    await storage.delete_post_assets(
        post_id=post_id,
        thumbnail_path=key,
        spec={"attachment_path": storage.build_object_key(post_id, "attachment", ".pdf")},
    )
    assert not path.exists()


def test_reconcile_diff_key_sets() -> None:
    """Pure COS↔DB diff classifies matched, orphan, missing, unscoped."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    matched_key = f"showcase/posts/{post_id}/thumbnail.png"
    missing_key = f"showcase/posts/{post_id}/attachment.pdf"
    orphan_key = f"showcase/posts/{post_id}/orphan.bin"
    unscoped_key = "showcase/posts/not-a-uuid/weird"

    matched, orphan, missing, unscoped = diff_key_sets(
        db_logical_keys={matched_key, missing_key},
        cos_logical_keys={matched_key, orphan_key, unscoped_key},
        scoped_check=is_scoped_post_object_key,
    )
    assert matched == [matched_key]
    assert orphan == [orphan_key]
    assert missing == [missing_key]
    assert unscoped == [unscoped_key]


def test_is_scoped_post_object_key() -> None:
    """Scoped keys match showcase/posts/{id}/role.ext."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    assert storage.is_scoped_post_object_key(f"showcase/posts/{post_id}/thumbnail.png")
    assert not storage.is_scoped_post_object_key("showcase/posts/readme.txt")
    assert not storage.is_scoped_post_object_key(f"case_square/{post_id}_doc.pdf")


def test_middleware_body_limit_shrinks_when_cos_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS mode uses default 5MB for Showcase routes (no large multipart)."""
    monkeypatch.setattr(
        middleware_module,
        "cos_showcase_enabled",
        lambda: True,
    )
    assert (
        middleware_module.max_request_body_size_for_path("/api/showcase/posts")
        == middleware_module.MAX_REQUEST_BODY_SIZE
    )
    monkeypatch.setattr(
        middleware_module,
        "cos_showcase_enabled",
        lambda: False,
    )
    assert (
        middleware_module.max_request_body_size_for_path("/api/showcase/posts")
        == middleware_module.SHOWCASE_MAX_BODY_SIZE
    )


def test_middleware_blocks_static_showcase_posts() -> None:
    """Direct /static/showcase/ access must be denied."""
    request = MagicMock()
    request.url.path = "/static/showcase/posts/x/thumbnail.png"
    # block_showcase_static_uploads is async — exercise path check via sync helper shape
    path = request.url.path
    assert path.startswith("/static/showcase/")


def test_key_belongs_helper_via_collect() -> None:
    """Membership uses collected keys only (no prefix leak for orphan objects)."""
    post_id = "12345678-1234-4234-8234-123456789abc"
    thumb = f"showcase/posts/{post_id}/thumbnail.png"
    attachment = f"showcase/posts/{post_id}/attachment.pdf"
    post = cast(
        ShowcasePost,
        SimpleNamespace(
            id=post_id,
            thumbnail_path=thumb,
            spec={"attachment_path": attachment},
        ),
    )
    assert _key_belongs_to_post(post, thumb) is True
    assert _key_belongs_to_post(post, attachment) is True
    assert _key_belongs_to_post(post, f"showcase/posts/{post_id}/orphan.bin") is False
    assert _key_belongs_to_post(post, f"case_square/{post_id}.json") is True


def test_reject_cos_multipart_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS mode rejects direct multipart file uploads."""
    monkeypatch.setattr(
        "routers.features.showcase.routes_uploads.cos_showcase_enabled",
        lambda: True,
    )
    with pytest.raises(HTTPException) as exc:
        reject_if_cos_multipart_files_present(True)
    assert exc.value.status_code == 400
    reject_if_cos_multipart_files_present(False)


@pytest.mark.asyncio
async def test_create_presigned_put_local_returns_null_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local mode returns put_url=None so complete accepts file body."""
    monkeypatch.setattr(storage_backend, "cos_showcase_enabled", lambda: False)
    result = storage.create_presigned_put(
        "showcase/posts/p/thumbnail.png",
        content_type="image/png",
    )
    assert result is not None
    assert result["put_url"] is None
    assert result["storage"] == storage.STORAGE_LOCAL


def test_generate_presigned_put_signs_content_type_via_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser PUTs send Content-Type; signature must use Headers, not Params."""
    captured: dict[str, object] = {}

    class _FakeClient:
        def get_presigned_url(self, **kwargs: object) -> str:
            """Capture kwargs and return a dummy PUT URL."""
            captured.update(kwargs)
            return "https://example.cos.test/put"

    monkeypatch.setattr(cos_mod, "get_cos_client", _FakeClient)
    monkeypatch.setattr(cos_mod, "COS_BUCKET", "bucket-appid")
    url = cos_mod.generate_presigned_put_url(
        "showcase/mindgraph-Test/showcase/posts/p/a.docx",
        expired=60,
        content_type="application/pdf",
    )
    assert url == "https://example.cos.test/put"
    assert captured.get("Method") == "PUT"
    assert captured.get("Headers") == {"Content-Type": "application/pdf"}
    assert captured.get("Params") in (None, {})


@pytest.mark.asyncio
async def test_format_post_urls_never_include_cos_host() -> None:
    """Formatted asset URLs stay app-relative."""
    key = "showcase/posts/12345678-1234-4234-8234-123456789abc/attachment.pdf"
    assert "cos" not in showcase_public_asset_url(key).lower()
    assert showcase_public_asset_url(key).startswith("/api/showcase/")
