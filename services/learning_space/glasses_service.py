"""Mint sheet QR tokens and accept glasses photos.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningSheetCapture, LearningSheetCopy, LearningSheetToken
from services.learning_space.glasses_contract import (
    MAX_INGEST_BYTES,
    SENT_DISPLAY,
    capture_image_path,
    parse_sheet_payload,
    sheet_payload,
)
from services.learning_space.glasses_vision import (
    VISION_SHEET_ERRORS,
    dashscope_read_learning_sheet,
    printed_diagram_outline,
)
from services.learning_space.image_storage import (
    build_logical_key,
    detect_image_content_type,
    logical_key_from_ref,
    put_image_bytes_sync,
    read_image_bytes_sync,
    ref_for_key,
)
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_MAX_SPEC_BYTES = 500_000
_ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _spec_dict(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sheet spec must be an object")
    return raw


def _ocr_status(row: LearningSheetCapture) -> str:
    if row.ocr_error:
        return "failed"
    if row.ocr_spec is None:
        return "pending"
    return "ready"


def capture_payload(row: LearningSheetCapture) -> dict[str, Any]:
    """Teacher list item."""
    return {
        "id": int(row.id),
        "sheet_id": row.sheet_id,
        "student_name": row.student_name,
        "class_name": row.class_name,
        "ocr_status": _ocr_status(row),
        "ocr_error": row.ocr_error or "",
        "spec": row.ocr_spec if isinstance(row.ocr_spec, dict) else None,
        "image_path": capture_image_path(int(row.id)),
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def mint_or_reuse_sheet(
    db: AsyncSession,
    user: User,
    *,
    diagram_id: str,
    spec: Any,
) -> LearningSheetToken:
    """Return the teacher's sheet token for this diagram, creating one when needed."""
    organization_id = user.organization_id
    if organization_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Teacher has no organization")
    course_spec = _spec_dict(spec)
    if len(str(course_spec)) > _MAX_SPEC_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sheet spec is too large")
    clean_diagram = (diagram_id or "").strip()[:36]
    if clean_diagram:
        existing = await db.execute(
            select(LearningSheetToken)
            .where(
                LearningSheetToken.owner_user_id == int(user.id),
                LearningSheetToken.diagram_id == clean_diagram,
            )
            .order_by(LearningSheetToken.created_at.desc())
            .limit(1)
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            found.course_spec = course_spec
            await db.commit()
            await db.refresh(found)
            return found
    token = LearningSheetToken(
        id=str(uuid.uuid4()),
        owner_user_id=int(user.id),
        organization_id=int(organization_id),
        diagram_id=clean_diagram or None,
        course_spec=course_spec,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


def token_response(token: LearningSheetToken) -> dict[str, str]:
    """Mint response, including the QR text."""
    return {"uuid": token.id, "qr_payload": sheet_payload(token.id)}


async def list_captures(db: AsyncSession, user: User) -> list[dict[str, Any]]:
    """Newest captures owned by this teacher."""
    result = await db.execute(
        select(LearningSheetCapture)
        .where(LearningSheetCapture.owner_user_id == int(user.id))
        .order_by(LearningSheetCapture.created_at.desc())
        .limit(100)
    )
    return [capture_payload(row) for row in result.scalars().all()]


async def capture_image_for_owner(
    db: AsyncSession,
    user: User,
    capture_id: int,
) -> tuple[bytes, str]:
    """Original photo bytes for a capture this teacher owns."""
    result = await db.execute(
        select(LearningSheetCapture).where(
            LearningSheetCapture.id == int(capture_id),
            LearningSheetCapture.owner_user_id == int(user.id),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture not found")
    logical_key = logical_key_from_ref(row.image_ref)
    if logical_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture image missing")
    stored = await asyncio.to_thread(read_image_bytes_sync, logical_key)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture image missing")
    return stored


def _image_type(data: bytes, declared: str) -> tuple[str, str]:
    if len(data) > MAX_INGEST_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large")
    detected = detect_image_content_type(data) or ""
    mime = detected if detected in _ALLOWED_TYPES else declared
    suffix = _ALLOWED_TYPES.get(mime)
    if suffix is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Use JPEG, PNG, or WebP")
    return mime, suffix


async def accept_sheet_photo(sheet_uuid: str, data: bytes, declared_type: str) -> dict[str, Any]:
    """Store a glasses photo and return the sent line. OCR runs after this returns."""
    sheet_id, copy_seq = parse_sheet_payload(sheet_uuid)
    if not sheet_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown sheet")
    mime, suffix = _image_type(data, declared_type)
    async with system_rls_session() as db:
        result = await db.execute(select(LearningSheetToken).where(LearningSheetToken.id == sheet_id))
        token = result.scalar_one_or_none()
        if token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown sheet")
        if copy_seq:
            copy = await db.execute(
                select(LearningSheetCopy).where(
                    LearningSheetCopy.sheet_id == token.id,
                    LearningSheetCopy.seq == int(copy_seq),
                )
            )
            if copy.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown sheet copy")
        logical_key = build_logical_key(owner_id=int(token.owner_user_id), filename=f"sheet{suffix}")
        await asyncio.to_thread(put_image_bytes_sync, logical_key, data, mime)
        row = LearningSheetCapture(
            sheet_id=token.id,
            owner_user_id=int(token.owner_user_id),
            organization_id=int(token.organization_id),
            image_ref=ref_for_key(logical_key),
            copy_seq=int(copy_seq) if copy_seq else None,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        capture_id = int(row.id)
    return {"accepted": True, "capture_id": capture_id, "display": SENT_DISPLAY}


async def run_sheet_ocr(capture_id: int) -> None:
    """Fill the student name and diagram spec for one stored photo."""
    async with system_rls_session() as db:
        result = await db.execute(select(LearningSheetCapture).where(LearningSheetCapture.id == int(capture_id)))
        row = result.scalar_one_or_none()
        if row is None:
            return
        image_ref = row.image_ref
        token = await db.get(LearningSheetToken, row.sheet_id)
        outline = printed_diagram_outline(token.course_spec if token is not None else None)
    logical_key = logical_key_from_ref(image_ref)
    stored = None if logical_key is None else await asyncio.to_thread(read_image_bytes_sync, logical_key)
    if stored is None:
        await _save_ocr(capture_id, "", "", None, "image_missing")
        return
    data, mime = stored
    try:
        read = await asyncio.to_thread(dashscope_read_learning_sheet, data, mime, outline)
    except VISION_SHEET_ERRORS as exc:
        logger.warning("[GlassesSheet] OCR failed for capture %s: %s", capture_id, exc)
        await _save_ocr(capture_id, "", "", None, "vision_failed")
        return
    await _save_ocr(capture_id, read.student_name, read.class_name, read.spec, read.error)


async def _save_ocr(
    capture_id: int,
    student_name: str,
    class_name: str,
    spec: Optional[dict[str, Any]],
    error: str,
) -> None:
    async with system_rls_session() as db:
        result = await db.execute(select(LearningSheetCapture).where(LearningSheetCapture.id == int(capture_id)))
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.student_name = student_name
        row.class_name = class_name
        row.ocr_spec = spec
        row.ocr_error = error or None
        await db.commit()
