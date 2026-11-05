"""Homework submit thumbnails, stored on the submission row until the PNG lands.

Submit writes the diagram spec and a ``thumb_pending`` token into Postgres.
The API worker renders that row, including after a restart. A failed render
keeps the token and records when to try again.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.domain.learning_space import LearningSubmission
from services.learning_space.image_storage import (
    delete_stored_images_sync,
    is_image_ref,
    logical_key_from_ref,
)
from services.learning_space.thumbnail_storage import promote_snapshot_thumbnail_sync, thumbnail_is_durable
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

THUMB_TOKEN = "thumb_token"
THUMB_PENDING = "thumb_pending"
THUMB_ATTEMPTS = "thumb_attempts"
THUMB_RETRY_AT = "thumb_retry_at"
_RETRY_DELAYS_SECONDS = (15, 60, 300, 900)

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


def thumbnail_clock(now: datetime | None = None) -> str:
    """UTC stamp that sorts as text, matching ``thumb_retry_at`` in Postgres."""
    clock = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    return clock.strftime("%Y-%m-%dT%H:%M:%SZ")


def thumbnail_not_before(now: datetime, delay_seconds: int) -> str:
    """UTC stamp ``delay_seconds`` after ``now``, in the same form as ``thumb_retry_at``."""
    due = now.astimezone(UTC) + timedelta(seconds=max(delay_seconds, 0))
    return due.strftime("%Y-%m-%dT%H:%M:%SZ")


def thumbnail_retry_deadline(now: datetime, attempts: int) -> str:
    """When this failed render may run again. Later failures wait longer."""
    index = min(max(attempts, 1), len(_RETRY_DELAYS_SECONDS)) - 1
    return thumbnail_not_before(now, _RETRY_DELAYS_SECONDS[index])


def _attempt_count(value: object) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def snapshot_thumbnail_due(snapshot: object, now_iso: str) -> bool:
    """True when this saved snapshot still needs a PNG and the backoff has elapsed."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("spec"), dict):
        return False
    pending = snapshot.get(THUMB_PENDING)
    pending_text = pending.strip() if isinstance(pending, str) else ""
    if not pending_text and thumbnail_is_durable(snapshot.get("thumbnail")):
        return False
    retry_at = snapshot.get(THUMB_RETRY_AT)
    retry_text = retry_at.strip() if isinstance(retry_at, str) else ""
    if retry_text and retry_text > now_iso:
        return False
    return True


def clear_thumbnail_work(snapshot: dict[str, Any]) -> None:
    """Drop the retry markers once the current submit has a stored PNG."""
    snapshot.pop(THUMB_PENDING, None)
    snapshot.pop(THUMB_ATTEMPTS, None)
    snapshot.pop(THUMB_RETRY_AT, None)


def _pending_is(snapshot: dict[str, Any], token: str) -> bool:
    pending = snapshot.get(THUMB_PENDING)
    return isinstance(pending, str) and pending == token


def hold_thumbnail_claim(snapshot: dict[str, Any], token: str, now: datetime, delay_seconds: int) -> bool:
    """Reserve this row so a second renderer waits until the PNG is stored."""
    if not token or not isinstance(snapshot.get("spec"), dict):
        return False
    snapshot[THUMB_TOKEN] = token
    snapshot[THUMB_PENDING] = token
    snapshot[THUMB_RETRY_AT] = thumbnail_not_before(now, delay_seconds)
    return True


def schedule_thumbnail_retry(snapshot: dict[str, Any], token: str, now: datetime) -> bool:
    """Keep this submit queued. A finished or newer snapshot is left untouched."""
    if snapshot.get(THUMB_TOKEN) != token or not _pending_is(snapshot, token):
        return False
    attempts = _attempt_count(snapshot.get(THUMB_ATTEMPTS)) + 1
    snapshot[THUMB_ATTEMPTS] = attempts
    snapshot[THUMB_RETRY_AT] = thumbnail_retry_deadline(now, attempts)
    snapshot[THUMB_PENDING] = token
    return True


