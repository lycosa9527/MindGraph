"""
File Upload Endpoints
=======================

Upload and retrieve file attachments for chat messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from services.features.workshop_chat import file_service
from services.features.workshop_chat.diagram_embed import (
    load_library_diagram_spec,
    store_library_diagram_png,
)
from services.infrastructure.utils.browser import BrowserUnavailableError
from utils.auth import get_current_user

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


@router.post("/library-diagrams/{diagram_id}", status_code=status.HTTP_201_CREATED)
async def embed_library_diagram_png(
    diagram_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Render a library diagram to PNG, store it on COS, return a download URL.

    Compose inserts markdown only. Message viewers load
    ``/api/chat/attachments/{id}/download``, which 302s to COS.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "workshop_diagram_embed",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    try:
        spec, diagram_type, title = await load_library_diagram_spec(
            current_user.id,
            diagram_id,
        )
        png_bytes = await capture_diagram_screenshot(spec, diagram_type)
        return await store_library_diagram_png(
            db,
            current_user.id,
            title,
            png_bytes,
            diagram_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BrowserUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram renderer is unavailable",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to render diagram PNG",
        ) from exc


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
    """Stream a local file or 302 to a short-lived COS URL after access check."""
    resolved = await file_service.resolve_download(db, attachment_id, current_user.id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if resolved.redirect_url:
        return RedirectResponse(url=resolved.redirect_url, status_code=302)
    if resolved.disk_path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(
        path=str(resolved.disk_path),
        media_type=resolved.content_type,
        filename=resolved.filename,
    )
