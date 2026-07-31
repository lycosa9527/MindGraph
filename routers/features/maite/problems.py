"""
Mate Learning problem and OCR endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.maite.helpers import MAITE_DOMAIN_ERRORS, organization_id_for, raise_maite_http_error
from services.maite.domain.problem_service import ProblemService
from services.maite.schemas.problem import OcrResult, ProblemCreate, ProblemRead
from services.maite.uploads.storage import resolve_safe_upload_path
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
_ALLOWED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_OCR_BYTES = 8 * 1024 * 1024


def _validate_upload_file(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG, JPEG, and WebP images are supported",
        )
    return content_type


@router.post("/problems", response_model=ProblemRead, status_code=status.HTTP_201_CREATED)
async def create_problem(
    payload: ProblemCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> ProblemRead:
    """Create a Maite problem owned by the authenticated user."""
    schedule_module_activity(
        user=current_user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details={"action": "create_problem"},
        detail="create_problem",
        usage_source="mindgraph",
        usage_action="maite_problem",
        title="maite:problem",
        prompt_preview=payload.raw_text[:120],
    )
    service = ProblemService(db)
    try:
        created = await service.create_problem(
            payload,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
        )
        logger.info(
            "[Maite] User %s created problem %s (chars=%s)",
            current_user.id,
            created.id,
            len(payload.raw_text or ""),
        )
        return created
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/problems/ocr", response_model=OcrResult)
async def extract_problem_ocr(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> OcrResult:
    """Extract problem text from an uploaded image via vision LLM."""
    mime_type = _validate_upload_file(file)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("maite_ocr", identifier, max_requests=30, window_seconds=60)
    image_bytes = await file.read()
    if not image_bytes:
        logger.warning("[Maite] Empty OCR upload from user %s", current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    if len(image_bytes) > _MAX_OCR_BYTES:
        logger.warning(
            "[Maite] OCR upload too large user=%s bytes=%s",
            current_user.id,
            len(image_bytes),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds 8MB limit",
        )
    schedule_module_activity(
        user=current_user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details={"action": "ocr"},
        detail="ocr",
        usage_source="mindgraph",
        usage_action="maite_ocr",
        title="maite:ocr",
    )
    service = ProblemService(db)
    try:
        result = await service.ocr_extract(
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            image_bytes=image_bytes,
            mime_type=mime_type,
            endpoint_path="/api/maite/problems/ocr",
        )
        text_len = len(result.clean_text or result.raw_text or "")
        logger.info(
            "[Maite] OCR ok user=%s mime=%s bytes=%s text_chars=%s",
            current_user.id,
            mime_type,
            len(image_bytes),
            text_len,
        )
        return result
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/problem-bank")
async def list_problem_bank(
    _db: AsyncSession = Depends(get_async_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    """Return seeded demo problems for quick starts."""
    service = ProblemService(_db)
    return service.list_problem_bank()


@router.get("/downloads/images/{file_name}")
async def download_uploaded_image(
    file_name: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download an image previously uploaded by the current user."""
    suffix = Path(file_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    relative = f"maite/uploads/{current_user.id}/{file_name}"
    try:
        absolute = resolve_safe_upload_path(relative)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found") from exc
    media_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    return FileResponse(path=str(absolute), media_type=media_type, filename=file_name)
