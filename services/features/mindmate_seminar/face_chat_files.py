"""Live face-to-face notes stored as one seminar artifact.

Each save overwrites the same COS object. The database row is created once
and then only its size changes, so the 面聊文档 list does not grow per chunk.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarBackgroundFile, MindmateSeminarSession
from services.features.mindmate_seminar.background_files import (
    MAX_BACKGROUND_BYTES,
    MAX_BACKGROUND_FILES,
    STATIC_ROOT,
    get_background_file,
    safe_background_filename,
)
from services.features.mindmate_seminar.redis_keys import face_chat_lock_key
from services.features.mindmate_seminar.seminar_file_storage import put_seminar_bytes_sync
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from services.features.workshop_chat.attachment_storage import build_logical_key
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import system_rls_session

FACE_CHAT_KIND = "face_chat"
FACE_CHAT_LOCK_TTL_SEC = 120
_MAX_CHARS = 400_000
_MARKDOWN_TYPE = "text/plain"


def parse_face_chat_lock(raw: object) -> tuple[int, str, str] | None:
    """Return ``(user id, client token, file id)`` for one lock value."""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", "replace")
    elif isinstance(raw, str):
        text = raw
    else:
        return None
    user_text, sep, rest = text.partition("|")
    if not sep or not user_text.isdigit():
        return None
    token, _, file_id = rest.partition("|")
    token = token.strip()
    if not token:
        return None
    return int(user_text), token, file_id


def face_chat_lock_decision(
    holder: tuple[int, str, str] | None,
    user_id: int,
    token: str,
    *,
    refresh: bool,
) -> str:
    """``acquire`` a free lock, ``refresh`` the same recorder, or ``busy``."""
    if holder is None:
        return "busy" if refresh else "acquire"
    holder_user, holder_token, _file_id = holder
    if holder_user == user_id and holder_token == token:
        return "refresh"
    return "busy"


def _lock_text(user_id: int, token: str, file_id: str = "") -> str:
    return f"{int(user_id)}|{token}|{file_id}"


def _lock_prefix(user_id: int, token: str) -> str:
    return f"{int(user_id)}|{token}|"


_TOUCH_LOCK_LUA = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
if string.sub(raw, 1, #ARGV[1]) ~= ARGV[1] then
  return 0
end
local file_id = ARGV[2]
if file_id == '' then
  file_id = string.sub(raw, #ARGV[1] + 1)
end
redis.call('SET', KEYS[1], ARGV[1] .. file_id, 'EX', ARGV[3])
return 1
"""

