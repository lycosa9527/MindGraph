"""MindMate seminar file bytes: private COS, local disk only when COS is off.

Chat text stays in Postgres. ``storage_key`` is a logical key. The browser
always reads bytes through the seminar download route (fetch + blob), so COS
objects are proxied instead of redirected.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from config.settings import config
from services.features.workshop_chat.attachment_storage import (
    assert_safe_logical_key,
    is_legacy_disk_path,
    local_path_for_key,
)
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    delete_object,
    get_object_bytes,
    object_exists,
    upload_bytes,
)

logger = logging.getLogger(__name__)

_PREVIEW_SUFFIX = ".preview.pdf"
_LOG = "[Seminar/COS]"


def cos_seminar_enabled() -> bool:
    """True when seminar COS storage is on and credentials exist."""
    if not config.COS_SEMINAR_ENABLED:
        return False
    return cos_credentials_configured()


def full_seminar_cos_key(logical_key: str) -> str:
    """Bucket key under the mindmate prefix (``{server}/mindmate`` or ``mindmate/mindgraph``)."""
    return cos_object_key(assert_safe_logical_key(logical_key), prefix=config.COS_SEMINAR_PREFIX)


def _cos_logical_key(storage_key: str) -> Optional[str]:
    """Return a COS logical key, or None for legacy disk paths and traversal."""
    if is_legacy_disk_path(storage_key):
        return None
    try:
        return assert_safe_logical_key(storage_key)
    except ValueError:
        return None


def preview_object_key(storage_key: str) -> Optional[str]:
    """COS logical key for a converted Office preview PDF."""
    logical = _cos_logical_key(storage_key)
    if logical is None:
        return None
    return f"{logical}{_PREVIEW_SUFFIX}"


def put_seminar_bytes_sync(
    logical_key: str,
    data: bytes,
    content_type: str,
    static_root: Path,
) -> str:
    """Write bytes to COS or local disk. Returns the logical key to persist."""
    key = assert_safe_logical_key(logical_key)
    if cos_seminar_enabled():
        uploaded = upload_bytes(
            data,
            full_seminar_cos_key(key),
            max_retries=1,
            log_prefix=_LOG,
            content_type=content_type,
        )
        if not uploaded:
            raise ValueError("upload_failed")
        logger.info("[SeminarFiles] COS put bytes=%s key=%s", len(data), key)
        return key
    path = local_path_for_key(key, static_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.info("[SeminarFiles] local put bytes=%s key=%s", len(data), key)
    return key


def read_seminar_bytes_sync(storage_key: str, *, max_bytes: int) -> Optional[bytes]:
    """Read one seminar object from COS. None when COS is off or the object is missing."""
    logical = _cos_logical_key(storage_key)
    if logical is None or not cos_seminar_enabled():
        return None
    return get_object_bytes(
        full_seminar_cos_key(logical),
        max_retries=1,
        log_prefix=_LOG,
        max_bytes=max_bytes,
    )


def mirror_local_seminar_file_sync(
    storage_key: str,
    path: Path,
    *,
    content_type: str = "",
) -> None:
    """Upload a disk-only seminar file to COS. Skip when COS is off or the object is already there."""
    logical = _cos_logical_key(storage_key)
    if logical is None or not cos_seminar_enabled() or not path.is_file():
        return
    full_key = full_seminar_cos_key(logical)
    if object_exists(full_key):
        return
    uploaded = upload_bytes(
        path.read_bytes(),
        full_key,
        max_retries=1,
        log_prefix=_LOG,
        content_type=content_type or None,
    )
    if uploaded:
        logger.info("[SeminarFiles] COS mirror key=%s", logical)
    else:
        logger.warning("[SeminarFiles] COS mirror failed key=%s", logical)


def mirror_cached_preview_pdf_sync(storage_key: str, path: Path) -> None:
    """Upload a local Office preview PDF that was converted before COS was in use."""
    logical = preview_object_key(storage_key)
    if logical is None or not cos_seminar_enabled() or not path.is_file():
        return
    full_key = full_seminar_cos_key(logical)
    if object_exists(full_key):
        return
    uploaded = upload_bytes(
        path.read_bytes(),
        full_key,
        max_retries=1,
        log_prefix=_LOG,
        content_type="application/pdf",
    )
    if uploaded:
        logger.info("[SeminarFiles] COS preview mirror key=%s", logical)
    else:
        logger.warning("[SeminarFiles] COS preview mirror failed key=%s", logical)


def put_preview_pdf_sync(storage_key: str, data: bytes) -> None:
    """Mirror a converted preview PDF to COS. Local cache remains if the upload fails."""
    logical = preview_object_key(storage_key)
    if logical is None or not data or not cos_seminar_enabled():
        return
    uploaded = upload_bytes(
        data,
        full_seminar_cos_key(logical),
        max_retries=1,
        log_prefix=_LOG,
        content_type="application/pdf",
    )
    if uploaded:
        logger.info("[SeminarFiles] COS preview put bytes=%s key=%s", len(data), logical)
    else:
        logger.warning("[SeminarFiles] COS preview upload failed key=%s", logical)


def pull_preview_pdf_sync(storage_key: str, dest: Path) -> bool:
    """Download a converted preview PDF from COS onto ``dest``."""
    logical = preview_object_key(storage_key)
    if logical is None or not cos_seminar_enabled():
        return False
    data = get_object_bytes(
        full_seminar_cos_key(logical),
        max_retries=1,
        log_prefix=_LOG,
    )
    if not data:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def delete_seminar_bytes_sync(storage_key: str, static_root: Path) -> None:
    """Remove local bytes, the local preview PDF, and the COS objects."""
    try:
        path = local_path_for_key(storage_key, static_root)
    except ValueError:
        path = None
    if path is not None and path.is_file():
        path.unlink(missing_ok=True)
    if path is not None:
        preview = path.with_name(f"{path.name}{_PREVIEW_SUFFIX}")
        if preview.is_file():
            preview.unlink(missing_ok=True)
    logical = _cos_logical_key(storage_key)
    if logical is None or not cos_seminar_enabled():
        return
    delete_object(full_seminar_cos_key(logical))
    preview_key = preview_object_key(storage_key)
    if preview_key is not None:
        delete_object(full_seminar_cos_key(preview_key))
