"""Share a saved canvas diagram into a live seminar, and open a personal copy."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import (
    build_public_temp_image_url,
    check_endpoint_rate_limit,
    generate_signed_url,
    get_rate_limit_identifier,
)
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from routers.auth.dependencies import get_language_dependency
from services.diagram.temp_image_storage import persist_diagram_preview_png
from services.features.mindmate_collab.diagram_library import (
    COPY_FAILED,
    COPY_FORBIDDEN,
    COPY_LIMIT,
    COPY_NOT_FOUND,
    COPY_NO_SPEC,
    load_shared_canvas_diagram_preview,
    save_shared_canvas_diagram_for_user,
)
from services.features.mindmate_collab.group_members import user_observes_seminar
from services.features.mindmate_collab.share_canvas import (
    SHARE_FORBIDDEN,
    SHARE_NOT_FOUND,
    SHARE_NOT_LIVE,
    post_canvas_diagram_share,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()
logger = logging.getLogger(__name__)

_SHARE_STATUS = {
    SHARE_NOT_FOUND: 404,
    SHARE_FORBIDDEN: 403,
    SHARE_NOT_LIVE: 409,
}
_COPY_STATUS = {
    COPY_FORBIDDEN: 403,
    COPY_LIMIT: 409,
    COPY_NO_SPEC: 409,
    COPY_NOT_FOUND: 404,
    COPY_FAILED: 500,
}


class ShareCanvasDiagramRequest(BaseModel):
    """Body for posting the caller's saved diagram into a seminar."""

    diagram_id: str = Field(min_length=36, max_length=36)
    note: str = Field(default="", max_length=500)


class OpenSharedCanvasRequest(BaseModel):
    """Body for opening a diagram that was shared into a seminar."""

    diagram_id: str = Field(min_length=36, max_length=36)


async def _require_collab_tier(user: User, lang: Language) -> None:
    """Ensure the caller has the online_collab school tier feature."""
    async with actor_rls_session(user) as db:
        await assert_user_has_school_tier_feature(
            db,
            user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )


async def _preview_url(request: Request, user_id: int, diagram_id: str) -> str:
    """Public preview URL for the chat bubble. Empty when capture is unavailable."""
    record = await get_diagram_cache().get_diagram(user_id, diagram_id)
    if record is None:
        return ""
    spec = record.get("spec")
    if not isinstance(spec, dict) or not spec:
        return ""
    diagram_type = str(record.get("diagram_type") or "mind_map")
    try:
        png_bytes = await capture_diagram_screenshot(spec, diagram_type)
    except RuntimeError as exc:
        logger.warning("[CanvasShare] preview capture failed: %s", exc)
        return ""
    filename = f"diagram_{uuid.uuid4().hex}.png"
    try:
        await persist_diagram_preview_png(filename, png_bytes)
    except (OSError, ValueError) as exc:
        logger.warning("[CanvasShare] preview write failed: %s", exc)
        return ""
    signed_path = generate_signed_url(filename, expiration_seconds=86400)
    return build_public_temp_image_url(request, signed_path)


@router.post("/{session_id}/share-diagram")
async def share_canvas_diagram(
    request: Request,
    session_id: str,
    body: ShareCanvasDiagramRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Post the caller's saved diagram into a live seminar."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_share_diagram",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    if await user_observes_seminar(session_id, int(current_user.id)):
        raise HTTPException(status_code=403, detail="observer_readonly")
    image_url = await _preview_url(request, int(current_user.id), body.diagram_id)
    payload, error = await post_canvas_diagram_share(
        session_id,
        body.diagram_id,
        current_user,
        image_url=image_url,
        note=body.note,
    )
    if error or payload is None:
        raise HTTPException(status_code=_SHARE_STATUS.get(error, 400), detail=error or SHARE_NOT_FOUND)
    return payload


@router.get("/{session_id}/canvas-diagram/{diagram_id}")
async def preview_shared_canvas_diagram(
    request: Request,
    session_id: str,
    diagram_id: str,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return the shared diagram spec so the seminar bubble can render it."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_canvas_preview",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    payload, error = await load_shared_canvas_diagram_preview(
        session_id,
        diagram_id,
        current_user,
    )
    if error or payload is None:
        status = _COPY_STATUS.get(error or "", 500)
        raise HTTPException(status_code=status, detail=error or COPY_FAILED)
    return payload


@router.post("/{session_id}/canvas-diagram")
async def open_shared_canvas_diagram(
    request: Request,
    session_id: str,
    body: OpenSharedCanvasRequest,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return a library id the caller can open. Members receive a personal copy."""
    await _require_collab_tier(current_user, lang)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_collab_canvas_diagram",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    diagram_id, error = await save_shared_canvas_diagram_for_user(
        session_id,
        body.diagram_id,
        current_user,
    )
    if error or not diagram_id:
        status = _COPY_STATUS.get(error or "", 500)
        raise HTTPException(status_code=status, detail=error or COPY_FAILED)
    return {"diagram_id": diagram_id}
