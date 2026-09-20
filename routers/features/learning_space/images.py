"""Learning Space instruction-image upload and download."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningAssignment
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_current_user
from routers.features.learning_space.deps import get_learning_space_db
from services.learning_space.access import (
    get_class_for_publisher,
    require_pilot_teacher,
    resolve_assignment_viewer,
)
from services.learning_space.assignments import get_assignment
from services.learning_space.image_storage import (
    MAX_IMAGE_BYTES,
    build_logical_key,
    create_presigned_get,
    detect_image_content_type,
    logical_key_from_ref,
    put_image_bytes_sync,
    read_image_bytes_sync,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_UPLOAD_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


async def _assert_can_view_assignment(
    db: AsyncSession,
    current_user: User,
    assignment: LearningAssignment,
) -> None:
    await resolve_assignment_viewer(db, current_user, assignment)


@router.post("/teacher/instruction-images")
async def upload_instruction_image(
    request: Request,
    class_id: int | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Store an instruction image on COS (local fallback only when COS is off)."""
    await require_pilot_teacher(db, current_user)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("learning_space_images", identifier, max_requests=30, window_seconds=60)
    if class_id is not None:
        await get_class_for_publisher(db, class_id, current_user)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    try:
        payload = await file.read(MAX_IMAGE_BYTES + 1)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[LearningSpace] Instruction image read failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=503, detail="Upload unavailable") from exc
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="instruction image too large")
    detected = detect_image_content_type(payload)
    if detected is None or detected not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    content_type = detected
    filename = file.filename or "image.jpg"
    logical_key = build_logical_key(owner_id=int(current_user.id), filename=filename)
    try:
        ref = await asyncio.to_thread(put_image_bytes_sync, logical_key, payload, content_type)
    except ValueError as exc:
        logger.warning(
            "[LearningSpace] Instruction image store failed user=%s: %s",
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("[LearningSpace] Instruction image uploaded user=%s class=%s", current_user.id, class_id)
    return {"ref": ref}


@router.get("/instruction-images/{assignment_id}/{index}")
async def download_instruction_image(
    assignment_id: int,
    index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_learning_space_db),
):
    """Access-checked image: 302 to COS when possible, otherwise stream bytes."""
    if index < 0 or index > 5:
        raise HTTPException(status_code=404, detail="Image not found")
    assignment = await get_assignment(db, assignment_id)
    await _assert_can_view_assignment(db, current_user, assignment)
    images = assignment.instruction_images
    if not isinstance(images, list) or index >= len(images):
        raise HTTPException(status_code=404, detail="Image not found")
    raw = images[index]
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=404, detail="Image not found")
    if raw.startswith("data:") or raw.startswith("http://") or raw.startswith("https://"):
        raise HTTPException(status_code=404, detail="Image not found")
    key = logical_key_from_ref(raw)
    if key is None:
        raise HTTPException(status_code=404, detail="Image not found")
    presigned = create_presigned_get(key)
    if presigned:
        return RedirectResponse(presigned, status_code=302)
    loaded = await asyncio.to_thread(read_image_bytes_sync, key)
    if loaded is None:
        logger.warning(
            "[LearningSpace] Instruction image missing assignment=%s index=%s",
            assignment_id,
            index,
        )
        raise HTTPException(status_code=404, detail="Image not found")
    body, content_type = loaded
    return Response(
        content=body,
        media_type=content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
