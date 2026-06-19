"""
Temporary export artifact cleanup (MindMate export jobs).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select

from models.domain.mindmate_export_job import MindmateExportJob
from services.dify.export.export_config import STUCK_JOB_SECONDS
from services.dify.export.job_storage import TEMP_EXPORTS_DIR, remove_job_dir
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

try:
    from services.redis.redis_async_client import get_async_redis
    from services.redis.redis_client import is_redis_available

    _REDIS_AVAILABLE = True
except ImportError:
    get_async_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

CLEANUP_LOCK_KEY = "cleanup:temp_exports:lock"
CLEANUP_LOCK_TTL = 600


class ExportCleanupLockState:
    """Hold a stable Redis lock token for export cleanup."""

    def __init__(self) -> None:
        self.lock_id: Optional[str] = None

    def lock_id_value(self) -> str:
        """Return a process-scoped lock id, creating it on first use."""
        if self.lock_id is None:
            self.lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        return self.lock_id


_lock_state = ExportCleanupLockState()


async def _acquire_lock() -> bool:
    if (
        not _REDIS_AVAILABLE
        or is_redis_available is None
        or get_async_redis is None
        or not is_redis_available()
    ):
        return True
    try:
        redis = await get_async_redis()
        acquired = await redis.set(
            CLEANUP_LOCK_KEY,
            _lock_state.lock_id_value(),
            nx=True,
            ex=CLEANUP_LOCK_TTL,
        )
        return bool(acquired)
    except REDIS_ERRORS:
        return True


async def _mark_stuck_jobs(now: datetime) -> int:
    """Mark long-idle running jobs as failed so admins can retry."""
    stuck_before = now - timedelta(seconds=STUCK_JOB_SECONDS)
    marked = 0
    async with rls_async_session(RlsContext.system_bootstrap()) as db:
        rows = (
            await db.execute(
                select(MindmateExportJob).where(
                    MindmateExportJob.status.in_(("running", "pending")),
                    MindmateExportJob.updated_at < stuck_before,
                )
            )
        ).scalars().all()
        for job in rows:
            job.status = "failed"
            job.error_message = (
                f"Export job stalled (no progress for {STUCK_JOB_SECONDS}s)"
            )[:2000]
            job.updated_at = now
            marked += 1
        if rows:
            await db.commit()
    return marked


async def cleanup_expired_exports() -> int:
    """Remove expired job rows and their artifact directories."""
    if not await _acquire_lock():
        return 0
    removed = 0
    now = datetime.now(UTC)
    await _mark_stuck_jobs(now)
    async with rls_async_session(RlsContext.system_bootstrap()) as db:
        rows = (
            await db.execute(
                select(MindmateExportJob).where(
                    MindmateExportJob.expires_at.is_not(None),
                    MindmateExportJob.expires_at < now,
                )
            )
        ).scalars().all()
        for job in rows:
            remove_job_dir(int(job.id))
            removed += 1
        if rows:
            ids = [int(job.id) for job in rows]
            await db.execute(delete(MindmateExportJob).where(MindmateExportJob.id.in_(ids)))
            await db.commit()
    if TEMP_EXPORTS_DIR.is_dir():
        for child in TEMP_EXPORTS_DIR.iterdir():
            if not child.is_dir():
                continue
            try:
                mtime = child.stat().st_mtime
                if time.time() - mtime > 86400:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                continue
    return removed


async def run_export_cleanup_scheduler(interval_seconds: int = 3600) -> None:
    """Background loop to purge expired export artifacts."""
    while True:
        try:
            count = await cleanup_expired_exports()
            if count:
                logger.info("[TempExportCleaner] removed %s expired export jobs", count)
        except (*DATABASE_ERRORS, *BACKGROUND_INFRA_ERRORS, OSError) as exc:
            logger.warning("[TempExportCleaner] cleanup failed: %s", exc)
        await asyncio.sleep(interval_seconds)


async def start_export_cleanup_scheduler(interval_hours: int = 1) -> None:
    """Run expired export cleanup on an interval (called from app lifespan)."""
    await run_export_cleanup_scheduler(interval_seconds=max(1, interval_hours) * 3600)
