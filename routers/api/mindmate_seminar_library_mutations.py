"""
Rename, pin, and delete a saved MindMate seminar.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.features.mindmate_seminar.library_archive import (
    delete_saved_seminar,
    update_saved_seminar,
)
from utils.auth import get_current_user

router = APIRouter()


class UpdateSavedSeminarRequest(BaseModel):
    """Body for PATCH /mindmate/seminar/my/library/{session_id}."""

    title: Optional[str] = None
    pinned: Optional[bool] = None


def raise_saved_seminar_error(error: Optional[str]) -> NoReturn:
    """Map a library mutation error code to an HTTP error."""
    if error in ("empty_title", "title_too_long", "empty_update"):
        raise HTTPException(status_code=400, detail="Invalid seminar update")
    if error == "still_live":
        raise HTTPException(status_code=409, detail="Seminar is still live")
    raise HTTPException(status_code=404, detail="Saved seminar not found")


@router.patch("/my/library/{session_id}")
async def update_my_saved_seminar(
    request: Request,
    session_id: str,
    body: UpdateSavedSeminarRequest,
    current_user: User = Depends(get_current_user),
):
    """Rename a saved seminar, pin it, or both."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_library_update",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    payload, error = await update_saved_seminar(
        session_id,
        current_user.id,
        title=body.title,
        pinned=body.pinned,
    )
    if error or payload is None:
        raise_saved_seminar_error(error)
    return {"success": True, "seminar": payload}


@router.delete("/my/library/{session_id}")
async def delete_my_saved_seminar(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a saved seminar and its transcript."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_seminar_library_delete",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    error = await delete_saved_seminar(session_id, current_user.id)
    if error:
        raise_saved_seminar_error(error)
    return {"success": True}
