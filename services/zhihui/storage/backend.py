"""ZhiHui media I/O: private COS (presigned) or local disk fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional
from urllib.parse import quote

from config.settings import config
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    delete_object,
    generate_presigned_get_url,
    get_object_bytes,
    open_object_stream,
    upload_bytes,
)
from services.zhihui.storage.keys import full_cos_key, resolve_local_safe

_STREAM_CHUNK_BYTES = 64 * 1024

logger = logging.getLogger(__name__)

STORAGE_COS = "cos"
STORAGE_LOCAL = "local"


def cos_zhihui_enabled() -> bool:
    """True when ZhiHui COS storage is enabled and credentials are configured."""
    if not config.COS_ZHIHUI_ENABLED:
        return False
    return cos_credentials_configured()


def storage_backend() -> str:
    """Active backend: cos | local."""
    return STORAGE_COS if cos_zhihui_enabled() else STORAGE_LOCAL


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
            log_prefix="[ZhiHui/COS]",
            content_type=content_type,
        ):
            raise RuntimeError("Failed to upload ZhiHui object to COS")
        logger.info("[ZhiHui] storage_put cos bytes=%s key=%s", len(data), logical_key)
        return logical_key
    path = resolve_local_safe(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.info("[ZhiHui] storage_put local bytes=%s key=%s", len(data), logical_key)
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


def get_bytes_sync(logical_key: str, *, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """Read object bytes from COS or local."""
    if cos_zhihui_enabled():
        return get_object_bytes(
            full_cos_key(logical_key),
            log_prefix="[ZhiHui/COS]",
            max_bytes=max_bytes,
        )
    path = resolve_local_safe(logical_key)
    if not path.is_file():
        return None
    if max_bytes is None:
        return path.read_bytes()
    with path.open("rb") as handle:
        return handle.read(max_bytes)


async def get_bytes(logical_key: str, *, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """Async get via to_thread."""
    return await asyncio.to_thread(get_bytes_sync, logical_key, max_bytes=max_bytes)


def open_bytes_stream_sync(logical_key: str) -> Optional[Any]:
    """Open a readable stream for a ZhiHui object (caller must close)."""
    if cos_zhihui_enabled():
        return open_object_stream(full_cos_key(logical_key), log_prefix="[ZhiHui/COS]")
    path = resolve_local_safe(logical_key)
    if not path.is_file():
        return None
    return path.open("rb")


async def aiter_bytes(
    logical_key: str,
    *,
    chunk_size: int = _STREAM_CHUNK_BYTES,
) -> AsyncGenerator[bytes, None]:
    """Yield object bytes in chunks without buffering the full body in RAM."""
    handle = await asyncio.to_thread(open_bytes_stream_sync, logical_key)
    if handle is None:
        return
    read_size = chunk_size if chunk_size > 0 else _STREAM_CHUNK_BYTES
    try:
        while True:
            chunk = await asyncio.to_thread(handle.read, read_size)
            if not chunk:
                break
            yield chunk
    finally:
        await asyncio.to_thread(handle.close)


def delete_key_sync(logical_key: str) -> bool:
    """Delete one object by logical key."""
    if not logical_key:
        return False
    ok = False
    if cos_zhihui_enabled():
        ok = delete_object(full_cos_key(logical_key))
    try:
        path = resolve_local_safe(logical_key)
        if path.is_file():
            path.unlink()
            ok = True
    except ValueError:
        pass
    if ok:
        logger.info("[ZhiHui] storage_delete key=%s", logical_key)
    return ok


async def delete_key(logical_key: str) -> bool:
    """Async delete one key."""
    return await asyncio.to_thread(delete_key_sync, logical_key)


def create_presigned_get(
    logical_key: str,
    *,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Short-lived GET URL for redirect Location only."""
    if not cos_zhihui_enabled():
        return None
    disposition = None
    if filename:
        safe = quote(filename)
        disposition = f'inline; filename="{safe}"'
    return generate_presigned_get_url(
        full_cos_key(logical_key),
        expired=config.COS_ZHIHUI_PRESIGN_GET_TTL,
        response_content_disposition=disposition,
    )
