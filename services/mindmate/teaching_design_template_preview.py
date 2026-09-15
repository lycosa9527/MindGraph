"""Cached LibreOffice PDF preview for teaching-design Word templates."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from services.mindmate.teaching_design_template_catalog import (
    find_template,
    template_exists_on_disk,
    template_file_path,
)
from services.mindmate.teaching_design_template_paths import (
    TEMPLATE_KEY_BUNDLED,
    catalog_files_dir,
)
from services.showcase.covers.office_to_pdf import convert_office_to_pdf
from services.utils.error_types import FILE_IO_ERRORS

logger = logging.getLogger(__name__)


def preview_cache_path(template_id: str) -> Path:
    """On-disk PDF cache for one catalog id (including bundled)."""
    safe_id = Path(template_id.strip()).name
    return catalog_files_dir() / f"{safe_id}.preview.pdf"


def invalidate_template_preview(template_id: str) -> None:
    """Drop a stale PDF after the Word file is replaced or deleted."""
    path = preview_cache_path(template_id)
    try:
        if path.is_file():
            path.unlink()
    except FILE_IO_ERRORS:
        logger.warning("[TeachingDesignTemplate] preview_invalidate_failed id=%s", template_id)


def ensure_template_preview_pdf(template_id: str) -> Path:
    """Return a PDF for the Word template, converting when the cache is stale."""
    key = template_id.strip()
    if key != TEMPLATE_KEY_BUNDLED and find_template(key) is None:
        raise FileNotFoundError(f"Teaching-design template missing: {key}")
    if not template_exists_on_disk(key):
        raise FileNotFoundError(f"Teaching-design template missing: {key}")
    source = template_file_path(key)
    cached = preview_cache_path(key)
    if cached.is_file() and cached.stat().st_mtime >= source.stat().st_mtime:
        return cached
    work = catalog_files_dir() / f".preview-work-{Path(key).name}"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    try:
        produced = convert_office_to_pdf(source, work)
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".pdf.tmp")
        tmp.write_bytes(produced.read_bytes())
        tmp.replace(cached)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    logger.info("[TeachingDesignTemplate] preview_ready id=%s", key)
    return cached
