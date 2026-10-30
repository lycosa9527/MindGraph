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
import shutil
import time
from pathlib import Path
from typing import Optional

from config.settings import config
from services.features.workshop_chat.attachment_storage import (
    assert_safe_logical_key,
    is_legacy_disk_path,
    local_path_for_key,
)
from services.utils.error_types import FILE_IO_ERRORS
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
_SCRATCH_TMP_SUFFIX = ".pdf.tmp"
_WORK_DIR_PREFIX = ".preview-work-"
_LOG = "[Seminar/COS]"
_CACHE_MAX_AGE_SECONDS = 86400


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
) -> bool:
    """Upload a disk-only seminar file to COS. True only when this call stored a new object."""
    logical = _cos_logical_key(storage_key)
    if logical is None or not cos_seminar_enabled() or not path.is_file():
        return False
    full_key = full_seminar_cos_key(logical)
    if object_exists(full_key):
        return False
    uploaded = upload_bytes(
        path.read_bytes(),
        full_key,
        max_retries=1,
        log_prefix=_LOG,
        content_type=content_type or None,
    )
    if uploaded:
        logger.info("[SeminarFiles] COS mirror key=%s", logical)
        return True
    logger.warning("[SeminarFiles] COS mirror failed key=%s", logical)
    return False


def mirror_cached_preview_pdf_sync(storage_key: str, path: Path) -> bool:
    """Upload a local Office preview PDF. Raise when COS is on and the put fails."""
    logical = preview_object_key(storage_key)
    if logical is None or not cos_seminar_enabled() or not path.is_file():
        return False
    full_key = full_seminar_cos_key(logical)
    if object_exists(full_key):
        return False
    uploaded = upload_bytes(
        path.read_bytes(),
        full_key,
        max_retries=1,
        log_prefix=_LOG,
        content_type="application/pdf",
    )
    if not uploaded:
        logger.warning("[SeminarFiles] COS preview mirror failed key=%s", logical)
        raise ValueError("upload_failed")
    logger.info("[SeminarFiles] COS preview mirror key=%s", logical)
    return True


def put_preview_pdf_sync(storage_key: str, data: bytes) -> None:
    """Store a converted preview PDF in COS. Raise when that put fails."""
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
    if not uploaded:
        logger.warning("[SeminarFiles] COS preview upload failed key=%s", logical)
        raise ValueError("upload_failed")
    logger.info("[SeminarFiles] COS preview put bytes=%s key=%s", len(data), logical)


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


def _relative_cache_key(static_root: Path, path: Path) -> Optional[str]:
    """Logical key for a file under the seminar static tree."""
    try:
        key = path.resolve().relative_to(static_root.resolve()).as_posix()
    except FILE_IO_ERRORS:
        return None
    if not key or ".." in key.split("/"):
        return None
    return key


def _cos_has_logical_key(logical_key: str) -> bool:
    if not cos_seminar_enabled():
        return False
    return object_exists(full_seminar_cos_key(logical_key))


def _expired(path: Path, now: float, max_age_seconds: int) -> bool:
    try:
        return now - path.stat().st_mtime > max_age_seconds
    except FILE_IO_ERRORS:
        return False


def seminar_preview_work_dir(source: Path) -> Path:
    """LibreOffice scratch directory beside a seminar source file."""
    return source.parent / f"{_WORK_DIR_PREFIX}{source.stem}"


def seminar_preview_scratch_path(pdf_path: Path) -> Path:
    """Atomic-replace temp written next to a preview PDF."""
    return pdf_path.with_suffix(_SCRATCH_TMP_SUFFIX)


def release_seminar_preview_cache_sync(storage_key: str, source: Path, pdf_path: Path) -> None:
    """Drop LibreOffice scratch, and local copies once COS holds the bytes."""
    scratch = seminar_preview_scratch_path(pdf_path)
    if scratch.is_file() and scratch != source:
        scratch.unlink(missing_ok=True)
    work = seminar_preview_work_dir(source)
    if work.is_dir():
        shutil.rmtree(work, ignore_errors=True)
    if not cos_seminar_enabled():
        return
    logical = _cos_logical_key(storage_key)
    preview_key = preview_object_key(storage_key)
    if preview_key and pdf_path != source and pdf_path.is_file() and _cos_has_logical_key(preview_key):
        pdf_path.unlink(missing_ok=True)
    if logical and source.is_file() and _cos_has_logical_key(logical):
        source.unlink(missing_ok=True)


def cleanup_seminar_disk_cache(
    static_root: Path,
    max_age_seconds: int = _CACHE_MAX_AGE_SECONDS,
) -> int:
    """Remove seminar working copies that COS already holds, plus old preview scratch.

    Preview PDFs and LibreOffice work dirs are regenerable. The uploaded bytes
    stay on disk when COS is off or the object is not in the bucket yet.
    """
    if not static_root.is_dir():
        return 0
    now = time.time()
    removed = 0
    work_dirs: list[Path] = []
    files: list[Path] = []
    try:
        for path in static_root.rglob("*"):
            if path.is_dir() and path.name.startswith(_WORK_DIR_PREFIX):
                work_dirs.append(path)
            elif path.is_file():
                files.append(path)
    except FILE_IO_ERRORS as exc:
        logger.warning("[SeminarFiles] cache scan failed: %s", exc)
        return 0

    for path in work_dirs:
        if not _expired(path, now, max_age_seconds):
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed += 1

    for path in files:
        if not path.is_file() or not _expired(path, now, max_age_seconds):
            continue
        if path.name.endswith(_SCRATCH_TMP_SUFFIX):
            path.unlink(missing_ok=True)
            removed += 1
            continue
        if path.name.endswith(_PREVIEW_SUFFIX):
            if cos_seminar_enabled():
                logical = _relative_cache_key(static_root, path)
                if logical is not None and _cos_has_logical_key(logical):
                    path.unlink(missing_ok=True)
                    removed += 1
                continue
            source = path.with_name(path.name[: -len(_PREVIEW_SUFFIX)])
            if source.is_file():
                path.unlink(missing_ok=True)
                removed += 1
            continue
        logical = _relative_cache_key(static_root, path)
        if logical is not None and _cos_has_logical_key(logical):
            path.unlink(missing_ok=True)
            removed += 1

    if removed:
        logger.info("[SeminarFiles] cache cleanup removed %s local file(s)", removed)
    return removed


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
