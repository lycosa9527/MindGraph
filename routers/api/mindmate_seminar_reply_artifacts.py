"""Archive a MindMate seminar reply as a Word artifact."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_seminar.background_files import list_reply_artifacts, load_folder_session
from services.features.mindmate_seminar.reply_artifacts import archive_assistant_reply
from services.mindmate.teaching_design_template_store import DOCX_READ_ERRORS
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()
logger = logging.getLogger(__name__)

_STATUS = {
    "room_not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "message_not_found": status.HTTP_404_NOT_FOUND,
    "empty_reply": status.HTTP_400_BAD_REQUEST,
    "reply_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "file_too_large": status.HTTP_400_BAD_REQUEST,
    "file_type": status.HTTP_400_BAD_REQUEST,
    "file_limit": status.HTTP_400_BAD_REQUEST,
}


class ReplyArtifactBody(BaseModel):
    """Which stored assistant reply to turn into a Word artifact."""

    message_id: int = Field(..., ge=1)


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


@router.get("/{session_id}/reply-artifacts")
async def list_seminar_reply_artifacts(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List Word files archived from MindMate replies in this seminar."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_reply_artifacts_list",
        get_rate_limit_identifier(current_user, request),
        max_requests=60,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return {"items": await list_reply_artifacts(session.id)}


@router.post("/{session_id}/reply-artifacts", status_code=status.HTTP_201_CREATED)
async def create_seminar_reply_artifact(
    session_id: str,
    body: ReplyArtifactBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Turn one stored assistant reply into a Word file and keep it in 产物."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_reply_artifacts",
        get_rate_limit_identifier(current_user, request),
        max_requests=12,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    try:
        saved = await archive_assistant_reply(
            session,
            message_id=body.message_id,
            uploader_user_id=int(current_user.id),
            room_code=session.code,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    except (FileNotFoundError, *DOCX_READ_ERRORS) as exc:
        logger.exception(
            "[SeminarArtifact] docx build failed session=%s message=%s",
            session_id,
            body.message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="reply_docx_failed",
        ) from exc
    return saved
