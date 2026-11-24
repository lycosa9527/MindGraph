"""List, pin, and remove shared seminar highlights."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.features.mindmate_seminar.background_files import load_folder_session
from services.features.mindmate_seminar.highlights import (
    MAX_HIGHLIGHT_TEXT,
    SeminarHighlightDraft,
    create_seminar_highlight,
    delete_seminar_highlight,
    list_seminar_highlights,
    parse_highlight_instant,
)
from utils.auth import get_current_user

router = APIRouter()

_STATUS = {
    "room_not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "observer_readonly": status.HTTP_403_FORBIDDEN,
    "empty": status.HTTP_400_BAD_REQUEST,
    "highlight_limit": status.HTTP_400_BAD_REQUEST,
    "duplicate": status.HTTP_409_CONFLICT,
}


class SeminarHighlightBody(BaseModel):
    """Pin a whole message or a selected excerpt as a group highlight."""

    session_id: str = Field(..., min_length=8, max_length=36)
    text: str = Field(..., min_length=1, max_length=MAX_HIGHLIGHT_TEXT)
    author_name: str = Field("", max_length=80)
    created_by_name: str = Field("", max_length=80)
    message_id: int | None = None
    message_at: str | None = None


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    return HTTPException(status_code=_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code)


@router.get("/highlights")
async def list_highlights(
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
):
    """Return every highlight in this seminar, not only the caller's."""
    await check_endpoint_rate_limit(
        "mindmate_seminar_highlights",
        get_rate_limit_identifier(current_user, request),
        max_requests=60,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return {"items": await list_seminar_highlights(session.id)}


@router.post("/highlights", status_code=status.HTTP_201_CREATED)
async def pin_highlight(
    body: SeminarHighlightBody,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Pin one highlight that every participant can see."""
    await check_endpoint_rate_limit(
        "mindmate_seminar_highlight_pin",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, body.session_id)
        return await create_seminar_highlight(
            session,
            current_user,
            SeminarHighlightDraft(
                text=body.text,
                author_name=body.author_name,
                created_by_name=body.created_by_name,
                message_id=body.message_id,
                message_at=parse_highlight_instant(body.message_at),
            ),
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete("/highlights/{highlight_id}")
async def unpin_highlight(
    highlight_id: str,
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
):
    """Remove a highlight the caller owns, or any highlight if they lead the room."""
    await check_endpoint_rate_limit(
        "mindmate_seminar_highlight_delete",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        return await delete_seminar_highlight(session, current_user, highlight_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
