"""HTTP handler: Kitty conversation image → OCR / hand-drawn rebuild."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import File, Form, HTTPException, UploadFile

from models.domain.auth import User
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.knowledge.conversation_image import process_conversation_image
from services.knowledge.conversation_image_upload import (
    ALLOWED_CONVERSATION_IMAGE_TYPES,
    normalize_conversation_image_content_type,
    validate_conversation_image_bytes,
)
from services.utils.error_types import FILE_IO_ERRORS, LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

_PROCESS_ERRORS: tuple[type[BaseException], ...] = LLM_PIPELINE_ERRORS + FILE_IO_ERRORS


async def kitty_rest_conversation_image(
    current_user: User,
    file: UploadFile = File(...),
    language: str = Form("zh"),
    diagram_id: str = Form(...),
    diagram_title: Optional[str] = Form(None),
    apply_to_library: bool = Form(True),
) -> dict:
    """Process a conversation image (hand-drawn rebuild or OCR extract)."""
    mime = normalize_conversation_image_content_type(
        content_type=file.content_type,
        filename=file.filename,
    )
    if mime not in ALLOWED_CONVERSATION_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    raw = await file.read()
    try:
        validate_conversation_image_bytes(raw)
    except ValueError as exc:
        detail = str(exc)
        status = 413 if detail == "Image too large" else 400
        raise HTTPException(status_code=status, detail=detail) from exc

    org_id = getattr(current_user, "organization_id", None)
    try:
        result = await process_conversation_image(
            user_id=int(current_user.id),
            organization_id=int(org_id) if org_id is not None else None,
            image_bytes=raw,
            mime_type=mime,
            filename=(file.filename or "photo.jpg"),
            language=language,
            diagram_id=diagram_id,
            diagram_title=diagram_title,
            apply_to_library=bool(apply_to_library),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except _PROCESS_ERRORS as exc:
        logger.warning(
            "[ConversationImage] failed user=%s: %s",
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Image processing failed") from exc

    if result.get("mode") == "handdrawn" and current_user.id:
        schedule_user_usage_activity(
            user_id=int(current_user.id),
            organization_id=org_id,
            source="mindgraph",
            action="diagram_generate",
            title=(diagram_title or file.filename or "hand-drawn")[:200],
            prompt_preview="conversation_image_handdrawn",
            diagram_type="mind_map",
        )
    return result
