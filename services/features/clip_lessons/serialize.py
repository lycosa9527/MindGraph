"""JSON shapes for clip-teaching lessons and comments."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.domain.clip_lesson import ClipLesson, ClipLessonChapter, ClipLessonComment


def iso(value: datetime | None) -> str | None:
    """ISO-8601 timestamp, or None."""
    if value is None:
        return None
    return value.isoformat()


def chapter_payload(row: ClipLessonChapter) -> dict[str, object]:
    """One timeline chapter."""
    return {"id": row.id, "title": row.title, "start_ms": row.start_ms}


def lesson_payload(
    row: ClipLesson,
    *,
    owner_name: str,
    viewer_id: int,
    chapters: list[ClipLessonChapter],
    video_status: Optional[str],
    duration_ms: Optional[int],
    video_storage: str,
) -> dict[str, object]:
    """Lesson detail, including chapters and the saved trim."""
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "owner_id": row.owner_id,
        "owner_name": owner_name,
        "is_owner": row.owner_id == viewer_id,
        "title": row.title,
        "vod_media_id": row.vod_media_id,
        "has_video": bool(row.vod_media_id or row.local_video_key),
        "video_storage": video_storage,
        "video_status": video_status,
        "duration_ms": duration_ms,
        "trim_start_ms": row.trim_start_ms,
        "trim_end_ms": row.trim_end_ms,
        "preview_status": row.preview_status,
        "has_deck": bool(row.deck_key),
        "chapters": [chapter_payload(chapter) for chapter in chapters],
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


def lesson_summary(row: ClipLesson, *, owner_name: str, viewer_id: int) -> dict[str, object]:
    """List card."""
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "owner_name": owner_name,
        "is_owner": row.owner_id == viewer_id,
        "title": row.title,
        "has_video": bool(row.vod_media_id or row.local_video_key),
        "preview_status": row.preview_status,
        "updated_at": iso(row.updated_at),
    }


def comment_payload(
    row: ClipLessonComment,
    *,
    author_name: str,
    replies: list[dict[str, object]],
    can_delete: bool,
) -> dict[str, object]:
    """One root comment and its replies."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "author_name": author_name,
        "body": row.body,
        "created_at": iso(row.created_at),
        "can_delete": can_delete,
        "replies": replies,
    }
