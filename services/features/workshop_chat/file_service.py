"""
File Service
==============

File upload and attachment operations for workshop chat.

Files are stored under ``static/chat/<year>/<month>/`` with a UUID prefix
to avoid collisions.  The existing ``/static`` mount serves them.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from models.domain.workshop_chat import FileAttachment

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
        "file_path": att.file_path,
        "created_at": att.created_at.isoformat(),
    }


class FileService:
    """File upload and attachment operations."""

    @staticmethod
    async def save_attachment(
        db: Session,
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

        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported file type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )

        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File too large ({len(data)} bytes). Max {MAX_FILE_SIZE} bytes.")

        now = datetime.utcnow()
        sub_dir = STATIC_ROOT / str(now.year) / f"{now.month:02d}"
        sub_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        disk_path = sub_dir / safe_name
        disk_path.write_bytes(data)

        relative_path = f"/static/chat/{now.year}/{now.month:02d}/{safe_name}"

        attachment = FileAttachment(
            message_id=message_id,
            dm_id=dm_id,
            uploader_id=uploader_id,
            filename=file.filename,
            content_type=content_type,
            file_size=len(data),
            file_path=relative_path,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        return _format_attachment(attachment)

    @staticmethod
    def get_message_attachments(
        db: Session,
        message_id: int,
    ) -> List[Dict[str, Any]]:
        """List attachments for a channel/topic message."""
        rows = (
            db.query(FileAttachment)
            .filter(FileAttachment.message_id == message_id)
            .order_by(FileAttachment.created_at)
            .all()
        )
        return [_format_attachment(a) for a in rows]

    @staticmethod
    def get_dm_attachments(
        db: Session,
        dm_id: int,
    ) -> List[Dict[str, Any]]:
        """List attachments for a direct message."""
        rows = db.query(FileAttachment).filter(FileAttachment.dm_id == dm_id).order_by(FileAttachment.created_at).all()
        return [_format_attachment(a) for a in rows]

    @staticmethod
    def get_attachments_batch(
        db: Session,
        message_ids: List[int],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Batch-fetch attachments keyed by message_id."""
        if not message_ids:
            return {}
        rows = (
            db.query(FileAttachment)
            .filter(FileAttachment.message_id.in_(message_ids))
            .order_by(FileAttachment.created_at)
            .all()
        )
        result: Dict[int, List[Dict[str, Any]]] = {}
        for att in rows:
            if att.message_id is not None:
                result.setdefault(att.message_id, []).append(_format_attachment(att))
        return result

    @staticmethod
    def get_attachment(
        db: Session,
        attachment_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get a single attachment by ID."""
        att = (
            db.query(FileAttachment)
            .filter(
                FileAttachment.id == attachment_id,
            )
            .first()
        )
        if not att:
            return None
        return _format_attachment(att)


file_service = FileService()
