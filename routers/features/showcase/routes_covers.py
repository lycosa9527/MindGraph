"""Showcase teaching-design cover SSE stream."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from models.domain.auth import User
from services.showcase.covers.stream import showcase_cover_stream_response
from utils.auth import get_current_user

router = APIRouter()


@router.get("/posts/{post_id}/cover-stream")
async def stream_showcase_cover(
    post_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """SSE: cover_ready / cover_fail for a teaching-design post."""
    return await showcase_cover_stream_response(request, post_id, current_user)
