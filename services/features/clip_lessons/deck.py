"""PPTX upload and LibreOffice preview for a clip lesson."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.clip_lesson import PREVIEW_FAILED, PREVIEW_PENDING, PREVIEW_READY, ClipLesson
from services.features.clip_lessons.errors import ClipLessonError
from services.features.clip_lessons.lessons import load_owned
from services.features.clip_lessons.storage import (
    lesson_deck_key,
    lesson_preview_key,
    put_object,
    read_object,
)
from services.showcase.covers.office_to_pdf import convert_office_to_pdf
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

DECK_MAX_BYTES = 20 * 1024 * 1024
_PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def assert_pptx(data: bytes) -> None:
    """Reject anything that is not a PPTX package under the size cap."""
    if len(data) > DECK_MAX_BYTES:
        raise ClipLessonError("deck_too_large", 413)
    if len(data) < 4 or data[:2] != b"PK":
        raise ClipLessonError("deck_invalid", 400)
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ClipLessonError("deck_invalid", 400) from exc
    if "ppt/presentation.xml" not in names:
        raise ClipLessonError("deck_invalid", 400)


async def store_deck(db: AsyncSession, user: User, lesson_id: str, data: bytes) -> str:
    """Save the PPTX and mark the preview pending. Returns the lesson id."""
    assert_pptx(data)
    lesson = await load_owned(db, user, lesson_id)
    key = lesson_deck_key(lesson.id)
    try:
        put_object(key, data, _PPTX_TYPE)
    except OSError as exc:
        raise ClipLessonError("deck_store_failed", 503) from exc
    lesson.deck_key = key
    lesson.preview_pdf_key = None
    lesson.preview_status = PREVIEW_PENDING
    lesson.updated_at = datetime.now(UTC)
    await db.commit()
    return lesson.id


async def run_deck_preview(lesson_id: str) -> None:
    """Convert the stored PPTX to PDF. Safe to run after the HTTP response."""
    try:
        await _convert(lesson_id)
    except (OSError, ValueError, ClipLessonError) as exc:
        logger.warning("Clip lesson preview failed lesson=%s: %s", lesson_id, exc)
        await _set_status(lesson_id, PREVIEW_FAILED, None)


async def _convert(lesson_id: str) -> None:
    deck_key = lesson_deck_key(lesson_id)
    data = read_object(deck_key)
    if not data:
        raise ClipLessonError("deck_invalid", 400)
    with tempfile.TemporaryDirectory(prefix="clip-deck-") as temp:
        source = Path(temp) / "deck.pptx"
        source.write_bytes(data)
        pdf_path = convert_office_to_pdf(source, Path(temp))
        pdf_bytes = pdf_path.read_bytes()
    preview_key = lesson_preview_key(lesson_id)
    put_object(preview_key, pdf_bytes, "application/pdf")
    await _set_status(lesson_id, PREVIEW_READY, preview_key)


async def _set_status(lesson_id: str, status: str, preview_key: str | None) -> None:
    async with system_rls_session() as db:
        row = await db.get(ClipLesson, lesson_id)
        if row is None:
            return
        row.preview_status = status
        if preview_key is not None:
            row.preview_pdf_key = preview_key
        await db.commit()


def read_preview(preview_key: str | None, status: str) -> bytes:
    """Return preview PDF bytes when conversion has finished."""
    if status != PREVIEW_READY or not preview_key:
        raise ClipLessonError("preview_pending", 409)
    data = read_object(preview_key)
    if data is None:
        raise ClipLessonError("preview_pending", 409)
    return data
