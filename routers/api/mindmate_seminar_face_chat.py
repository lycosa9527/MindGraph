"""Save a seminar face-to-face transcript onto COS as it is recorded."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language
from models.domain.mindmate_seminar import MindmateSeminarSession
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_seminar.background_files import load_folder_session
from services.features.mindmate_seminar.face_chat_files import (
    hold_face_chat_lock,
    release_face_chat_lock,
    upsert_face_chat_document,
)
from services.features.mindmate_seminar.group_members import user_observes_seminar
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()
logger = logging.getLogger(__name__)

_STATUS = {
    "room_not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "file_missing": status.HTTP_404_NOT_FOUND,
    "empty_reply": status.HTTP_400_BAD_REQUEST,
    "file_too_large": status.HTTP_400_BAD_REQUEST,
    "file_type": status.HTTP_400_BAD_REQUEST,
    "file_limit": status.HTTP_400_BAD_REQUEST,
    "face_chat_busy": status.HTTP_409_CONFLICT,
    "upload_failed": status.HTTP_503_SERVICE_UNAVAILABLE,
}


class FaceChatSaveBody(BaseModel):
    """One markdown snapshot of the in-person notes."""

    content: str = Field(..., min_length=1, max_length=400_000)
    filename: str = Field(default="", max_length=180)
    file_id: str = Field(default="", max_length=36)
    token: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9-]*$")


class FaceChatLockBody(BaseModel):
    """Client token for the one live recorder in this seminar."""

    token: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    refresh: bool = False


async def _require_collab_tier(current_user: User, lang: Language) -> None:
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    return HTTPException(status_code=_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code)


async def _writable_session(current_user: User, session_id: str) -> MindmateSeminarSession:
    """Load a seminar the caller may record in."""
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    if await user_observes_seminar(session.id, int(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="observer_readonly")
    return session


@router.put("/{session_id}/face-chat")
async def save_seminar_face_chat(
    session_id: str,
    body: FaceChatSaveBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Overwrite the live face-to-face markdown for this recorder."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_face_chat",
        get_rate_limit_identifier(current_user, request),
        max_requests=40,
        window_seconds=60,
    )
    session = await _writable_session(current_user, session_id)
    try:
        saved = await upsert_face_chat_document(
            session,
            current_user,
            content=body.content,
            filename=body.filename,
            file_id=body.file_id,
            token=body.token,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    except DATABASE_ERRORS:
        logger.exception(
            "[SeminarFaceChat] save failed user=%s session=%s",
            current_user.id,
            session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="upload_failed",
        ) from None
    return saved


@router.post("/{session_id}/face-chat/claim")
async def claim_seminar_face_chat(
    session_id: str,
    body: FaceChatLockBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Take or refresh the single recorder lock before the microphone opens."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_face_chat_claim",
        get_rate_limit_identifier(current_user, request),
        max_requests=80,
        window_seconds=60,
    )
    session = await _writable_session(current_user, session_id)
    held = await hold_face_chat_lock(
        session.code,
        int(current_user.id),
        body.token,
        refresh=body.refresh,
    )
    if not held:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="face_chat_busy")
    return {"ok": True}


@router.post("/{session_id}/face-chat/release")
async def release_seminar_face_chat(
    session_id: str,
    body: FaceChatLockBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Release the recorder lock when this client stops."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_face_chat_release",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    session = await _writable_session(current_user, session_id)
    await release_face_chat_lock(session.code, int(current_user.id), body.token)
    return {"ok": True}
