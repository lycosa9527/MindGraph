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

import aiohttp
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from models import Messages, get_request_language
from models.domain.auth import User
from utils.auth import get_current_user_or_api_key


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/dify/files/upload')
async def upload_file_to_dify(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key)
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

    # Get Dify configuration
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')

    if not api_key:
        logger.error("DIFY_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail=Messages.error("ai_not_configured", lang)
        )

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Check file size (15MB limit for documents, 10MB for images)
    max_size = 15 * 1024 * 1024  # 15MB
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 15MB, got {file_size / 1024 / 1024:.1f}MB"
        )

    logger.info("Uploading file to Dify: %s (%s bytes) for user %s", file.filename, file_size, user_id)

    try:
        # Create form data for Dify upload
        form_data = aiohttp.FormData()
        form_data.add_field('user', user_id)
        form_data.add_field(
            'file',
            content,
            filename=file.filename,
            content_type=file.content_type or 'application/octet-stream'
        )

        # Upload to Dify
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{api_url.rstrip('/')}/files/upload"

            async with session.post(url, data=form_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("Dify upload failed: %s - %s", response.status, error_text)

                    # Map Dify errors
                    if response.status == 413:
                        raise HTTPException(status_code=413, detail="File too large")
                    elif response.status == 415:
                        raise HTTPException(status_code=415, detail="Unsupported file type")
                    else:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"File upload failed: {error_text}"
                        )

                result = await response.json()
                logger.info("File uploaded successfully: %s", result.get('id'))

                return {
                    "success": True,
                    "data": {
                        "id": result.get("id"),
                        "name": result.get("name"),
                        "size": result.get("size"),
                        "extension": result.get("extension"),
                        "mime_type": result.get("mime_type"),
                        "created_at": result.get("created_at")
                    }
                }

    except aiohttp.ClientError as e:
        logger.error("Dify upload connection error: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to AI service") from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Dify upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/dify/app/parameters')
async def get_dify_parameters(
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Get Dify app parameters including opening_statement, suggested_questions,
    file upload settings, etc.
    """
    lang = get_request_language(x_language)

    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')

    if not api_key:
        raise HTTPException(status_code=500, detail=Messages.error("ai_not_configured", lang))

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{api_url.rstrip('/')}/parameters"

            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Failed to get parameters")

                return await response.json()

    except aiohttp.ClientError as e:
        logger.error("Dify parameters error: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to AI service") from e
