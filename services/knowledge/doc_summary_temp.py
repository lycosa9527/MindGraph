"""Short-lived temp files for Document Summary binary ingest.

Original uploads and LibreOffice intermediates live under
``{KNOWLEDGE_STORAGE_DIR}/doc_summary_tmp/...`` and must be deleted after
extract succeeds or fails. Only ``extracted.md`` is durable.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

from config.settings import config
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from services.utils.safe_upload import safe_upload_basename

logger = logging.getLogger(__name__)

DOC_SUMMARY_TMP_DIRNAME = "doc_summary_tmp"
DEFAULT_TMP_MAX_AGE_SECONDS = 3600
_SWEEP_INTERVAL_SECONDS = 1800


def doc_summary_tmp_root() -> Path:
    """Root directory for Document Summary temporary uploads."""
    return Path(config.KNOWLEDGE_STORAGE_DIR) / DOC_SUMMARY_TMP_DIRNAME


def build_job_temp_dir(user_id: int, package_id: int, job_id: Optional[str] = None) -> Path:
    """Create (and return) a unique temp directory for one ingest job."""
    resolved_job = job_id or uuid.uuid4().hex
    path = doc_summary_tmp_root() / f"user_{user_id}" / f"pkg_{package_id}" / resolved_job
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_upload_temp(
    *,
    user_id: int,
    package_id: int,
    file_name: str,
    content: bytes,
    job_id: Optional[str] = None,
) -> tuple[Path, Path]:
    """Write upload bytes into a job temp dir. Returns ``(job_dir, file_path)``."""
    job_dir = build_job_temp_dir(user_id, package_id, job_id=job_id)
    safe_name = safe_upload_basename(file_name)
    file_path = job_dir / safe_name
    file_path.write_bytes(content)
    return job_dir, file_path


def unlink_paths(paths: Iterable[Optional[str | Path]]) -> None:
    """Best-effort delete of files (never raises)."""
    for raw in paths:
        if not raw:
            continue
        path = Path(raw)
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("[DocSummaryTemp] Failed to delete file %s: %s", path, exc)


def remove_job_dir(job_dir: Optional[str | Path]) -> None:
    """Remove an entire ingest job temp directory."""
    if not job_dir:
        return
    path = Path(job_dir)
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    except OSError as exc:
        logger.warning("[DocSummaryTemp] Failed to remove job dir %s: %s", path, exc)


def sweep_stale_doc_summary_temps(max_age_seconds: int = DEFAULT_TMP_MAX_AGE_SECONDS) -> int:
    """Delete stale job dirs under doc_summary_tmp. Returns removed directory count."""
    root = doc_summary_tmp_root()
    if not root.is_dir():
        return 0

    cutoff = time.time() - max_age_seconds
    removed = 0
    for job_dir in _iter_job_dirs(root):
        try:
            mtime = job_dir.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
            removed += 1
        except OSError as exc:
            logger.warning("[DocSummaryTemp] Sweep failed for %s: %s", job_dir, exc)
    if removed:
        logger.info("[DocSummaryTemp] Swept %s stale temp job dirs", removed)
    return removed


def _iter_job_dirs(root: Path) -> List[Path]:
    """Yield job directories: user_*/pkg_*/{job_id}."""
    jobs: List[Path] = []
    for user_dir in root.glob("user_*"):
        if not user_dir.is_dir():
            continue
        for pkg_dir in user_dir.glob("pkg_*"):
            if not pkg_dir.is_dir():
                continue
            for job_dir in pkg_dir.iterdir():
                if job_dir.is_dir():
                    jobs.append(job_dir)
    return jobs


async def start_doc_summary_tmp_cleanup_scheduler(
    interval_seconds: int = _SWEEP_INTERVAL_SECONDS,
) -> None:
    """Periodically sweep orphaned Document Summary temp job directories."""
    while True:
        try:
            await asyncio.to_thread(sweep_stale_doc_summary_temps)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[DocSummaryTemp] Cleanup scheduler error: %s", exc)
        await asyncio.sleep(interval_seconds)
