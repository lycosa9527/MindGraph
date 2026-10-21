"""On-demand PDF preview for seminar shared files (LibreOffice for Office).

Native PDF is served as-is. Office documents are converted once and cached
next to the source blob so every participant can read them in the browser.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from models.domain.mindmate_collab import MindmateCollabBackgroundFile
from services.features.mindmate_collab.background_files import seminar_disk_path
from services.showcase.covers.office_to_pdf import convert_office_to_pdf, office_suffix_needs_pdf
from services.utils.error_types import FILE_IO_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PREVIEW_SUFFIX = ".preview.pdf"


def preview_cache_path(source: Path) -> Path:
    """Stable PDF cache path beside the uploaded bytes."""
    return source.with_name(f"{source.name}{_PREVIEW_SUFFIX}")


def _source_disk_path(storage_key: str) -> Optional[Path]:
    """Resolve the on-disk source for a seminar storage key."""
    return seminar_disk_path(storage_key)


def _ensure_preview_pdf_sync(source: Path, filename: str) -> Path:
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
        return cached
    work = source.parent / f".preview-work-{source.stem}"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    try:
        # LibreOffice keeps the stem; use a copy so odd unicode names stay stable.
        work_source = work / f"source{suffix}"
        shutil.copy2(source, work_source)
        produced = convert_office_to_pdf(work_source, work)
        tmp = cached.with_suffix(".pdf.tmp")
        tmp.write_bytes(produced.read_bytes())
        tmp.replace(cached)
    except ValueError:
        raise
    except FILE_IO_ERRORS as exc:
        raise ValueError("preview_failed") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    logger.info("[SeminarFiles] preview_ready file=%s pdf=%s", filename, cached.name)
    return cached


async def resolve_background_preview_pdf(session_id: str, file_id: str) -> tuple[Path, str]:
    """Return ``(pdf_path, download_name)`` ready for an inline FileResponse."""
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        storage_key = row.storage_key
        filename = row.filename
    source = _source_disk_path(storage_key)
    if source is None:
        raise ValueError("preview_missing")
    pdf_path = await asyncio.to_thread(_ensure_preview_pdf_sync, source, filename)
    return pdf_path, f"{Path(filename).stem}.pdf"
