"""Age out classroom working copies on this server.

When COS is on, local transcripts/images are a cache — same idea as
``temp_images/``. Durable bytes stay on COS and are hydrated on return.
When COS is off, local files are the only copy and must not be deleted.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import aiofiles.os

from services.mind_classroom.storage_keys import classroom_local_root
from services.utils.error_types import FILE_IO_ERRORS
from services.zhihui.storage.backend import cos_zhihui_enabled

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_SECONDS = 86400
_TEMP_SUBDIRS = ("transcripts", "generations")


def list_classroom_temp_files(root: Path) -> list[Path]:
    """Return files under the classroom working-copy dirs."""
    found: list[Path] = []
    for name in _TEMP_SUBDIRS:
        folder = root / name
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if path.is_file():
                found.append(path)
    return found


async def cleanup_classroom_temp_files(max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> int:
    """Delete local classroom files older than max_age_seconds when COS is on."""
    if not cos_zhihui_enabled():
        return 0
    root = classroom_local_root()
    if not root.exists():
        return 0
    current_time = time.time()
    deleted = 0
    try:
        files = await asyncio.to_thread(list_classroom_temp_files, root)
        for file_path in files:
            try:
                stat_result = await aiofiles.os.stat(file_path)
                file_age = current_time - stat_result.st_mtime
                if file_age <= max_age_seconds:
                    continue
                await aiofiles.os.remove(file_path)
                deleted += 1
                logger.debug(
                    "[MindClassroom] Deleted expired temp %s (age: %.1fh)",
                    file_path.name,
                    file_age / 3600,
                )
            except FILE_IO_ERRORS as exc:
                logger.warning("[MindClassroom] Temp cleanup skip %s: %s", file_path.name, exc)
        if deleted:
            logger.info("[MindClassroom] Temp cleanup deleted %s expired file(s)", deleted)
        return deleted
    except FILE_IO_ERRORS as exc:
        logger.error("[MindClassroom] Temp cleanup failed: %s", exc)
        return deleted
