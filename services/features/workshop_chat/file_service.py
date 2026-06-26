"""
File Service
==============

File upload and attachment operations for workshop chat.

Files are stored under ``static/chat/<year>/<month>/`` with a UUID prefix.
Clients fetch bytes via authenticated ``/api/chat/attachments/{id}/download``;
direct ``/static/chat/`` URLs are blocked by middleware.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.workshop_chat import (
    ChannelMember,
    ChatMessage,
    DirectMessage,
    FileAttachment,
)
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)

STATIC_ROOT = Path(__file__).parent.parent.parent.parent / "static" / "chat"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


def attachment_download_url(attachment_id: int) -> str:
    """Authenticated download URL exposed to clients (not the on-disk static path)."""
    return f"/api/chat/attachments/{attachment_id}/download"


def _safe_upload_basename(filename: str) -> str:
    base = Path(filename).name.strip()
    if not base or base in (".", ".."):
        raise ValueError("Invalid filename")
    return base


def _disk_path_for_stored_url(stored_path: str) -> Path:
    """Map DB ``/static/chat/...`` path to absolute file on disk."""
    prefix = "/static/chat/"
    if not stored_path.startswith(prefix):
        raise ValueError("Invalid attachment path")
    relative = stored_path[len(prefix) :]
    candidate = (STATIC_ROOT / relative).resolve()
    root_resolved = STATIC_ROOT.resolve()
    if not candidate.is_relative_to(root_resolved):
        raise ValueError("Invalid attachment path")
    return candidate


def _format_attachment(att: FileAttachment) -> Dict[str, Any]:
    """Serialize a FileAttachment ORM object to a response dict."""
    return {
        "id": att.id,
        "message_id": att.message_id,
        "dm_id": att.dm_id,
        "uploader_id": att.uploader_id,
        "filename": att.filename,
        "content_type": att.content_type,
        "file_size": att.file_size,
        "file_path": attachment_download_url(att.id),
        "created_at": att.created_at.isoformat(),
    }


async def _user_is_channel_member(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
) -> bool:
    row = await db.execute(
        select(ChannelMember.id).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def _verify_attachment_link(
    db: AsyncSession,
    user_id: int,
    message_id: Optional[int],
    dm_id: Optional[int],
) -> None:
    """Ensure the uploader may associate an upload with the given message or DM."""
    if message_id is not None and dm_id is not None:
        raise ValueError("Specify message_id or dm_id, not both")
    if message_id is not None:
        row = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
        msg = row.scalar_one_or_none()
        if msg is None:
            raise ValueError("Message not found")
        if not await _user_is_channel_member(db, msg.channel_id, user_id):
            raise ValueError("Not a member of this channel")
        return
    if dm_id is not None:
        row = await db.execute(select(DirectMessage).where(DirectMessage.id == dm_id))
        dm = row.scalar_one_or_none()
        if dm is None:
            raise ValueError("Direct message not found")
        if user_id not in (dm.sender_id, dm.recipient_id):
            raise ValueError("Not a participant in this conversation")


async def user_can_access_attachment(
    db: AsyncSession,
    user_id: int,
    att: FileAttachment,
) -> bool:
    """Return True when the user may read attachment metadata or bytes."""
    if att.message_id is not None:
        row = await db.execute(select(ChatMessage).where(ChatMessage.id == att.message_id))
        msg = row.scalar_one_or_none()
        if msg is None:
            return att.uploader_id == user_id
        return await _user_is_channel_member(db, msg.channel_id, user_id)
    if att.dm_id is not None:
        row = await db.execute(select(DirectMessage).where(DirectMessage.id == att.dm_id))
        dm = row.scalar_one_or_none()
        if dm is None:
            return att.uploader_id == user_id
        return user_id in (dm.sender_id, dm.recipient_id)
    return att.uploader_id == user_id


class FileService:
    """File upload and attachment operations."""

    @staticmethod
    async def save_attachment(
        db: AsyncSession,
        file: UploadFile,
        uploader_id: int,
        message_id: Optional[int] = None,
        dm_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Validate, persist to disk, and create a DB record.

        Raises ``ValueError`` on validation failure.
        """
        if not file.filename:
            raise ValueError("Filename is required")

        await _verify_attachment_link(db, uploader_id, message_id, dm_id)

        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported file type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )

        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File too large ({len(data)} bytes). Max {MAX_FILE_SIZE} bytes.")

        basename = _safe_upload_basename(file.filename)

        now = datetime.now(UTC)
        sub_dir = STATIC_ROOT / str(now.year) / f"{now.month:02d}"
        sub_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex[:12]}_{basename}"
        disk_path = sub_dir / safe_name
        root_resolved = STATIC_ROOT.resolve()
        resolved = disk_path.resolve()
        if not resolved.is_relative_to(root_resolved):
            raise ValueError("Invalid filename")

        resolved.write_bytes(data)

        relative_path = f"/static/chat/{now.year}/{now.month:02d}/{safe_name}"

        attachment = FileAttachment(
            message_id=message_id,
            dm_id=dm_id,
            uploader_id=uploader_id,
            filename=basename,
            content_type=content_type,
            file_size=len(data),
            file_path=relative_path,
        )
        db.add(attachment)
        try:
            await db.commit()
            await db.refresh(attachment)
        except DATABASE_ERRORS:
            await db.rollback()
            raise

        return _format_attachment(attachment)

    @staticmethod
    async def get_message_attachments(
        db: AsyncSession,
        message_id: int,
    ) -> List[Dict[str, Any]]:
        """List attachments for a channel/topic message."""
        result = await db.execute(
            select(FileAttachment).where(FileAttachment.message_id == message_id).order_by(FileAttachment.created_at)
        )
        rows = result.scalars().all()
        return [_format_attachment(a) for a in rows]

    @staticmethod
    async def get_dm_attachments(
        db: AsyncSession,
        dm_id: int,
    ) -> List[Dict[str, Any]]:
        """List attachments for a direct message."""
        result = await db.execute(
            select(FileAttachment).where(FileAttachment.dm_id == dm_id).order_by(FileAttachment.created_at)
        )
        rows = result.scalars().all()
        return [_format_attachment(a) for a in rows]

    @staticmethod
    async def get_attachments_batch(
        db: AsyncSession,
        message_ids: List[int],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Batch-fetch attachments keyed by message_id."""
        if not message_ids:
            return {}
        result = await db.execute(
            select(FileAttachment).where(FileAttachment.message_id.in_(message_ids)).order_by(FileAttachment.created_at)
        )
        rows = result.scalars().all()
        batch_result: Dict[int, List[Dict[str, Any]]] = {}
        for att in rows:
            if att.message_id is not None:
                batch_result.setdefault(att.message_id, []).append(_format_attachment(att))
        return batch_result

    @staticmethod
    async def get_attachment_row(
        db: AsyncSession,
        attachment_id: int,
    ) -> Optional[FileAttachment]:
        """Load attachment ORM row by id."""
        result = await db.execute(select(FileAttachment).where(FileAttachment.id == attachment_id))
        return result.scalars().first()

    @staticmethod
    async def get_attachment(
        db: AsyncSession,
        attachment_id: int,
        *,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get attachment metadata when the user is allowed to access it."""
        att = await FileService.get_attachment_row(db, attachment_id)
        if att is None:
            return None
        if not await user_can_access_attachment(db, user_id, att):
            return None
        return _format_attachment(att)

    @staticmethod
    async def resolve_download(
        db: AsyncSession,
        attachment_id: int,
        user_id: int,
    ) -> Optional[Tuple[Path, str, str]]:
        """Return (disk_path, content_type, download_filename) when access is allowed."""
        att = await FileService.get_attachment_row(db, attachment_id)
        if att is None:
            return None
        if not await user_can_access_attachment(db, user_id, att):
            return None
        try:
            disk_path = _disk_path_for_stored_url(att.file_path)
        except ValueError:
            logger.warning("Attachment %s has invalid stored path: %s", att.id, att.file_path)
            return None
        if not disk_path.is_file():
            logger.warning("Attachment %s file missing on disk: %s", att.id, disk_path)
            return None
        return disk_path, att.content_type, att.filename


file_service = FileService()