_RELEASE_LOCK_LUA = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
if string.sub(raw, 1, #ARGV[1]) ~= ARGV[1] then
  return 0
end
return redis.call('DEL', KEYS[1])
"""


async def _touch_face_chat_lock(code: str, user_id: int, token: str, file_id: str) -> bool:
    redis = get_async_redis()
    try:
        touched = await redis.eval(
            _TOUCH_LOCK_LUA,
            1,
            face_chat_lock_key(code),
            _lock_prefix(user_id, token),
            file_id,
            str(FACE_CHAT_LOCK_TTL_SEC),
        )
    except REDIS_ERRORS:
        return False
    return bool(touched)


async def hold_face_chat_lock(code: str, user_id: int, token: str, *, refresh: bool) -> bool:
    """Keep the single-recorder lock for this client token."""
    cleaned = token.strip()
    if not cleaned:
        return False
    if not refresh:
        redis = get_async_redis()
        try:
            acquired = await redis.set(
                face_chat_lock_key(code),
                _lock_text(user_id, cleaned),
                nx=True,
                ex=FACE_CHAT_LOCK_TTL_SEC,
            )
        except REDIS_ERRORS:
            return False
        if acquired:
            return True
    return await _touch_face_chat_lock(code, user_id, cleaned, "")


async def remember_face_chat_file(code: str, user_id: int, token: str, file_id: str) -> None:
    """Attach the notes file to the recorder lock and extend its TTL."""
    cleaned = token.strip()
    if not cleaned or not file_id:
        return
    await _touch_face_chat_lock(code, user_id, cleaned, file_id)


async def face_chat_locked_file_id(code: str, user_id: int, token: str) -> str:
    """Return the notes file already bound to this recorder, if any."""
    cleaned = token.strip()
    if not cleaned:
        return ""
    redis = get_async_redis()
    try:
        holder = parse_face_chat_lock(await redis.get(face_chat_lock_key(code)))
    except REDIS_ERRORS:
        return ""
    if holder is None:
        return ""
    if face_chat_lock_decision(holder, user_id, cleaned, refresh=True) != "refresh":
        return ""
    return holder[2]


async def release_face_chat_lock(code: str, user_id: int, token: str) -> None:
    """Drop the lock when this recorder stops. Another token is left alone."""
    cleaned = token.strip()
    if not cleaned:
        return
    redis = get_async_redis()
    try:
        await redis.eval(
            _RELEASE_LOCK_LUA,
            1,
            face_chat_lock_key(code),
            _lock_prefix(user_id, cleaned),
        )
    except REDIS_ERRORS:
        return


def normalize_face_chat_filename(raw: str) -> str:
    """Keep a markdown basename for the archived notes."""
    name = safe_background_filename((raw or "").strip() or "face-chat.md")
    if Path(name).suffix.lower() != ".md":
        name = safe_background_filename(f"{Path(name).stem}.md")
    return name


def face_chat_body(content: str) -> bytes:
    """UTF-8 bytes for one notes snapshot. Empty text is rejected."""
    text = (content or "").replace("\x00", "").strip()
    if not text:
        raise ValueError("empty_reply")
    if len(text) > _MAX_CHARS:
        raise ValueError("file_too_large")
    data = text.encode("utf-8")
    if len(data) > MAX_BACKGROUND_BYTES:
        raise ValueError("file_too_large")
    return data


async def upsert_face_chat_document(
    session: MindmateSeminarSession,
    user: User,
    *,
    content: str,
    filename: str = "",
    file_id: str = "",
    token: str = "",
) -> dict[str, object]:
    """Create or overwrite the recorder's markdown artifact and tell the room."""
    data = face_chat_body(content)
    user_id = int(user.id)
    requested = file_id.strip()
    target = requested
    if not target:
        if not await hold_face_chat_lock(session.code, user_id, token, refresh=False):
            raise ValueError("face_chat_busy")
        target = await face_chat_locked_file_id(session.code, user_id, token)
    saved_id = ""
    if target:
        try:
            saved_id = await _replace_face_chat(session.id, user_id, target, data)
        except ValueError as exc:
            if requested or str(exc) != "file_missing":
                raise
    if not saved_id:
        saved_id = await _create_face_chat(
            session.id,
            user_id,
            normalize_face_chat_filename(filename),
            data,
        )
    await remember_face_chat_file(session.code, user_id, token, saved_id)
    saved = await get_background_file(session.id, saved_id)
    if saved is None:
        raise ValueError("upload_failed")
    await broadcast_to_all(session.code, {"type": "seminar_artifact", "file": saved})
    return saved


async def _replace_face_chat(session_id: str, user_id: int, file_id: str, data: bytes) -> str:
    async with system_rls_session() as db:
        row = await db.get(MindmateSeminarBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("file_missing")
        if row.kind != FACE_CHAT_KIND or int(row.uploader_user_id) != user_id:
            raise ValueError("forbidden")
        storage_key = row.storage_key
        content_type = row.content_type or _MARKDOWN_TYPE
    await asyncio.to_thread(
        put_seminar_bytes_sync,
        storage_key,
        data,
        content_type,
        STATIC_ROOT,
    )
    async with system_rls_session() as db:
        row = await db.get(MindmateSeminarBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("file_missing")
        row.size_bytes = len(data)
        await db.commit()
    return file_id


async def _create_face_chat(session_id: str, user_id: int, filename: str, data: bytes) -> str:
    async with system_rls_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(MindmateSeminarBackgroundFile)
            .where(
                MindmateSeminarBackgroundFile.session_id == session_id,
                MindmateSeminarBackgroundFile.artifact.is_(True),
            )
        )
    if int(count or 0) >= MAX_BACKGROUND_FILES:
        raise ValueError("file_limit")
    storage_key = await asyncio.to_thread(
        put_seminar_bytes_sync,
        build_logical_key(filename),
        data,
        _MARKDOWN_TYPE,
        STATIC_ROOT,
    )
    row_id = str(uuid4())
    row = MindmateSeminarBackgroundFile(
        id=row_id,
        session_id=session_id,
        uploader_user_id=user_id,
        filename=filename,
        content_type=_MARKDOWN_TYPE,
        size_bytes=len(data),
        storage_key=storage_key,
        listed=False,
        artifact=True,
        kind=FACE_CHAT_KIND,
        created_at=datetime.now(tz=UTC),
    )
    async with system_rls_session() as db:
        db.add(row)
        await db.commit()
    return row_id
