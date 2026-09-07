"""研习社 attachment bytes: private COS, local disk only when COS is off.

Message text stays in Postgres. ``file_attachments`` keeps metadata and a
logical key. Clients always fetch via ``/api/chat/attachments/{id}/download``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from config.settings import config
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    generate_presigned_get_url,
    upload_bytes,
)

logger = logging.getLogger(__name__)

STORAGE_COS = "cos"
STORAGE_LOCAL = "local"
LEGACY_DISK_PREFIX = "/static/chat/"
INLINE_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)


@dataclass(frozen=True)
class AttachmentDownload:
    """Resolved download after ACL: disk file or short-lived COS redirect."""

    content_type: str
    filename: str
    disk_path: Optional[Path] = None
    redirect_url: Optional[str] = None


def cos_workshop_enabled() -> bool:
    """True when workshop COS storage is on and credentials exist."""
    if not config.COS_WORKSHOP_ENABLED:
        return False
    return cos_credentials_configured()


def storage_backend() -> str:
    """Active byte store: cos | local."""
    return STORAGE_COS if cos_workshop_enabled() else STORAGE_LOCAL


def is_legacy_disk_path(stored_path: str) -> bool:
    """True for pre-COS rows that point at ``/static/chat/...``."""
    return stored_path.startswith(LEGACY_DISK_PREFIX)


def assert_safe_logical_key(logical_key: str) -> str:
    """Reject empty keys and path traversal."""
    cleaned = logical_key.strip().lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise ValueError("Invalid attachment key")
    return cleaned


def build_logical_key(basename: str) -> str:
    """Year/month key with a unique prefix. No COS host in the string."""
    now = datetime.now(UTC)
    return f"{now.year}/{now.month:02d}/{uuid4().hex[:12]}_{basename}"


def full_workshop_cos_key(logical_key: str) -> str:
    """Bucket key under COS_WORKSHOP_PREFIX."""
    return cos_object_key(assert_safe_logical_key(logical_key), prefix=config.COS_WORKSHOP_PREFIX)


def local_path_for_key(logical_key: str, static_root: Path) -> Path:
    """Map a logical key onto the local chat static tree."""
    key = assert_safe_logical_key(logical_key)
    candidate = (static_root / key).resolve()
    root = static_root.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Invalid attachment key")
    return candidate


def _presign_disposition(filename: str, content_type: str) -> Optional[str]:
    if content_type in INLINE_CONTENT_TYPES:
        return None
    safe = filename.replace('"', "").replace("\r", "").replace("\n", "")
    return f'attachment; filename="{safe}"'


def put_attachment_bytes_sync(
    logical_key: str,
    data: bytes,
    content_type: str,
    static_root: Path,
) -> str:
    """Write bytes to COS or local disk. Returns the logical key to persist."""
    key = assert_safe_logical_key(logical_key)
    backend = storage_backend()
    if backend == STORAGE_COS:
        uploaded = upload_bytes(
            data,
            full_workshop_cos_key(key),
            content_type=content_type,
            log_prefix="[Workshop/COS]",
        )
        if not uploaded:
            raise ValueError("Could not store attachment on COS")
        return key
    path = local_path_for_key(key, static_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def resolve_stored_payload_sync(
    stored_path: str,
    content_type: str,
    filename: str,
    static_root: Path,
) -> Optional[AttachmentDownload]:
    """Turn a DB ``file_path`` into a disk path or COS redirect."""
    if is_legacy_disk_path(stored_path):
        try:
            disk_path = local_path_for_key(stored_path[len(LEGACY_DISK_PREFIX) :], static_root)
        except ValueError:
            logger.warning("[Workshop] invalid legacy attachment path: %s", stored_path)
            return None
        if not disk_path.is_file():
            logger.warning("[Workshop] legacy attachment missing on disk: %s", disk_path)
            return None
        return AttachmentDownload(
            content_type=content_type,
            filename=filename,
            disk_path=disk_path,
        )

    key = stored_path
    if cos_workshop_enabled():
        url = generate_presigned_get_url(
            full_workshop_cos_key(key),
            expired=config.COS_WORKSHOP_PRESIGN_GET_TTL,
            response_content_disposition=_presign_disposition(filename, content_type),
        )
        if url:
            return AttachmentDownload(
                content_type=content_type,
                filename=filename,
                redirect_url=url,
            )
        logger.warning("[Workshop/COS] presign failed key=%s", key)

    try:
        disk_path = local_path_for_key(key, static_root)
    except ValueError:
        return None
    if disk_path.is_file():
        return AttachmentDownload(
            content_type=content_type,
            filename=filename,
            disk_path=disk_path,
        )
    return None


async def put_attachment_bytes(
    logical_key: str,
    data: bytes,
    content_type: str,
    static_root: Path,
) -> str:
    """Async write that offloads COS/disk I/O."""
    return await asyncio.to_thread(
        put_attachment_bytes_sync,
        logical_key,
        data,
        content_type,
        static_root,
    )


async def resolve_stored_payload(
    stored_path: str,
    content_type: str,
    filename: str,
    static_root: Path,
) -> Optional[AttachmentDownload]:
    """Async resolve that offloads COS/disk I/O."""
    return await asyncio.to_thread(
        resolve_stored_payload_sync,
        stored_path,
        content_type,
        filename,
        static_root,
    )
