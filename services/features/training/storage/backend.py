"""Training media I/O: private COS (presigned) or local disk fallback."""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Optional

from config.settings import config
from services.features.training.storage.keys import (
    course_folder,
    full_cos_key,
    resolve_local_safe,
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


def cos_training_enabled() -> bool:
    """True when training COS storage is enabled and credentials are configured."""
    if not config.COS_TRAINING_ENABLED:
        return False
    return cos_credentials_configured()


def storage_backend() -> str:
    """Active backend: cos | local."""
    return STORAGE_COS if cos_training_enabled() else STORAGE_LOCAL


def put_bytes_sync(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Write bytes to COS or local; returns logical key."""
    path = resolve_local_safe(logical_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if cos_training_enabled():
        upload_bytes(
            data,
            full_cos_key(logical_key),
            content_type=content_type,
            log_prefix="[Training/COS]",
        )
    return logical_key


def get_bytes_sync(logical_key: str) -> Optional[bytes]:
    """Read local first, then COS."""
    try:
        path = resolve_local_safe(logical_key)
    except ValueError:
        return None
    if path.is_file():
        return path.read_bytes()
    if not cos_training_enabled():
        return None
    return get_object_bytes(full_cos_key(logical_key), log_prefix="[Training/COS]")


def head_object_sync(logical_key: str) -> Optional[dict]:
    """COS head or local file size."""
    if cos_training_enabled():
        return head_object(full_cos_key(logical_key))
    try:
        path = resolve_local_safe(logical_key)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return {"ContentLength": path.stat().st_size}


def create_presigned_put(logical_key: str, content_type: str) -> Optional[str]:
    """Short-TTL PUT URL, or None when COS is off."""
    if not cos_training_enabled():
        return None
    return generate_presigned_put_url(
        full_cos_key(logical_key),
        expired=config.COS_TRAINING_PRESIGN_PUT_TTL,
        content_type=content_type,
    )


def create_presigned_get(logical_key: str) -> Optional[str]:
    """Short-TTL GET URL, or None when COS is off."""
    if not cos_training_enabled():
        return None
    return generate_presigned_get_url(
        full_cos_key(logical_key),
        expired=config.COS_TRAINING_PRESIGN_GET_TTL,
    )


async def put_bytes(
    logical_key: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
) -> str:
    """Async write that offloads disk/COS I/O off the event loop."""
    return await asyncio.to_thread(put_bytes_sync, logical_key, data, content_type=content_type)


async def get_bytes(logical_key: str) -> Optional[bytes]:
    """Async read that offloads disk/COS I/O off the event loop."""
    return await asyncio.to_thread(get_bytes_sync, logical_key)


async def head_object_async(logical_key: str) -> Optional[dict]:
    """Async head that offloads disk/COS I/O off the event loop."""
    return await asyncio.to_thread(head_object_sync, logical_key)


async def delete_course_folder(course_id: str) -> None:
    """Async delete of the course COS/local folder."""
    await asyncio.to_thread(delete_course_prefix, course_id)


def delete_course_prefix(course_id: str) -> None:
    """Delete every object under the course folder (COS + local)."""
    folder = course_folder(course_id)
    if cos_training_enabled():
        prefix = full_cos_key(folder)
        for obj in list_prefix(prefix):
            key = str(obj.get("key") or "")
            if key:
                delete_object(key)
    try:
        local_root = resolve_local_safe(f"{folder}/.keep").parent
    except ValueError:
        return
    if local_root.is_dir():
        shutil.rmtree(local_root, ignore_errors=True)
