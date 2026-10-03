"""
Library demo playlists, speaker notes, and type styles for the signed-in user.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.library_demo import UserLibraryDemo
from models.requests.library_demo import LibraryDemoDocumentModel
from services.features.library_demo_document import normalize_library_demo
from services.features.library_demo_thumbnails import (
    clean_library_demo_diagram_id,
    library_demo_thumbnail_path,
    read_library_demo_thumbnail,
    store_library_demo_thumbnail,
)
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_BODY_CHARS = 500_000
_EMPTY = LibraryDemoDocumentModel()


def _stored_document(payload: object) -> LibraryDemoDocumentModel:
    try:
        return normalize_library_demo(payload)
    except ValueError:
        return _EMPTY


@router.get("/library-demo", response_model=LibraryDemoDocumentModel)
async def read_library_demo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> LibraryDemoDocumentModel:
    """Return this account's demo lists, notes, and type styles."""
    row = await db.scalar(select(UserLibraryDemo).where(UserLibraryDemo.user_id == current_user.id))
    if row is None:
        return _EMPTY
    return _stored_document(row.payload)


@router.put("/library-demo", response_model=LibraryDemoDocumentModel)
async def write_library_demo(
    body: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> LibraryDemoDocumentModel:
    """Replace this account's demo document."""
    if len(json.dumps(body)) > _MAX_BODY_CHARS:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Library demo is too large")
    try:
        document = normalize_library_demo(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid library demo") from exc

    payload = document.model_dump(by_alias=True, exclude_none=True)
    row = await db.scalar(select(UserLibraryDemo).where(UserLibraryDemo.user_id == current_user.id))
    now = datetime.now(UTC)
    if row is None:
        db.add(UserLibraryDemo(user_id=current_user.id, payload=payload, updated_at=now))
    else:
        row.payload = payload
        row.updated_at = now
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("Failed to save library demo for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save") from exc
    return document


@router.post("/library-demo/thumbnails")
async def upload_library_demo_thumbnail(
    diagram_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Store one list thumbnail in COS and return the same-origin URL."""
    cleaned = clean_library_demo_diagram_id(diagram_id)
    if cleaned is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid diagram")
    payload = await file.read()
    stored = await asyncio.to_thread(
        store_library_demo_thumbnail,
        current_user.id,
        cleaned,
        payload,
    )
    if not stored:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thumbnail was not stored")
    return {"url": library_demo_thumbnail_path(cleaned)}


@router.get("/library-demo/thumbnails/{diagram_id}")
async def read_library_demo_thumbnail_image(
    diagram_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Stream a stored list thumbnail. The browser never sees COS credentials."""
    cleaned = clean_library_demo_diagram_id(diagram_id)
    if cleaned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
    payload = await asyncio.to_thread(read_library_demo_thumbnail, current_user.id, cleaned)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
    return Response(content=payload, media_type="image/png")
