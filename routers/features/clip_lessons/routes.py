"""HTTP API for clip-teaching lessons."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.features.clip_lessons.comments import add_comment, delete_comment, list_comments
from services.features.clip_lessons.deck import DECK_MAX_BYTES, read_preview, run_deck_preview, store_deck
from services.features.clip_lessons.errors import ClipLessonError
from services.features.clip_lessons.lessons import (
    attach_video,
    create_lesson,
    delete_lesson,
    get_lesson_detail,
    get_visible_lesson,
    list_lessons,
    require_organization_id,
    local_video_response_path,
    play_lesson,
    rename_lesson,
    store_local_video,
    replace_chapters,
    set_trim,
    sign_video_upload,
)
from services.features.clip_lessons.rules import ChapterDraft
from utils.auth import get_current_user
from utils.db.session_open import actor_rls_session

router = APIRouter(prefix="/api/clip-lessons", tags=["Clip teaching"])


class CreateBody(BaseModel):
    """New lesson title."""

    title: str = Field(min_length=1, max_length=200)


class RenameBody(BaseModel):
    """Owner rename."""

    title: str = Field(min_length=1, max_length=200)


class TrimBody(BaseModel):
    """Playback window. ``trim_end_ms`` null plays through the end of the file."""

    trim_start_ms: int = Field(ge=0)
    trim_end_ms: Optional[int] = Field(default=None, ge=0)


class ChapterIn(BaseModel):
    """One chapter start."""

    title: str = Field(min_length=1, max_length=80)
    start_ms: int = Field(ge=0)


class ChaptersBody(BaseModel):
    """Full chapter list."""

    chapters: list[ChapterIn] = Field(default_factory=list)


class RegisterBody(BaseModel):
    """Tencent FileId after the browser upload finishes."""

    file_id: str = Field(min_length=1, max_length=64)
    source_context: str = Field(default="", max_length=256)


class CommentBody(BaseModel):
    """Root comment or a reply to a root comment."""

    body: str = Field(min_length=1, max_length=2000)
    parent_id: Optional[int] = None


def _http(exc: ClipLessonError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.code)


@router.get("")
async def list_clip_lessons(user: User = Depends(get_current_user)) -> dict:
    """Lessons in the caller's organization."""
    try:
        async with actor_rls_session(user) as db:
            items = await list_lessons(db, user)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return {"items": items}


@router.post("")
async def create_clip_lesson(body: CreateBody, user: User = Depends(get_current_user)) -> dict:
    """Create an empty lesson."""
    try:
        async with actor_rls_session(user) as db:
            return await create_lesson(db, user, body.title)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.get("/{lesson_id}")
