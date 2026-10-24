"""Shared background files for one seminar room.

Bytes go to seminar COS when it is on, and to local disk only when COS is off.
The database row is what every participant lists and downloads. The download
route proxies COS bytes so the room can preview them with fetch().

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabBackgroundFile, MindmateCollabSession
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.seminar_file_storage import (
    delete_seminar_bytes_sync,
    mirror_local_seminar_file_sync,
    put_seminar_bytes_sync,
    read_seminar_bytes_sync,
)
from services.features.workshop_chat.attachment_storage import (
    AttachmentDownload,
    LEGACY_DISK_PREFIX,
    build_logical_key,
    is_legacy_disk_path,
    local_path_for_key,
)
from utils.db.session_open import system_rls_session

STATIC_ROOT = Path(__file__).parent.parent.parent.parent / "static" / "mindmate_seminar"


@dataclass(frozen=True)
class SeminarDownload:
    """Resolved seminar file: local path or COS bytes proxied by the API."""

    content_type: str
    filename: str
    disk_path: Optional[Path] = None
    body: Optional[bytes] = None


MAX_BACKGROUND_BYTES = 20 * 1024 * 1024
MAX_BACKGROUND_FILES = 40
DIAGRAM_REF_TYPE = "application/vnd.mindgraph.diagram-ref"

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".webm": "audio/webm",
    ".weba": "audio/webm",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}


def safe_background_filename(raw: str) -> str:
    """Keep the uploaded basename and drop path pieces."""
    base = Path(raw or "").name.replace("\x00", "").replace("\r", "").replace("\n", "").strip()
    if not base or base in {".", ".."}:
        raise ValueError("file_type")
    if len(base) > 180:
        suffix = Path(base).suffix[:20]
        base = f"{Path(base).stem[: 180 - len(suffix)]}{suffix}"
    return base


def background_content_type(filename: str) -> str:
    """Map an allowed extension to a stored content type."""
    content_type = _CONTENT_TYPES.get(Path(filename).suffix.lower())
    if not content_type:
        raise ValueError("file_type")
    return content_type


async def load_folder_session(user: User, session_id: str) -> MindmateCollabSession:
    """Return the live seminar when this person may use its shared folder."""
    manager = get_mindmate_collab_manager()
    session = await manager.load_session_by_id(session_id)
    if session is None:
        raise ValueError("room_not_found")
    if not await manager.user_may_connect(int(user.id), session):
        raise ValueError("forbidden")
    return session


def _file_payload(row: MindmateCollabBackgroundFile, uploader_name: str) -> dict[str, object]:
    return {
        "id": row.id,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "uploader_name": uploader_name,
        "pinned": bool(row.pinned),
        "pinned_at": row.pinned_at.isoformat() if row.pinned_at else None,
        "artifact": bool(row.artifact),
        "listed": bool(row.listed),
        "source_message_id": row.source_message_id,
        "diagram_id": row.diagram_id,
        "created_at": row.created_at.isoformat(),
    }


async def get_background_file(session_id: str, file_id: str) -> Optional[dict[str, object]]:
    """Return one seminar file, including chat attachments that stay out of the folder."""
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            return None
        names = await _uploader_names(db, [row.uploader_user_id])
        return _file_payload(row, names.get(row.uploader_user_id, ""))


async def list_background_files(session_id: str) -> list[dict[str, object]]:
    """Pinned files first, then newest shared files."""
    async with system_rls_session() as db:
        result = await db.execute(
            select(MindmateCollabBackgroundFile)
            .where(
                MindmateCollabBackgroundFile.session_id == session_id,
                MindmateCollabBackgroundFile.listed.is_(True),
            )
            .order_by(
                MindmateCollabBackgroundFile.pinned.desc(),
                MindmateCollabBackgroundFile.pinned_at.desc().nulls_last(),
                MindmateCollabBackgroundFile.created_at.desc(),
            )
        )
        rows = list(result.scalars().all())
        names = await _uploader_names(db, [row.uploader_user_id for row in rows])
        payloads = [_file_payload(row, names.get(row.uploader_user_id, "")) for row in rows]
        copies = [(row.storage_key, row.content_type) for row in rows]
    await _mirror_local_copies(copies)
    return payloads


async def _uploader_names(db: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    unique = {int(user_id) for user_id in user_ids}
    if not unique:
        return {}
    result = await db.execute(select(User.id, User.name).where(User.id.in_(unique)))
    return {int(row.id): (row.name or "") for row in result.all()}


async def find_reply_artifact(session_id: str, message_id: int) -> Optional[dict[str, object]]:
    """Return the Word artifact already saved for one assistant message."""
    async with system_rls_session() as db:
        result = await db.execute(
            select(MindmateCollabBackgroundFile).where(
                MindmateCollabBackgroundFile.session_id == session_id,
                MindmateCollabBackgroundFile.source_message_id == message_id,
                MindmateCollabBackgroundFile.artifact.is_(True),
            )
        )
        row = result.scalars().first()
        if row is None:
            return None
        names = await _uploader_names(db, [row.uploader_user_id])
        return _file_payload(row, names.get(row.uploader_user_id, ""))


async def list_reply_artifacts(session_id: str) -> list[dict[str, object]]:
    """Newest seminar Word artifacts first."""
    async with system_rls_session() as db:
        result = await db.execute(
            select(MindmateCollabBackgroundFile)
            .where(
                MindmateCollabBackgroundFile.session_id == session_id,
                MindmateCollabBackgroundFile.artifact.is_(True),
            )
            .order_by(MindmateCollabBackgroundFile.created_at.desc())
        )
        rows = list(result.scalars().all())
        names = await _uploader_names(db, [row.uploader_user_id for row in rows])
        payloads = [_file_payload(row, names.get(row.uploader_user_id, "")) for row in rows]
        copies = [(row.storage_key, row.content_type) for row in rows]
    await _mirror_local_copies(copies)
    return payloads


async def _mirror_local_copies(copies: list[tuple[str, str]]) -> None:
    """Copy seminar files that still exist only on this host up to COS."""
    for storage_key, content_type in copies:
        disk = seminar_disk_path(storage_key)
        if disk is None or not disk.is_file():
            continue
        await asyncio.to_thread(
            mirror_local_seminar_file_sync,
            storage_key,
            disk,
            content_type=content_type,
        )


async def save_generated_background_file(
    session: MindmateCollabSession,
    *,
    uploader_user_id: int,
    uploader_name: str,
    filename: str,
    data: bytes,
    source_message_id: int,
) -> dict[str, object]:
    """Store a generated Word file as a seminar artifact, not a folder upload."""
    if not data or len(data) > MAX_BACKGROUND_BYTES:
        raise ValueError("file_too_large" if data else "file_type")
    safe_name = safe_background_filename(filename)
    content_type = background_content_type(safe_name)
    async with system_rls_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(MindmateCollabBackgroundFile)
            .where(
                MindmateCollabBackgroundFile.session_id == session.id,
                MindmateCollabBackgroundFile.artifact.is_(True),
            )
        )
    if int(count or 0) >= MAX_BACKGROUND_FILES:
        raise ValueError("file_limit")
    storage_key = await store_background_bytes(safe_name, data, content_type)
    row = MindmateCollabBackgroundFile(
        id=str(uuid4()),
        session_id=session.id,
        uploader_user_id=uploader_user_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        listed=False,
        artifact=True,
        source_message_id=source_message_id,
        created_at=datetime.now(tz=UTC),
    )
    try:
        async with system_rls_session() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return _file_payload(row, uploader_name)
    except IntegrityError:
        existing = await find_reply_artifact(session.id, source_message_id)
        if existing is not None:
            return existing
        raise


async def store_background_bytes(filename: str, data: bytes, content_type: str) -> str:
    """Store seminar bytes on COS, or on local disk when COS is off."""
    logical_key = build_logical_key(filename)
    return await asyncio.to_thread(
        put_seminar_bytes_sync,
        logical_key,
        data,
        content_type,
        STATIC_ROOT,
    )


async def save_background_file(
    session: MindmateCollabSession,
    user: User,
    upload: UploadFile,
    *,
    listed: bool = True,
) -> dict[str, object]:
    """Store one seminar file.

    ``listed`` files appear in the shared folder. Chat drops stay unlisted
    and travel with the message instead.
    """
    filename = safe_background_filename(upload.filename or "")
    content_type = background_content_type(filename)
    data = await upload.read(MAX_BACKGROUND_BYTES + 1)
    if not data:
        raise ValueError("file_type")
    if len(data) > MAX_BACKGROUND_BYTES:
        raise ValueError("file_too_large")
    async with system_rls_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(MindmateCollabBackgroundFile)
            .where(
                MindmateCollabBackgroundFile.session_id == session.id,
                MindmateCollabBackgroundFile.listed.is_(True),
            )
        )
    if listed and int(count or 0) >= MAX_BACKGROUND_FILES:
        raise ValueError("file_limit")
    storage_key = await store_background_bytes(filename, data, content_type)
    async with system_rls_session() as db:
        row = MindmateCollabBackgroundFile(
            id=str(uuid4()),
            session_id=session.id,
            uploader_user_id=user.id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            storage_key=storage_key,
            listed=listed,
            created_at=datetime.now(tz=UTC),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _file_payload(row, user.name or "")


def seminar_disk_path(storage_key: str) -> Optional[Path]:
    """Map a seminar storage key onto the local static tree."""
    try:
        if is_legacy_disk_path(storage_key):
            relative = storage_key[len(LEGACY_DISK_PREFIX) :]
            return local_path_for_key(relative, STATIC_ROOT)
        return local_path_for_key(storage_key, STATIC_ROOT)
    except ValueError:
        return None


def local_seminar_attachment(
    storage_key: str,
    content_type: str,
    filename: str,
) -> Optional[AttachmentDownload]:
    """Return the on-disk seminar file when a local copy exists."""
    disk = seminar_disk_path(storage_key)
    if disk is None or not disk.is_file():
        return None
    return AttachmentDownload(
        content_type=content_type,
        filename=filename,
        disk_path=disk,
    )


async def resolve_background_download(session_id: str, file_id: str) -> Optional[SeminarDownload]:
    """Resolve one shared file after the caller has already passed the room check."""
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            return None
        stored = row.storage_key
        content_type = row.content_type
        filename = row.filename
    local = local_seminar_attachment(stored, content_type, filename)
    if local is not None and local.disk_path is not None:
        await asyncio.to_thread(
            mirror_local_seminar_file_sync,
            stored,
            local.disk_path,
            content_type=content_type,
        )
        return SeminarDownload(
            content_type=content_type,
            filename=filename,
            disk_path=local.disk_path,
        )
    body = await asyncio.to_thread(
        read_seminar_bytes_sync,
        stored,
        max_bytes=MAX_BACKGROUND_BYTES,
    )
    if body is None:
        return None
    return SeminarDownload(
        content_type=content_type,
        filename=filename,
        body=body,
    )


async def rename_background_file(
    session_id: str,
    file_id: str,
    filename: str,
) -> dict[str, object]:
    """Rename a shared file; extension must stay the same family."""
    clean = safe_background_filename(filename)
    new_type = background_content_type(clean)
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        old_ext = Path(row.filename).suffix.lower()
        new_ext = Path(clean).suffix.lower()
        if old_ext != new_ext:
            raise ValueError("file_type")
        row.filename = clean
        row.content_type = new_type
        await db.commit()
        await db.refresh(row)
        names = await _uploader_names(db, [row.uploader_user_id])
        return _file_payload(row, names.get(row.uploader_user_id, ""))


async def set_background_file_pinned(
    session_id: str,
    file_id: str,
    pinned: bool,
) -> dict[str, object]:
    """Pin or unpin a shared file at the top of the folder list."""
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        row.pinned = bool(pinned)
        row.pinned_at = datetime.now(tz=UTC) if pinned else None
        await db.commit()
        await db.refresh(row)
        names = await _uploader_names(db, [row.uploader_user_id])
        return _file_payload(row, names.get(row.uploader_user_id, ""))


async def delete_background_file(session_id: str, file_id: str) -> dict[str, Any] | None:
    """Remove the DB row and the COS or local bytes.

    Returns a small payload when the row was on the resource or artifact shelf,
    so the room can announce the removal. Chat-only attachments stay quiet.
    """
    notice: dict[str, Any] | None = None
    async with system_rls_session() as db:
        row = await db.get(MindmateCollabBackgroundFile, file_id)
        if row is None or row.session_id != session_id:
            raise ValueError("room_not_found")
        storage_key = row.storage_key
        if row.artifact:
            shelf = "artifact"
        elif row.listed:
            shelf = "resource"
        else:
            shelf = ""
        if shelf:
            notice = {
                "id": row.id,
                "filename": row.filename,
                "artifact": bool(row.artifact),
                "listed": bool(row.listed),
                "shelf": shelf,
            }
        await db.delete(row)
        await db.commit()
    await asyncio.to_thread(delete_seminar_bytes_sync, storage_key, STATIC_ROOT)
    return notice
