"""Pure checks for trim, chapters, and comment replies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from services.features.clip_lessons.errors import ClipLessonError

MAX_CHAPTERS = 40
MAX_CHAPTER_TITLE = 80
MAX_COMMENT_BODY = 2000
MAX_LESSON_TITLE = 200


@dataclass(frozen=True)
class ChapterDraft:
    """One chapter start the owner wants to save."""

    title: str
    start_ms: int


def parse_lesson_id(value: str) -> str:
    """Return a canonical lesson id, or reject a value that is not a UUID."""
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ClipLessonError("not_found", 404) from exc


def validate_trim(start_ms: int, end_ms: int | None) -> tuple[int, int | None]:
    """Accept a playback window. ``end_ms`` None means through the end of the file."""
    if start_ms < 0 or (end_ms is not None and end_ms <= start_ms):
        raise ClipLessonError("trim_invalid", 400)
    return start_ms, end_ms


def chapter_in_window(start_ms: int, trim_start: int, trim_end: int | None) -> bool:
    """True when the chapter start sits inside the saved trim."""
    if start_ms < trim_start:
        return False
    if trim_end is not None and start_ms >= trim_end:
        return False
    return True


def normalize_chapters(
    drafts: list[ChapterDraft],
    trim_start: int,
    trim_end: int | None,
) -> list[ChapterDraft]:
    """Validate and order chapter starts. Reject duplicates and points outside the trim."""
    if len(drafts) > MAX_CHAPTERS:
        raise ClipLessonError("chapter_invalid", 400)
    seen: set[int] = set()
    cleaned: list[ChapterDraft] = []
    for draft in drafts:
        title = draft.title.strip()
        if not title or len(title) > MAX_CHAPTER_TITLE or draft.start_ms < 0:
            raise ClipLessonError("chapter_invalid", 400)
        if draft.start_ms in seen or not chapter_in_window(draft.start_ms, trim_start, trim_end):
            raise ClipLessonError("chapter_invalid", 400)
        seen.add(draft.start_ms)
        cleaned.append(ChapterDraft(title=title, start_ms=draft.start_ms))
    cleaned.sort(key=lambda row: row.start_ms)
    return cleaned


def drop_chapters_outside(
    drafts: list[ChapterDraft],
    trim_start: int,
    trim_end: int | None,
) -> list[ChapterDraft]:
    """Keep chapters that still sit inside a newly saved trim."""
    kept = [row for row in drafts if chapter_in_window(row.start_ms, trim_start, trim_end)]
    kept.sort(key=lambda row: row.start_ms)
    return kept


def normalize_title(value: str) -> str:
    """Trim a lesson title down to the column width."""
    title = value.strip()
    if not title or len(title) > MAX_LESSON_TITLE:
        raise ClipLessonError("title_invalid", 400)
    return title


def normalize_comment_body(value: str) -> str:
    """Reject an empty or oversized comment."""
    body = value.strip()
    if not body or len(body) > MAX_COMMENT_BODY:
        raise ClipLessonError("comment_invalid", 400)
    return body


def assert_reply_target(
    *,
    parent_lesson_id: str,
    lesson_id: str,
    parent_parent_id: int | None,
    parent_deleted: bool,
) -> None:
    """Allow a reply only to a live root comment on the same lesson."""
    if parent_deleted or parent_lesson_id != lesson_id:
        raise ClipLessonError("parent_not_found", 404)
    if parent_parent_id is not None:
        raise ClipLessonError("reply_depth", 400)


def can_edit_lesson(user_id: int, owner_id: int) -> bool:
    """True when this user owns the lesson."""
    return user_id == owner_id


def can_delete_comment(user_id: int, owner_id: int, author_id: int) -> bool:
    """The author and the lesson owner may remove a comment."""
    return user_id in {author_id, owner_id}
