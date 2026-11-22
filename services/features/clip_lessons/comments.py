"""Organization comment threads on a clip lesson."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.clip_lesson import ClipLessonComment
from services.features.clip_lessons.errors import ClipLessonError
from services.features.clip_lessons.lessons import display_name, get_visible_lesson, require_organization_id
from services.features.clip_lessons.rules import assert_reply_target, can_delete_comment, normalize_comment_body
from services.features.clip_lessons.serialize import comment_payload


async def list_comments(db: AsyncSession, user: User, lesson_id: str) -> list[dict[str, object]]:
    """Root comments newest first, each with replies oldest first."""
    require_organization_id(user)
    lesson = await get_visible_lesson(db, lesson_id)
    result = await db.scalars(
        select(ClipLessonComment)
        .where(ClipLessonComment.lesson_id == lesson.id, ClipLessonComment.is_deleted.is_(False))
        .order_by(ClipLessonComment.created_at.asc())
    )
    rows = list(result.all())
    names: dict[int, str] = {}
    for row in rows:
        if row.user_id not in names:
            names[row.user_id] = await display_name(db, int(row.user_id))
    replies: dict[int, list[ClipLessonComment]] = {}
    roots: list[ClipLessonComment] = []
    for row in rows:
        if row.parent_id is None:
            roots.append(row)
            continue
        replies.setdefault(int(row.parent_id), []).append(row)
    roots.reverse()
    viewer = int(user.id)
    owner = int(lesson.owner_id)
    payload: list[dict[str, object]] = []
    for root in roots:
        nested = [
            comment_payload(
                reply,
                author_name=names.get(int(reply.user_id), ""),
                replies=[],
                can_delete=can_delete_comment(viewer, owner, int(reply.user_id)),
            )
            for reply in replies.get(int(root.id), [])
        ]
        payload.append(
            comment_payload(
                root,
                author_name=names.get(int(root.user_id), ""),
                replies=nested,
                can_delete=can_delete_comment(viewer, owner, int(root.user_id)),
            )
        )
    return payload


async def add_comment(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    body: str,
    parent_id: int | None,
) -> list[dict[str, object]]:
    """Post a root comment or a single-level reply."""
    require_organization_id(user)
    lesson = await get_visible_lesson(db, lesson_id)
    text = normalize_comment_body(body)
    if parent_id is not None:
        parent = await db.get(ClipLessonComment, parent_id)
        if parent is None:
            raise ClipLessonError("parent_not_found", 404)
        assert_reply_target(
            parent_lesson_id=parent.lesson_id,
            lesson_id=lesson.id,
            parent_parent_id=parent.parent_id,
            parent_deleted=bool(parent.is_deleted),
        )
    row = ClipLessonComment(
        lesson_id=lesson.id,
        user_id=int(user.id),
        parent_id=parent_id,
        body=text,
        is_deleted=False,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    return await list_comments(db, user, lesson.id)


async def delete_comment(db: AsyncSession, user: User, lesson_id: str, comment_id: int) -> list[dict[str, object]]:
    """Soft-delete a comment the author or the lesson owner may remove."""
    require_organization_id(user)
    lesson = await get_visible_lesson(db, lesson_id)
    row = await db.get(ClipLessonComment, comment_id)
    if row is None or row.lesson_id != lesson.id or row.is_deleted:
        raise ClipLessonError("not_found", 404)
    if not can_delete_comment(int(user.id), int(lesson.owner_id), int(row.user_id)):
        raise ClipLessonError("forbidden", 403)
    row.is_deleted = True
    await db.commit()
    return await list_comments(db, user, lesson.id)
