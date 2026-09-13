"""
HTTP clicker for mind-map 演讲模式 (desktop publishes, watch steers).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.features.slides_remote.session_store import (
    SlideRemoteError,
    drain_commands,
    end_session,
    ended_snapshot,
    enqueue_command,
    get_session,
    public_snapshot,
    upsert_session,
)
from utils.auth import get_current_user

router = APIRouter(prefix="/slides/remote", tags=["slides-remote"])


class SnapshotBody(BaseModel):
    """Desktop 演讲模式 HUD published to the watch."""

    diagram_id: str = Field(default="", max_length=64)
    title: str = Field(default="", max_length=80)
    slide_index: int = Field(default=0, ge=0, le=500)
    slide_count: int = Field(default=0, ge=0, le=500)
    traversal: str = Field(default="firstLevel", max_length=16)
    autoplay: bool = False
    can_prev: bool = False
    can_next: bool = False


class CommandBody(BaseModel):
    """One watch click."""

    action: str = Field(..., min_length=1, max_length=16)
    on: Optional[bool] = None
    mode: Optional[str] = Field(default=None, max_length=16)
    diagram_id: Optional[str] = Field(default=None, max_length=64)


def _http_for_store(exc: SlideRemoteError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message}
    if exc.code == "not_found":
        return HTTPException(status_code=404, detail=detail)
    if exc.code in {"bad_action", "bad_traversal", "bad_diagram"}:
        return HTTPException(status_code=400, detail=detail)
    return HTTPException(status_code=503, detail=detail)


def _user_id(user: User) -> int:
    return int(user.id)


@router.put("/sessions")
@router.post("/sessions")
async def publish_session(
    body: SnapshotBody,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Desktop opens or refreshes the live 演讲模式 snapshot."""
    try:
        session = await upsert_session(user_id=_user_id(current_user), fields=body.model_dump())
    except SlideRemoteError as exc:
        raise _http_for_store(exc) from exc
    return public_snapshot(session)


@router.get("/sessions/active")
async def active_session(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Watch poll: idle when the desktop is not in 演讲模式."""
    session = await get_session(_user_id(current_user))
    return public_snapshot(session)


@router.get("/commands")
async def pop_commands(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Desktop drains queued watch clicks."""
    items = await drain_commands(_user_id(current_user))
    return {"items": items}


@router.post("/command")
async def post_command(
    body: CommandBody,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Watch posts next / prev / autoplay / traversal / quit / start."""
    payload = body.model_dump(exclude_none=True)
    try:
        row = await enqueue_command(_user_id(current_user), payload)
    except SlideRemoteError as exc:
        raise _http_for_store(exc) from exc
    return {"ok": True, "command": row}


@router.post("/end")
async def close_session(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Desktop leaves 演讲模式."""
    await end_session(_user_id(current_user))
    return ended_snapshot()
