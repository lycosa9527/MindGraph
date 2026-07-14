"""Showcase media I/O: private COS (presigned) or local disk fallback."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

from config.settings import config
from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage.keys import (
    LEGACY_LOGICAL_PREFIX,
    LOGICAL_PREFIX,
    collect_keys_from_post,
    full_cos_key,
    resolve_local_safe,
    showcase_local_root,
)
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    delete_object,
    generate_presigned_get_url,
    generate_presigned_put_url,
    get_object_bytes,
    head_object,
    list_prefix,
    upload_bytes,
)

logger = logging.getLogger(__name__)

STORAGE_COS = "cos"
STORAGE_LOCAL = "local"


def cos_showcase_enabled() -> bool:
    """True when Showcase COS storage is enabled and credentials are configured."""
    if not config.COS_SHOWCASE_ENABLED:
        return False
    return cos_credentials_configured()


def storage_backend() -> str:
    """Active backend: cos | local."""
    return STORAGE_COS if cos_showcase_enabled() else STORAGE_LOCAL


def put_bytes_sync(logical_key: str, data: bytes) -> str:
    """Write bytes to COS or local; returns logical key."""
    backend = storage_backend()
    if cos_showcase_enabled():
        key = full_cos_key(logical_key)
        if not upload_bytes(data, key, log_prefix="[Showcase/COS]"):
            raise RuntimeError("Failed to upload Showcase object to COS")
        showcase_wf_log(
            "storage_put",
            f"bytes={len(data)}",
            key=logical_key,
            backend=backend,
        )
        return logical_key
    path = resolve_local_safe(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    showcase_wf_log(
        "storage_put",
        f"bytes={len(data)}",
        key=logical_key,
        backend=backend,
    )
    return logical_key


async def put_bytes(logical_key: str, data: bytes) -> str:
    """Async put via to_thread."""
    return await asyncio.to_thread(put_bytes_sync, logical_key, data)


def get_bytes_sync(logical_key: str, *, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """Read object bytes from COS or local (optionally capped for magic samples)."""
    if cos_showcase_enabled() and not logical_key.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        return get_object_bytes(
            full_cos_key(logical_key),
            log_prefix="[Showcase/COS]",
            max_bytes=max_bytes,
        )
    if logical_key.startswith(f"{LEGACY_LOGICAL_PREFIX}/") or not cos_showcase_enabled():
        path = resolve_local_safe(logical_key)
        if not path.is_file():
            return None
        if max_bytes is None:
            return path.read_bytes()
        with path.open("rb") as handle:
            return handle.read(max_bytes)
    return get_object_bytes(
        full_cos_key(logical_key),
        log_prefix="[Showcase/COS]",
        max_bytes=max_bytes,
    )


async def get_bytes(logical_key: str, *, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """Async get via to_thread."""
    return await asyncio.to_thread(get_bytes_sync, logical_key, max_bytes=max_bytes)


def head_object_sync(logical_key: str) -> Optional[dict[str, Any]]:
    """Head metadata for COS object, or local size for fallback."""
    if cos_showcase_enabled() and not logical_key.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        return head_object(full_cos_key(logical_key))
    path = resolve_local_safe(logical_key)
    if not path.is_file():
        return None
    return {"Content-Length": str(path.stat().st_size), "storage": STORAGE_LOCAL}


async def head_object_async(logical_key: str) -> Optional[dict[str, Any]]:
    """Async head."""
    return await asyncio.to_thread(head_object_sync, logical_key)


def delete_key_sync(logical_key: str) -> bool:
    """Delete one object by logical key."""
    if not logical_key:
        return False
    ok = False
    backend = storage_backend()
    if cos_showcase_enabled() and not logical_key.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        ok = delete_object(full_cos_key(logical_key))
    try:
        path = resolve_local_safe(logical_key)
        if path.is_file():
            path.unlink()
            ok = True
    except ValueError:
        pass
    if ok:
        showcase_wf_log("storage_delete", "ok", key=logical_key, backend=backend)
    return ok


async def delete_key(logical_key: str) -> bool:
    """Async delete one key."""
    return await asyncio.to_thread(delete_key_sync, logical_key)


def delete_keys_sync(logical_keys: Iterable[str]) -> int:
    """Delete many keys (best-effort); return count deleted."""
    deleted = 0
    for key in logical_keys:
        if key and delete_key_sync(key):
            deleted += 1
    return deleted


async def delete_keys(logical_keys: Iterable[str]) -> int:
    """Async delete many keys; return count deleted."""
    return await asyncio.to_thread(delete_keys_sync, list(logical_keys))


def delete_post_prefix_sync(post_id: str) -> int:
    """Delete all objects under showcase/posts/{post_id}/; return count deleted."""
    deleted = 0
    logical_prefix = f"{LOGICAL_PREFIX}/{post_id}/"
    if cos_showcase_enabled():
        cos_prefix = full_cos_key(logical_prefix)
        for entry in list_prefix(cos_prefix):
            key = entry.get("key")
            if key and delete_object(key):
                deleted += 1
    local_dir = showcase_local_root() / post_id
    if local_dir.is_dir():
        for path in local_dir.rglob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)
                deleted += 1
        try:
            local_dir.rmdir()
        except OSError:
            logger.debug("[Showcase] local dir not empty post_id=%s", post_id)
    legacy_dir = Path("static") / LEGACY_LOGICAL_PREFIX
    if legacy_dir.is_dir():
        for path in legacy_dir.glob(f"{post_id}*"):
            if path.is_file():
                path.unlink(missing_ok=True)
                deleted += 1
    return deleted


async def delete_post_prefix(post_id: str) -> int:
    """Async delete post prefix; return count deleted."""
    return await asyncio.to_thread(delete_post_prefix_sync, post_id)


def create_presigned_put(
    logical_key: str,
    *,
    content_type: str,
) -> Optional[dict[str, Any]]:
    """
    Mint short-lived PUT for browser upload when COS is on.

    Local fallback returns None put_url — client should POST bytes to complete.
    """
    if not cos_showcase_enabled():
        return {
            "key": logical_key,
            "put_url": None,
            "storage": STORAGE_LOCAL,
            "headers": {"Content-Type": content_type},
            "expires_in": config.COS_SHOWCASE_PRESIGN_PUT_TTL,
        }
    url = generate_presigned_put_url(
        full_cos_key(logical_key),
        expired=config.COS_SHOWCASE_PRESIGN_PUT_TTL,
        content_type=content_type,
    )
    if not url:
        return None
    return {
        "key": logical_key,
        "put_url": url,
        "storage": STORAGE_COS,
        "headers": {"Content-Type": content_type},
        "expires_in": config.COS_SHOWCASE_PRESIGN_PUT_TTL,
    }


def create_presigned_get(
    logical_key: str,
    *,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Short-lived GET URL for redirect Location only."""
    if not cos_showcase_enabled() or logical_key.startswith(f"{LEGACY_LOGICAL_PREFIX}/"):
        return None
    disposition = None
    if filename:
        safe = quote(filename)
        disposition = f'inline; filename="{safe}"'
    return generate_presigned_get_url(
        full_cos_key(logical_key),
        expired=config.COS_SHOWCASE_PRESIGN_GET_TTL,
        response_content_disposition=disposition,
    )


async def delete_post_assets(
    *,
    post_id: str,
    thumbnail_path: Optional[str] = None,
    spec: Optional[dict[str, Any]] = None,
) -> int:
    """Delete referenced keys plus leftovers under the post prefix; return total deleted."""
    keys = collect_keys_from_post(thumbnail_path=thumbnail_path, spec=spec)
    deleted = await delete_keys(keys)
    deleted += await delete_post_prefix(post_id)
    showcase_wf_log(
        "assets_deleted",
        f"keys={len(keys)} deleted={deleted}",
        post_id=post_id,
        backend=storage_backend(),
    )
    return deleted