def apply_submit_thumbnail(snapshot: dict[str, Any], token: str, ref: str) -> bool:
    """Write ``ref`` only when this render still belongs to the current submit."""
    if snapshot.get(THUMB_TOKEN) != token or not _pending_is(snapshot, token) or not is_image_ref(ref):
        return False
    snapshot["thumbnail"] = ref
    clear_thumbnail_work(snapshot)
    return True


def backfill_still_matches(snapshot: dict[str, Any], token: str) -> bool:
    """True when an admin render is still drawing the submit it loaded."""
    if not token:
        return True
    pending = snapshot.get(THUMB_PENDING)
    if isinstance(pending, str) and pending.strip():
        return pending == token
    if thumbnail_is_durable(snapshot.get("thumbnail")):
        return False
    return snapshot.get(THUMB_TOKEN) == token


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


async def record_submit_thumbnail_retry(submission_id: int, token: str, now: datetime | None = None) -> bool:
    """Remember a failed render on the submission so a later pass can draw it."""
    clock = now if now is not None else datetime.now(UTC)
    async with system_rls_session() as db:
        row = await _load_for_thumbnail_update(db, submission_id)
        if row is None or not isinstance(row.snapshot_spec, dict):
            return False
        snap = dict(row.snapshot_spec)
        if not schedule_thumbnail_retry(snap, token, clock):
            return False
        row.snapshot_spec = snap
        flag_modified(row, "snapshot_spec")
        try:
            await db.commit()
        except DATABASE_ERRORS:
            await db.rollback()
            raise
    logger.warning(
        "[LearningSpace] Submit thumbnail retry submission=%s attempt=%s at=%s",
        submission_id,
        snap.get(THUMB_ATTEMPTS),
        snap.get(THUMB_RETRY_AT),
    )
    return True


async def _note_thumbnail_failure(
    job: SubmitThumbnailJob,
    note_failure: Callable[[SubmitThumbnailJob], Awaitable[None]] | None,
    save: SaveThumb | None,
) -> None:
    if note_failure is not None:
        await note_failure(job)
        return
    if save is not None:
        return
    try:
        await record_submit_thumbnail_retry(job.submission_id, job.token)
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Submit thumbnail retry save failed submission=%s: %s",
            job.submission_id,
            exc,
        )


async def _load_for_thumbnail_update(db: AsyncSession, submission_id: int) -> LearningSubmission | None:
    """Lock the submission row so a resubmit cannot land under this write."""
    statement = select(LearningSubmission).where(LearningSubmission.id == submission_id).with_for_update()
    return (await db.execute(statement)).scalar_one_or_none()


async def _save_submit_thumbnail_row(submission_id: int, token: str, ref: str) -> bool:
    """Attach the COS ref when the submission is still the one we rendered."""
    async with system_rls_session() as db:
        row = await _load_for_thumbnail_update(db, submission_id)
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


async def run_submit_thumbnail_job(
    job: SubmitThumbnailJob,
    *,
    save: SaveThumb | None = None,
    note_failure: Callable[[SubmitThumbnailJob], Awaitable[None]] | None = None,
) -> bool:
    """Render, store on COS, then point the committed submission at that image."""
    ref = await render_submit_thumbnail(
        job.spec,
        job.diagram_type,
        owner_id=job.owner_id,
        fallback_thumb=job.fallback_thumb,
    )
    if not is_image_ref(ref):
        logger.warning("[LearningSpace] Submit thumbnail missing submission=%s", job.submission_id)
        await _note_thumbnail_failure(job, note_failure, save)
        return False
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
        await _note_thumbnail_failure(job, note_failure, save)
        return False
    await asyncio.to_thread(_drop_replaced, job.previous_ref, ref)
    logger.info("[LearningSpace] Stored submit thumbnail submission=%s", job.submission_id)
    return True
