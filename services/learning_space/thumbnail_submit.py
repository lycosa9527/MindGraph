"""Homework submit thumbnails, generated after the student has left.

The renderer is installed when the Learning Space thumbnail module loads.
The submit request only stores the diagram snapshot. A background task renders
the PNG, uploads it, and writes the ``lsimg:`` ref onto that same snapshot.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models.domain.learning_space import LearningSubmission
from services.learning_space.image_storage import (
    delete_stored_images_sync,
    is_image_ref,
    logical_key_from_ref,
)
from services.learning_space.thumbnail_storage import promote_snapshot_thumbnail_sync
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

RenderRef = Callable[[object, object, int], Awaitable[str]]
SaveThumb = Callable[[int, str, str], Awaitable[bool]]


class SubmitThumbnailRenderer:
    """Holds the diagram renderer so assignments can stay free of the router cycle."""

    def __init__(self) -> None:
        self.render_ref: RenderRef | None = None


submit_thumbnail_renderer = SubmitThumbnailRenderer()


@dataclass(frozen=True)
class SubmitThumbnailJob:
    """One submitted diagram waiting for a background PNG."""

    submission_id: int
    owner_id: int
    token: str
    spec: object
    diagram_type: object
    fallback_thumb: object
    previous_ref: object


class _InflightThumbnails:
    """Keep background render tasks alive until they finish."""

    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[None]] = set()

    def schedule(self, job: SubmitThumbnailJob) -> None:
        """Start a render without waiting for it."""
        task = asyncio.create_task(run_submit_thumbnail_job(job))
        self.tasks.add(task)
        task.add_done_callback(self._done)

    def _done(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("[LearningSpace] Submit thumbnail task failed: %s", exc)


inflight_thumbnails = _InflightThumbnails()


def schedule_submit_thumbnail(job: SubmitThumbnailJob) -> None:
    """Queue a thumbnail render after the submission row is committed."""
    inflight_thumbnails.schedule(job)


def apply_submit_thumbnail(snapshot: dict[str, Any], token: str, ref: str) -> bool:
    """Write ``ref`` only when this render still belongs to the current submit."""
    if snapshot.get("thumb_token") != token or not is_image_ref(ref):
        return False
    snapshot["thumbnail"] = ref
    return True


async def render_submit_thumbnail(
    spec: object,
    diagram_type: object,
    *,
    owner_id: int,
    fallback_thumb: object,
) -> str:
    """Render the diagram, or upload an existing data URL when render fails."""
    render_ref = submit_thumbnail_renderer.render_ref
    ref = ""
    if render_ref is not None:
        ref = await render_ref(spec, diagram_type, owner_id)
    if is_image_ref(ref):
        return ref
    snap = {"thumbnail": fallback_thumb}
    await asyncio.to_thread(promote_snapshot_thumbnail_sync, snap, owner_id=owner_id)
    promoted = snap.get("thumbnail")
    if isinstance(promoted, str) and is_image_ref(promoted):
        return promoted
    return ""


def _keys_of(value: object) -> list[str]:
    key = logical_key_from_ref(str(value or ""))
    if key is None:
        return []
    return [key]


def _drop_replaced(previous_ref: object, new_ref: str) -> None:
    old = logical_key_from_ref(str(previous_ref or ""))
    new = logical_key_from_ref(new_ref)
    if old and old != new:
        delete_stored_images_sync([old])


async def _save_submit_thumbnail_row(submission_id: int, token: str, ref: str) -> bool:
    """Attach the COS ref when the submission is still the one we rendered."""
    async with system_rls_session() as db:
        row = await db.get(LearningSubmission, submission_id)
        if row is None or not isinstance(row.snapshot_spec, dict):
            return False
        snap = dict(row.snapshot_spec)
        if not apply_submit_thumbnail(snap, token, ref):
            return False
        row.snapshot_spec = snap
        flag_modified(row, "snapshot_spec")
        try:
            await db.commit()
        except DATABASE_ERRORS:
            await db.rollback()
            raise
    return True


async def run_submit_thumbnail_job(job: SubmitThumbnailJob, *, save: SaveThumb | None = None) -> None:
    """Render, store on COS, then point the committed submission at that image."""
    ref = await render_submit_thumbnail(
        job.spec,
        job.diagram_type,
        owner_id=job.owner_id,
        fallback_thumb=job.fallback_thumb,
    )
    if not is_image_ref(ref):
        logger.warning("[LearningSpace] Submit thumbnail missing submission=%s", job.submission_id)
        return
    writer = save or _save_submit_thumbnail_row
    try:
        stored = await writer(job.submission_id, job.token, ref)
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Submit thumbnail save failed submission=%s: %s",
            job.submission_id,
            exc,
        )
        stored = False
    if not stored:
        await asyncio.to_thread(delete_stored_images_sync, _keys_of(ref))
        return
    await asyncio.to_thread(_drop_replaced, job.previous_ref, ref)
    logger.info("[LearningSpace] Stored submit thumbnail submission=%s", job.submission_id)
