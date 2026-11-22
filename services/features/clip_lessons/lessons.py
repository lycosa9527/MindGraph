"""Create, trim, and play a clip-teaching lesson."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.domain.auth import User
from models.domain.clip_lesson import ClipLesson, ClipLessonChapter
from models.domain.vod import VodMedia, generate_vod_uuid
from services.features.clip_lessons.errors import ClipLessonError
from services.features.clip_lessons.rules import (
    ChapterDraft,
    can_edit_lesson,
    drop_chapters_outside,
    normalize_chapters,
    normalize_title,
    parse_lesson_id,
    validate_trim,
)
from services.features.clip_lessons.serialize import lesson_payload, lesson_summary
from services.features.clip_lessons.storage import (
    delete_object_key,
    lesson_video_key,
    local_video_file,
    uses_local_disk,
    video_media_type,
    write_local_video,
)
from services.features.vod.catalog import (
    VodCatalogError,
    delete_catalog_media,
    issue_play_token,
    issue_upload_signature,
    register_media,
)
from services.utils.error_types import SQLAlchemyError
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def require_organization_id(user: User) -> int:
    """Clip teaching is organization-scoped."""
    if user.organization_id is None:
        raise ClipLessonError("organization_required", 403)
    return int(user.organization_id)


async def display_name(db: AsyncSession, user_id: int) -> str:
    """Visible name for a user id, or an empty string when the row is hidden."""
    name = await db.scalar(select(User.name).where(User.id == user_id))
    if isinstance(name, str) and name.strip():
        return name.strip()
    return ""


async def get_visible_lesson(db: AsyncSession, lesson_id: str) -> ClipLesson:
    """Load a lesson the current row-level policy allows the caller to see."""
    parsed = parse_lesson_id(lesson_id)
    row = await db.get(ClipLesson, parsed)
    if row is None:
        raise ClipLessonError("not_found", 404)
    return row


async def _require_owner(db: AsyncSession, user: User, lesson_id: str) -> ClipLesson:
    row = await get_visible_lesson(db, lesson_id)
    if not can_edit_lesson(int(user.id), int(row.owner_id)):
        raise ClipLessonError("forbidden", 403)
    if int(row.organization_id) != require_organization_id(user):
        raise ClipLessonError("forbidden", 403)
    return row


async def _chapters(db: AsyncSession, lesson_id: str) -> list[ClipLessonChapter]:
    result = await db.scalars(
        select(ClipLessonChapter).where(ClipLessonChapter.lesson_id == lesson_id).order_by(ClipLessonChapter.start_ms)
    )
    return list(result.all())


async def _video_meta(media_id: Optional[str], organization_id: int) -> tuple[Optional[str], Optional[int]]:
    if not media_id:
        return None, None
    async with system_rls_session() as db:
        row = await db.get(VodMedia, media_id)
        if row is None or int(row.organization_id) != organization_id:
            return None, None
        return row.status, row.duration_ms


async def _detail(db: AsyncSession, user: User, row: ClipLesson) -> dict[str, object]:
    chapters = await _chapters(db, row.id)
    status, duration = await _video_meta(row.vod_media_id, int(row.organization_id))
    return lesson_payload(
        row,
        owner_name=await display_name(db, int(row.owner_id)),
        viewer_id=int(user.id),
        chapters=chapters,
        video_status=status,
        duration_ms=duration,
        video_storage="local" if uses_local_disk() else "vod",
    )


async def list_lessons(db: AsyncSession, user: User) -> list[dict[str, object]]:
    """Lessons in the caller's organization, newest first."""
    org_id = require_organization_id(user)
    result = await db.scalars(
        select(ClipLesson).where(ClipLesson.organization_id == org_id).order_by(ClipLesson.updated_at.desc())
    )
    rows = list(result.all())
    payloads: list[dict[str, object]] = []
    for row in rows:
        payloads.append(
            lesson_summary(row, owner_name=await display_name(db, int(row.owner_id)), viewer_id=int(user.id))
        )
    return payloads