async def read_clip_lesson(lesson_id: str, user: User = Depends(get_current_user)) -> dict:
    """Lesson detail."""
    try:
        async with actor_rls_session(user) as db:
            return await get_lesson_detail(db, user, lesson_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.patch("/{lesson_id}")
async def rename_clip_lesson(
    lesson_id: str,
    body: RenameBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Owner rename."""
    try:
        async with actor_rls_session(user) as db:
            return await rename_lesson(db, user, lesson_id, body.title)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.delete("/{lesson_id}")
async def remove_clip_lesson(lesson_id: str, user: User = Depends(get_current_user)) -> dict:
    """Owner delete."""
    try:
        async with actor_rls_session(user) as db:
            await delete_lesson(db, user, lesson_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return {"ok": True}


@router.put("/{lesson_id}/trim")
async def save_clip_trim(
    lesson_id: str,
    body: TrimBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Save the playback window."""
    try:
        async with actor_rls_session(user) as db:
            return await set_trim(db, user, lesson_id, body.trim_start_ms, body.trim_end_ms)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.put("/{lesson_id}/chapters")
async def save_clip_chapters(
    lesson_id: str,
    body: ChaptersBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Replace timeline chapters."""
    drafts = [ChapterDraft(title=item.title, start_ms=item.start_ms) for item in body.chapters]
    try:
        async with actor_rls_session(user) as db:
            return await replace_chapters(db, user, lesson_id, drafts)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.post("/{lesson_id}/uploads/sign")
async def sign_clip_upload(lesson_id: str, user: User = Depends(get_current_user)) -> dict:
    """Upload signature for the lesson owner."""
    try:
        async with actor_rls_session(user) as db:
            return await sign_video_upload(db, user, lesson_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.post("/{lesson_id}/media")
async def register_clip_media(
    lesson_id: str,
    body: RegisterBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Attach a finished Tencent upload."""
    try:
        async with actor_rls_session(user) as db:
            return await attach_video(db, user, lesson_id, body.file_id, body.source_context)
    except ClipLessonError as exc:
        raise _http(exc) from exc


_VIDEO_READ_CAP = 100 * 1024 * 1024 + 1


@router.post("/{lesson_id}/video")
async def upload_clip_video(
    lesson_id: str,
    user: User = Depends(get_current_user),
    upload: UploadFile = File(...),
) -> dict:
    """Store the clip on this development machine."""
    raw = await upload.read(_VIDEO_READ_CAP)
    try:
        async with actor_rls_session(user) as db:
            return await store_local_video(db, user, lesson_id, upload.filename or "", raw)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.get("/{lesson_id}/video")
async def read_clip_video(lesson_id: str, user: User = Depends(get_current_user)) -> FileResponse:
    """Stream the development-machine clip. The browser sends the session cookie."""
    try:
        require_organization_id(user)
        async with actor_rls_session(user) as db:
            lesson = await get_visible_lesson(db, lesson_id)
            path, media_type = local_video_response_path(lesson)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return FileResponse(path, media_type=media_type)


@router.get("/{lesson_id}/play")
async def play_clip_lesson(lesson_id: str, user: User = Depends(get_current_user)) -> dict:
    """Play token for organization members."""
    try:
        async with actor_rls_session(user) as db:
            return await play_lesson(db, user, lesson_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc


@router.post("/{lesson_id}/deck")
async def upload_clip_deck(
    lesson_id: str,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    upload: UploadFile = File(...),
) -> dict:
    """Store a PPTX and convert it to a preview PDF after the response."""
    raw = await upload.read(DECK_MAX_BYTES + 1)
    filename = upload.filename or ""
    try:
        if len(raw) > DECK_MAX_BYTES:
            raise ClipLessonError("deck_too_large", 413)
        if not filename.lower().endswith(".pptx"):
            raise ClipLessonError("deck_invalid", 400)
        async with actor_rls_session(user) as db:
            stored_id = await store_deck(db, user, lesson_id, raw)
            detail = await get_lesson_detail(db, user, stored_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    background.add_task(run_deck_preview, stored_id)
    return detail


@router.get("/{lesson_id}/deck/preview")
async def read_clip_preview(lesson_id: str, user: User = Depends(get_current_user)) -> Response:
    """PDF bytes for the slide strip."""
    try:
        require_organization_id(user)
        async with actor_rls_session(user) as db:
            lesson = await get_visible_lesson(db, lesson_id)
            data = read_preview(lesson.preview_pdf_key, lesson.preview_status)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return Response(content=data, media_type="application/pdf", headers={"Cache-Control": "no-store"})


@router.get("/{lesson_id}/comments")
async def read_clip_comments(lesson_id: str, user: User = Depends(get_current_user)) -> dict:
    """Comment thread."""
    try:
        async with actor_rls_session(user) as db:
            items = await list_comments(db, user, lesson_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return {"items": items}


@router.post("/{lesson_id}/comments")
async def create_clip_comment(
    lesson_id: str,
    body: CommentBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Add a comment or a reply."""
    try:
        async with actor_rls_session(user) as db:
            items = await add_comment(db, user, lesson_id, body.body, body.parent_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return {"items": items}


@router.delete("/{lesson_id}/comments/{comment_id}")
async def remove_clip_comment(
    lesson_id: str,
    comment_id: int,
    user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete a comment."""
    try:
        async with actor_rls_session(user) as db:
            items = await delete_comment(db, user, lesson_id, comment_id)
    except ClipLessonError as exc:
        raise _http(exc) from exc
    return {"items": items}
