"""Chrome extension PDF text extraction, with OCR for image-only pages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.knowledge.extension_pdf_text import MAX_EXTENSION_PDF_BYTES, extract_pdf_bytes
from services.learning_space.ai_gate import assert_student_ai_capability
from utils.auth import get_current_user_or_api_key

router = APIRouter(tags=["extension"])


@router.post("/extension/extract_pdf_text")
async def extension_extract_pdf_text(
    request: Request,
    file: UploadFile = File(...),
    max_pages: int = Form(4),
    image_based: bool = Form(False),
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Return embedded text, or vision-OCR text when the PDF pages are images."""
    if current_user is not None:
        await assert_student_ai_capability(db, current_user, request, "web_generate")
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "extension_extract_pdf_text",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    raw = await file.read()
    if len(raw) > MAX_EXTENSION_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is too large")
    try:
        return await asyncio.to_thread(extract_pdf_bytes, raw, max_pages, image_based)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