async def create_lesson(db: AsyncSession, user: User, title: str) -> dict[str, object]:
    """Open an empty lesson for the owner."""
    org_id = require_organization_id(user)
    now = datetime.now(UTC)
    row = ClipLesson(
        organization_id=org_id,
        owner_id=int(user.id),
        title=normalize_title(title),
        trim_start_ms=0,
        preview_status="none",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _detail(db, user, row)


async def get_lesson_detail(db: AsyncSession, user: User, lesson_id: str) -> dict[str, object]:
    """One lesson visible to the caller's organization."""
    require_organization_id(user)
    row = await get_visible_lesson(db, lesson_id)
    return await _detail(db, user, row)


async def rename_lesson(db: AsyncSession, user: User, lesson_id: str, title: str) -> dict[str, object]:
    """Owner renames the lesson."""
    row = await _require_owner(db, user, lesson_id)
    row.title = normalize_title(title)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return await _detail(db, user, row)


async def _replace_chapter_rows(db: AsyncSession, lesson: ClipLesson, drafts: list[ChapterDraft]) -> None:
    existing = await _chapters(db, lesson.id)
    for row in existing:
        await db.delete(row)
    await db.flush()
    for draft in drafts:
        db.add(
            ClipLessonChapter(
                lesson_id=lesson.id,
                title=draft.title,
                start_ms=draft.start_ms,
            )
        )


async def set_trim(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    start_ms: int,
    end_ms: int | None,
) -> dict[str, object]:
    """Save the playback window and drop chapters that fall outside it."""
    row = await _require_owner(db, user, lesson_id)
    start, end = validate_trim(start_ms, end_ms)
    current = [ChapterDraft(title=chapter.title, start_ms=chapter.start_ms) for chapter in await _chapters(db, row.id)]
    kept = drop_chapters_outside(current, start, end)
    row.trim_start_ms = start
    row.trim_end_ms = end
    row.updated_at = datetime.now(UTC)
    await _replace_chapter_rows(db, row, kept)
    await db.commit()
    return await _detail(db, user, row)


async def replace_chapters(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    drafts: list[ChapterDraft],
) -> dict[str, object]:
    """Replace the timeline. Every start must sit inside the current trim."""
    row = await _require_owner(db, user, lesson_id)
    cleaned = normalize_chapters(drafts, int(row.trim_start_ms), row.trim_end_ms)
    row.updated_at = datetime.now(UTC)
    await _replace_chapter_rows(db, row, cleaned)
    await db.commit()
    return await _detail(db, user, row)


_VIDEO_MAX_BYTES = 100 * 1024 * 1024


async def store_local_video(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    filename: str,
    data: bytes,
) -> dict[str, object]:
    """Save the clip on this development machine and point the lesson at the file."""
    if not uses_local_disk():
        raise ClipLessonError("not_found", 404)
    if len(data) > _VIDEO_MAX_BYTES:
        raise ClipLessonError("video_too_large", 413)
    suffix = Path(filename).suffix.lower()
    try:
        key = lesson_video_key(lesson_id, suffix)
    except ValueError as exc:
        raise ClipLessonError("video_invalid", 400) from exc
    row = await _require_owner(db, user, lesson_id)
    old_media = row.vod_media_id
    old_key = row.local_video_key
    write_local_video(key, data)
    row.local_video_key = key
    row.vod_media_id = None
    row.updated_at = datetime.now(UTC)
    await db.commit()
    if old_key and old_key != key:
        try:
            delete_object_key(old_key)
        except ValueError as exc:
            logger.warning("Clip lesson video cleanup skipped key=%s: %s", old_key, exc)
    if old_media:
        await _drop_media(old_media)
    return await get_lesson_detail(db, user, lesson_id)


def local_video_response_path(row: ClipLesson) -> tuple[Path, str]:
    """File and content type for a development clip. Raises when it is missing."""
    if not uses_local_disk() or not row.local_video_key:
        raise ClipLessonError("video_missing", 404)
    try:
        path = local_video_file(row.local_video_key)
        media_type = video_media_type(row.local_video_key)
    except ValueError as exc:
        raise ClipLessonError("video_missing", 404) from exc
    if not path.is_file():
        raise ClipLessonError("video_missing", 404)
    return path, media_type


async def sign_video_upload(db: AsyncSession, user: User, lesson_id: str) -> dict[str, object]:
    """One-time Tencent upload signature for this lesson's owner."""
    row = await _require_owner(db, user, lesson_id)
    try:
        payload = issue_upload_signature(int(row.organization_id), int(row.owner_id), generate_vod_uuid())
    except VodCatalogError as exc:
        raise ClipLessonError(exc.code, exc.http_status) from exc
    return payload


async def attach_video(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    file_id: str,
    source_context: str,
) -> dict[str, object]:
    """Register a finished Tencent upload and point the lesson at it."""
    row = await _require_owner(db, user, lesson_id)
    org_id = int(row.organization_id)
    title = row.title
    old_media = row.vod_media_id
    try:
        async with system_rls_session() as catalog:
            media = await register_media(
                catalog,
                organization_id=org_id,
                owner=user,
                file_id=file_id,
                title=title,
                source_context=source_context,
                refresh=True,
            )
            await catalog.commit()
            media_id = media.id
    except VodCatalogError as exc:
        raise ClipLessonError(exc.code, exc.http_status) from exc
    stored = await _require_owner(db, user, lesson_id)
    stored.vod_media_id = media_id
    stored.updated_at = datetime.now(UTC)
    await db.commit()
    if old_media and old_media != media_id:
        await _drop_media(old_media)
    return await get_lesson_detail(db, user, lesson_id)


async def _drop_media(media_id: str) -> None:
    try:
        async with system_rls_session() as catalog:
            row = await catalog.get(VodMedia, media_id)
            if row is None:
                return
            await delete_catalog_media(catalog, row)
            await catalog.commit()
    except (VodCatalogError, SQLAlchemyError) as exc:
        logger.warning("Clip lesson video cleanup skipped media=%s: %s", media_id, exc)


async def play_lesson(db: AsyncSession, user: User, lesson_id: str) -> dict[str, object]:
    """Play token for a lesson the caller's organization can see."""
    require_organization_id(user)
    row = await get_visible_lesson(db, lesson_id)
    if row.local_video_key and uses_local_disk():
        return {"mode": "local", "url": f"/api/clip-lessons/{row.id}/video"}
    if not row.vod_media_id:
        raise ClipLessonError("video_missing", 409)
    async with system_rls_session() as catalog:
        media = await catalog.get(VodMedia, row.vod_media_id)
        if media is None or int(media.organization_id) != int(row.organization_id):
            raise ClipLessonError("video_missing", 404)
        try:
            token = issue_play_token(media)
        except VodCatalogError as exc:
            raise ClipLessonError(exc.code, exc.http_status) from exc
    return token


async def delete_lesson(db: AsyncSession, user: User, lesson_id: str) -> None:
    """Owner deletes the lesson, its deck files, and the catalog video."""
    row = await _require_owner(db, user, lesson_id)
    media_id = row.vod_media_id
    deck_key = row.deck_key
    preview_key = row.preview_pdf_key
    video_key = row.local_video_key
    await db.delete(row)
    await db.commit()
    if media_id:
        await _drop_media(media_id)
    for key in (deck_key, preview_key, video_key):
        if not key:
            continue
        try:
            delete_object_key(key)
        except ValueError as exc:
            logger.warning("Clip lesson file cleanup skipped key=%s: %s", key, exc)


async def load_owned(db: AsyncSession, user: User, lesson_id: str) -> ClipLesson:
    """Owner row for deck upload."""
    return await _require_owner(db, user, lesson_id)
