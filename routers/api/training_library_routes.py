"""Course Builder video library and the required-tutorial gate."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from models.domain.auth import User
from services.features.training.tutorial_gate import (
    complete_required_course,
    required_course_payload,
)
from services.features.training.vod_library import (
    TrainingVodError,
    list_author_library,
    play_for_training,
)
from utils.auth import get_current_user
from utils.db.session_open import system_rls_session

router = APIRouter()


def _locale(user: User) -> str:
    return str(getattr(user, "preferred_language", None) or "zh")


def _vod_error(exc: TrainingVodError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.code)


@router.get("/vod/library")
async def training_vod_library(current_user: User = Depends(get_current_user)) -> dict:
    """Folders and ready videos a course author can place on a step."""
    async with system_rls_session() as db:
        try:
            return await list_author_library(db, current_user)
        except TrainingVodError as exc:
            raise _vod_error(exc) from exc


@router.get("/vod/play/{media_id}")
async def training_vod_play(
    media_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """TCPlayer token for an author, or a video placed on a published course."""
    async with system_rls_session() as db:
        try:
            return await play_for_training(db, current_user, media_id)
        except TrainingVodError as exc:
            raise _vod_error(exc) from exc


@router.get("/required")
async def training_required_course(current_user: User = Depends(get_current_user)) -> dict:
    """The published mandatory course this user still has to finish."""
    async with system_rls_session() as db:
        course = await required_course_payload(db, int(current_user.id), _locale(current_user))
        return {"course": course}


@router.post("/courses/{course_id}/complete")
async def training_complete_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark a required course finished for the current user."""
    async with system_rls_session() as db:
        try:
            await complete_required_course(db, int(current_user.id), course_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="not_required") from exc
        await db.commit()
    return {"ok": True}
