"""
File Upload Endpoints
=======================

Upload and retrieve file attachments for chat messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from services.features.workshop_chat import file_service
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    message_id: int = 0,
    dm_id: int = 0,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file attachment.

    Pass ``message_id`` or ``dm_id`` to associate the file with a
    specific message.  Pass neither (both 0) to upload first and
    associate later.
    """
    try:
        result = await file_service.save_attachment(
            db,
            file,
            current_user.id,
            message_id=message_id if message_id > 0 else None,
            dm_id=dm_id if dm_id > 0 else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return result


@router.get("/attachments/{attachment_id}")
async def get_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Get attachment metadata by ID (channel/DM membership required)."""
    att = await file_service.get_attachment(db, attachment_id, user_id=current_user.id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return att


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Stream attachment bytes after access check."""
    resolved = await file_service.resolve_download(db, attachment_id, current_user.id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    disk_path, content_type, filename = resolved
    return FileResponse(
        path=str(disk_path),
        media_type=content_type,
        filename=filename,
    )
