"""Persist and wipe classroom slide images."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from repositories.mind_classroom_repo import MindClassroomSlideRepository
from services.mind_classroom.lease import LeaseLost
from services.mind_classroom.storage import delete_key, put_bytes
from services.mind_classroom.storage_keys import build_slide_key
from services.t2i.wan_image_client import DEFAULT_WAN_SIZE, download_image_bytes
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


async def persist_slide(
    *,
    job_id: str,
    user_id: int,
    prompt: str,
    image_url: str,
    size: Optional[str],
    slide_index: int,
    slide_title: Optional[str],
    teacher_script: Optional[str],
    focus_node_ids: Optional[list[str]],
) -> dict[str, Any]:
    """Download, store, and persist one slide."""
    image_bytes = await download_image_bytes(image_url)
    slide_id = str(uuid.uuid4())
    logical_key = build_slide_key(slide_id=slide_id, suffix=".png")
    await put_bytes(logical_key, image_bytes, content_type="image/png")
    script = (teacher_script or "").strip() or None
    try:
        async with system_rls_session() as db:
            repo = MindClassroomSlideRepository(db)
            await repo.create_slide(
                slide_id=slide_id,
                job_id=job_id,
                user_id=user_id,
                slide_index=slide_index,
                cos_logical_key=logical_key,
                title=slide_title,
                teacher_script=script[:4000] if script else None,
                focus_node_ids=focus_node_ids,
                content_type="image/png",
                size=size or DEFAULT_WAN_SIZE,
                prompt=prompt,
                commit=True,
            )
    except IntegrityError as exc:
        await delete_key(logical_key)
        raise LeaseLost(f"duplicate slide_index={slide_index}") from exc
    except DATABASE_ERRORS:
        await delete_key(logical_key)
        raise
    return {"slide_id": slide_id, "logical_key": logical_key, "bytes": len(image_bytes)}


async def wipe_slides(job_id: str) -> None:
    """Delete persisted slides and COS objects for a job."""
    async with system_rls_session() as db:
        repo = MindClassroomSlideRepository(db)
        keys = await repo.delete_by_job(job_id, commit=True)
    for key in keys:
        await delete_key(key)
    logger.info("[MindClassroom] Wipe slides job=%s count=%s", job_id, len(keys))
