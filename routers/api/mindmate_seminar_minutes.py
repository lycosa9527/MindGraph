"""Draft seminar minutes with qwen3.8-flash. The room still posts the card."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarSession
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.features.mindmate_seminar.background_files import load_folder_session
from services.features.mindmate_seminar.group_members import user_observes_seminar
from services.features.mindmate_seminar.minutes_draft import MinutesDraftInput, draft_seminar_minutes
from services.infrastructure.http.error_handler import LLMServiceError
from services.infrastructure.http.llm_http_errors import raise_http_for_llm_error
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

_STATUS = {
    "room_not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "observer_readonly": status.HTTP_403_FORBIDDEN,
    "empty_transcript": status.HTTP_400_BAD_REQUEST,
    "empty_reply": status.HTTP_502_BAD_GATEWAY,
}


class SeminarMinutesBody(BaseModel):
    """Facts for one minutes draft. The transcript is the seminar slice."""

    zh: bool = True
    topic: str = Field(default="", max_length=200)
    goals: list[str] = Field(default_factory=list, max_length=12)
    speakers: str = Field(default="", max_length=2000)
    observers: str = Field(default="", max_length=2000)
    files: list[str] = Field(default_factory=list, max_length=30)
    quotes: list[str] = Field(default_factory=list, max_length=3)
    transcript: str = Field(min_length=1, max_length=48_000)

    @field_validator("goals", "files", "quotes")
    @classmethod
    def _trim_lines(cls, value: list[str]) -> list[str]:
        kept: list[str] = []
        for item in value:
            text = item.strip()
            if text:
                kept.append(text[:500])
        return kept

    @field_validator("transcript")
    @classmethod
    def _transcript(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("empty_transcript")
        return text


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    return HTTPException(status_code=_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code)


async def _writable_session(current_user: User, session_id: str) -> MindmateSeminarSession:
    """Load a seminar the caller may summarize."""
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    if await user_observes_seminar(session.id, int(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="observer_readonly")
    return session


def _organization_id(current_user: User) -> int | None:
    raw = getattr(current_user, "organization_id", None)
    if isinstance(raw, int):
        return raw
    return None


@router.post("/{session_id}/minutes")
async def create_seminar_minutes_draft(
    session_id: str,
    body: SeminarMinutesBody,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return qwen3.8-flash minutes JSON. The client edits it before anyone else sees it."""
    await check_endpoint_rate_limit(
        "mindmate_seminar_minutes",
        get_rate_limit_identifier(current_user, request),
        max_requests=12,
        window_seconds=60,
    )
    await _writable_session(current_user, session_id)
    draft = MinutesDraftInput(
        zh=body.zh,
        topic=body.topic,
        goals=body.goals,
        speakers=body.speakers,
        observers=body.observers,
        files=body.files,
        quotes=body.quotes,
        transcript=body.transcript,
    )
    try:
        text = await draft_seminar_minutes(
            draft,
            user_id=int(current_user.id),
            organization_id=_organization_id(current_user),
        )
    except ValueError as exc:
        code = str(exc)
        if code not in _STATUS:
            logger.warning(
                "[SeminarMinutes] draft rejected user=%s session=%s: %s",
                current_user.id,
                session_id,
                code,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="summary_failed") from exc
        raise _http_error(exc) from exc
    except LLMServiceError as exc:
        raise_http_for_llm_error(exc)
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning(
            "[SeminarMinutes] draft failed user=%s session=%s: %s",
            current_user.id,
            session_id,
            exc,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="summary_failed") from exc
    return {"text": text}
