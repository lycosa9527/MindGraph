"""On-demand PDF preview for seminar shared files (LibreOffice for Office).

Native PDF is served as-is. Office documents are converted once. When COS is
on, the source and the preview PDF stay in the bucket, and local working
copies are removed after the response bytes are in memory.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from models.domain.mindmate_seminar import MindmateSeminarBackgroundFile
from services.features.mindmate_seminar.background_files import (
    MAX_BACKGROUND_BYTES,
    seminar_disk_path,
)
from services.features.mindmate_seminar.seminar_file_storage import (
    mirror_cached_preview_pdf_sync,
    mirror_local_seminar_file_sync,
    pull_preview_pdf_sync,
    put_preview_pdf_sync,
    read_seminar_bytes_sync,
    release_seminar_preview_cache_sync,
    seminar_preview_scratch_path,
    seminar_preview_work_dir,
)
from services.showcase.covers.office_to_pdf import convert_office_to_pdf, office_suffix_needs_pdf
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PREVIEW_SUFFIX = ".preview.pdf"


def preview_cache_path(source: Path) -> Path:
    """Stable PDF cache path beside the uploaded bytes."""
    return source.with_name(f"{source.name}{_PREVIEW_SUFFIX}")


def _materialize_source(storage_key: str) -> Path:
    """Return a local source file, downloading it from COS when this host has no copy."""
    source = seminar_disk_path(storage_key)
    if source is None:
        raise ValueError("preview_missing")
    if source.is_file():
        mirror_local_seminar_file_sync(storage_key, source)
        return source
    data = read_seminar_bytes_sync(storage_key, max_bytes=MAX_BACKGROUND_BYTES)
    if not data:
        raise ValueError("preview_missing")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(data)
    return source


def _ensure_preview_pdf_sync(source: Path, filename: str, storage_key: str) -> Path:
    """Return a readable PDF for ``source``, converting Office when needed."""
    suffix = Path(filename).suffix.lower() or source.suffix.lower()
    if suffix == ".pdf":
        if not source.is_file():
            raise ValueError("preview_missing")
        return source
    if not office_suffix_needs_pdf(suffix):
        raise ValueError("preview_unsupported")
    if not source.is_file():
        raise ValueError("preview_missing")
    cached = preview_cache_path(source)
    if cached.is_file() and cached.stat().st_mtime >= source.stat().st_mtime:
        mirror_cached_preview_pdf_sync(storage_key, cached)
        return cached
    if pull_preview_pdf_sync(storage_key, cached) and cached.is_file():
        return cached
    work = seminar_preview_work_dir(source)
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    tmp = seminar_preview_scratch_path(cached)
    try:
        # LibreOffice keeps the stem; use a copy so odd unicode names stay stable.
        work_source = work / f"source{suffix}"
        shutil.copy2(source, work_source)
        produced = convert_office_to_pdf(work_source, work)
        tmp.write_bytes(produced.read_bytes())
        tmp.replace(cached)
    except (OSError, RuntimeError) as exc:
        tmp.unlink(missing_ok=True)
        raise ValueError("preview_failed") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    logger.info("[SeminarFiles] preview_ready file=%s pdf=%s", filename, cached.name)
    put_preview_pdf_sync(storage_key, cached.read_bytes())
    return cached


def _load_preview_bytes_sync(storage_key: str, filename: str) -> bytes:
    """Convert if needed, read the PDF, then drop scratch even when convert fails."""
    source = _materialize_source(storage_key)
    pdf_path = preview_cache_path(source)
    try:
        pdf_path = _ensure_preview_pdf_sync(source, filename, storage_key)
        return pdf_path.read_bytes()
    finally:
        release_seminar_preview_cache_sync(storage_key, source, pdf_path)


async def resolve_background_preview_pdf(session_id: str, file_id: str) -> tuple[bytes, str]:
    """Return ``(pdf_bytes, download_name)`` for the browser preview."""
    async with system_rls_session() as db:
        row = await db.get(MindmateSeminarBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        storage_key = row.storage_key
        filename = row.filename
    data = await asyncio.to_thread(_load_preview_bytes_sync, storage_key, filename)
    return data, f"{Path(filename).stem}.pdf"
