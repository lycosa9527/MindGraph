"""Classroom slide I/O: shared COS bucket or local disk fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional
from urllib.parse import quote

from config.settings import config
from services.utils.tencent_cos_client import (
    delete_object,
    generate_presigned_get_url,
    get_object_bytes,
    open_object_stream,
    upload_bytes,
)
from services.mind_classroom.storage_keys import full_cos_key, resolve_local_safe
from services.zhihui.storage.backend import STORAGE_COS, STORAGE_LOCAL, cos_zhihui_enabled

logger = logging.getLogger(__name__)

_STREAM_CHUNK_BYTES = 64 * 1024


def storage_backend() -> str:
    """Active backend: cos | local."""
    return STORAGE_COS if cos_zhihui_enabled() else STORAGE_LOCAL


def write_local_bytes_sync(logical_key: str, data: bytes) -> str:
    """Always persist the working copy on this server."""
    path = resolve_local_safe(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return logical_key


def read_local_bytes_sync(logical_key: str) -> Optional[bytes]:
    """Read the server working copy, or None if missing."""
    try:
        path = resolve_local_safe(logical_key)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path.read_bytes()


def hydrate_local_from_cos_sync(logical_key: str) -> Optional[bytes]:
    """Prefer the server file; if absent, pull from COS and cache locally."""
    local = read_local_bytes_sync(logical_key)
    if local is not None:
        return local
    if not cos_zhihui_enabled():
        return None
    remote = get_object_bytes(
        full_cos_key(logical_key),
        log_prefix="[MindClassroom/COS]",
    )
    if not remote:
        return None
    write_local_bytes_sync(logical_key, remote)
    return remote


async def hydrate_local_from_cos(logical_key: str) -> Optional[bytes]:
    """Async hydrate via to_thread."""
    return await asyncio.to_thread(hydrate_local_from_cos_sync, logical_key)


def put_local_and_cos_sync(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Write the server working copy, then mirror to COS when enabled."""
    write_local_bytes_sync(logical_key, data)
    if cos_zhihui_enabled():
        key = full_cos_key(logical_key)
        if not upload_bytes(
            data,
            key,
            log_prefix="[MindClassroom/COS]",
            content_type=content_type,
        ):
            raise RuntimeError("Failed to upload classroom object to COS")
    return logical_key


async def put_local_and_cos(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Async local+COS put via to_thread."""
    return await asyncio.to_thread(
        put_local_and_cos_sync,
        logical_key,
        data,
        content_type=content_type,
    )


def put_bytes_sync(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Write bytes to COS or local; returns logical key."""
    if cos_zhihui_enabled():
        key = full_cos_key(logical_key)
        if not upload_bytes(
            data,
            key,
            log_prefix="[MindClassroom/COS]",
            content_type=content_type,
        ):
            raise RuntimeError("Failed to upload classroom object to COS")
        return logical_key
    path = resolve_local_safe(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return logical_key


async def put_bytes(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Async put via to_thread."""
    return await asyncio.to_thread(
        put_bytes_sync,
        logical_key,
        data,
        content_type=content_type,
    )


def delete_key_sync(logical_key: str) -> bool:
    """Delete COS or local object."""
    ok = False
    if cos_zhihui_enabled():
        ok = bool(delete_object(full_cos_key(logical_key)))
    try:
        path = resolve_local_safe(logical_key)
        if path.is_file():
            path.unlink()
            ok = True
    except ValueError:
        pass
    return ok


async def delete_key(logical_key: str) -> bool:
    """Async delete via to_thread."""
    return await asyncio.to_thread(delete_key_sync, logical_key)


def open_bytes_stream_sync(logical_key: str) -> Optional[Any]:
    """Open a readable stream (caller must close). Prefer the server working copy."""
    try:
        path = resolve_local_safe(logical_key)
        if path.is_file():
            return path.open("rb")
    except ValueError:
        pass
    if cos_zhihui_enabled():
        return open_object_stream(full_cos_key(logical_key), log_prefix="[MindClassroom/COS]")
    return None


async def aiter_bytes(logical_key: str) -> AsyncGenerator[bytes, None]:
    """Yield object bytes in chunks."""
    handle = await asyncio.to_thread(open_bytes_stream_sync, logical_key)
    if handle is None:
        return
    try:
        while True:
            chunk = await asyncio.to_thread(handle.read, _STREAM_CHUNK_BYTES)
            if not chunk:
                break
            yield chunk
    finally:
        await asyncio.to_thread(handle.close)


def create_presigned_get(logical_key: str, *, filename: Optional[str] = None) -> Optional[str]:
    """Short-TTL COS GET URL, or None when COS is off."""
    if not cos_zhihui_enabled():
        return None
    disposition = None
    if filename:
        disposition = f'inline; filename="{quote(filename)}"'
    return generate_presigned_get_url(
        full_cos_key(logical_key),
        expired=int(getattr(config, "COS_ZHIHUI_PRESIGN_GET_TTL", 300) or 300),
        response_content_disposition=disposition,
    )
