"""Push seminar file bytes that still sit on disk up to COS.

Postgres names every shared file, chat chip, and artifact. A new upload writes
COS before the row is saved. This pass catches a copy that was written while
COS was off, or a mirror that failed, including rooms that have already ended.
Local cleanup runs only after this, and only for objects COS already holds.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import select

from models.domain.mindmate_seminar import MindmateSeminarBackgroundFile
from services.features.mindmate_seminar.background_files import seminar_disk_path
from services.features.mindmate_seminar.seminar_file_storage import (
    cos_seminar_enabled,
    mirror_cached_preview_pdf_sync,
    mirror_local_seminar_file_sync,
)
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PAGE_SIZE = 200
_PREVIEW_SUFFIX = ".preview.pdf"
_PENDING: set[asyncio.Task[int]] = set()


def schedule_seminar_cos_sync(session_id: Optional[str] = None) -> None:
    """Mirror one room, or every room, without blocking the caller."""
    task = asyncio.create_task(
        sync_seminar_files_to_cos(session_id),
        name="seminar-cos-sync",
    )
    _PENDING.add(task)
    task.add_done_callback(_PENDING.discard)


def mirror_seminar_disk_copy(storage_key: str, content_type: str) -> int:
    """Upload one stored file and its Office preview when they exist only on disk."""
    uploaded = 0
    disk = seminar_disk_path(storage_key)
    if (
        disk is not None
        and disk.is_file()
        and mirror_local_seminar_file_sync(
            storage_key,
            disk,
            content_type=content_type,
        )
    ):
        uploaded += 1
    if disk is None:
        return uploaded
    preview = disk.with_name(f"{disk.name}{_PREVIEW_SUFFIX}")
    if not preview.is_file():
        return uploaded
    try:
        if mirror_cached_preview_pdf_sync(storage_key, preview):
            uploaded += 1
    except FILE_IO_ERRORS:
        return uploaded
    return uploaded


async def sync_seminar_files_to_cos(session_id: Optional[str] = None) -> int:
    """Upload local seminar bytes Postgres still names. Returns how many objects were stored."""
    if not cos_seminar_enabled():
        return 0
    uploaded = 0
    offset = 0
    try:
        while True:
            async with system_rls_session() as db:
                stmt = (
                    select(
                        MindmateSeminarBackgroundFile.storage_key,
                        MindmateSeminarBackgroundFile.content_type,
                    )
                    .order_by(
                        MindmateSeminarBackgroundFile.created_at,
                        MindmateSeminarBackgroundFile.id,
                    )
                    .offset(offset)
                    .limit(_PAGE_SIZE)
                )
                if session_id:
                    stmt = stmt.where(MindmateSeminarBackgroundFile.session_id == session_id)
                rows = list((await db.execute(stmt)).all())
            if not rows:
                break
            for storage_key, content_type in rows:
                uploaded += await asyncio.to_thread(
                    mirror_seminar_disk_copy,
                    str(storage_key),
                    str(content_type or ""),
                )
            if len(rows) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
    except DATABASE_ERRORS as exc:
        logger.warning("[Seminar/COS] sync failed session=%s: %s", session_id or "*", exc)
        return uploaded
    if uploaded:
        logger.info(
            "[Seminar/COS] mirrored %s object(s) session=%s",
            uploaded,
            session_id or "*",
        )
    return uploaded
