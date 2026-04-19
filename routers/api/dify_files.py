"""
Dify File Upload API Router
============================

API endpoint for uploading files to Dify:
- /api/dify/files/upload: Upload file for Vision/document processing

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from clients.dify import AsyncDifyClient
from models import Messages, get_request_language
from models.domain.auth import User
from utils.auth import get_current_user_or_api_key


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


def _get_dify_client(lang: str) -> AsyncDifyClient:
    """Instantiate AsyncDifyClient from environment, raising 500 if unconfigured."""
    api_key = os.getenv("DIFY_API_KEY")
    api_url = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))

    if not api_key:
        logger.error("DIFY_API_KEY not configured")
        raise HTTPException(status_code=500, detail=Messages.error("ai_not_configured", lang))

    return AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)


@router.post("/dify/files/upload")
async def upload_file_to_dify(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Upload a file to Dify for use in chat messages.

    Supports:
    - Images: JPG, JPEG, PNG, GIF, WEBP, SVG
    - Documents: TXT, MD, PDF, HTML, XLSX, DOC, DOCX, CSV, PPT, PPTX, XML, EPUB
    - Audio: MP3, M4A, WAV, WEBM, MPGA
    - Video: MP4, MOV, MPEG, WEBM

    Returns:
        id: Upload file ID to use in chat messages
        name: Original filename
        size: File size in bytes
        extension: File extension
        mime_type: File MIME type
    """
    lang = get_request_language(x_language)
    client = _get_dify_client(lang)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    file_size = len(content)

    max_size = 15 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 15MB, got {file_size / 1024 / 1024:.1f}MB",
        )

    logger.info(
        "Uploading file to Dify: %s (%s bytes) for user %s",
        file.filename,
        file_size,
        user_id,
    )

    try:
        result = await client.upload_file(
            user_id=user_id,
            file_bytes=content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
        )
        logger.info("File uploaded successfully: %s", result.get("id"))

        return {
            "success": True,
            "data": {
                "id": result.get("id"),
                "name": result.get("name"),
                "size": result.get("size"),
                "extension": result.get("extension"),
                "mime_type": result.get("mime_type"),
                "created_at": result.get("created_at"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Dify upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dify/app/parameters")
async def get_dify_parameters(
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Get Dify app parameters including opening_statement, suggested_questions,
    file upload settings, etc.
    """
    lang = get_request_language(x_language)
    client = _get_dify_client(lang)

    try:
        return await client.get_app_parameters()
    except Exception as e:
        logger.error("Dify parameters error: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to AI service") from e
