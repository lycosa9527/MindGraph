"""
Device-bound canvas input mode.

GET and PUT live under ``/api/auth`` so the httpOnly ``mg_device`` cookie is sent.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from services.canvas.canvas_input_device import load_canvas_input_mode, save_canvas_input_mode
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.config import REFRESH_TOKEN_EXPIRY_DAYS
from utils.auth.request_helpers import is_https
from utils.auth.tokens import DEVICE_COOKIE_NAME, assign_device_id, read_device_cookie

router = APIRouter()

CanvasInputModeName = Literal["mouse", "laptop", "mobile", "board"]


class CanvasInputDeviceBody(BaseModel):
    """PUT body."""

    input_mode: CanvasInputModeName


class CanvasInputDeviceResponse(BaseModel):
    """Stored mode for this browser."""

    input_mode: CanvasInputModeName


def _mode_name(mode: str) -> CanvasInputModeName:
    """Map a stored string onto the response literal."""
    if mode == "mouse":
        return "mouse"
    if mode == "laptop":
        return "laptop"
    if mode == "mobile":
        return "mobile"
    if mode == "board":
        return "board"
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to load canvas input mode",
    )


def _device_id_for_request(request: Request, response: Response) -> str:
    """Reuse ``mg_device``, or mint it and set the cookie on this response."""
    existing = read_device_cookie(request)
    if existing:
        return existing
    device_id = assign_device_id(request)
    response.set_cookie(
        key=DEVICE_COOKIE_NAME,
        value=device_id,
        httponly=True,
        secure=is_https(request),
        samesite="lax",
        path="/api/auth",
        max_age=REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60,
    )
    return device_id


@router.get("/canvas-input-device", response_model=CanvasInputDeviceResponse)
async def get_canvas_input_device(
    request: Request,
    response: Response,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return this browser's canvas input mode."""
    device_id = _device_id_for_request(request, response)
    try:
        mode = await load_canvas_input_mode(db, device_id)
    except DATABASE_ERRORS as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load canvas input mode",
        ) from exc
    if mode is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canvas input mode not set",
        )
    return CanvasInputDeviceResponse(input_mode=_mode_name(mode))


@router.put("/canvas-input-device", response_model=CanvasInputDeviceResponse)
async def put_canvas_input_device(
    body: CanvasInputDeviceBody,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Store this browser's canvas input mode. Classroom boards are ``board``."""
    device_id = _device_id_for_request(request, response)
    try:
        await save_canvas_input_mode(db, device_id, body.input_mode, current_user.id)
    except DATABASE_ERRORS as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save canvas input mode",
        ) from exc
    return CanvasInputDeviceResponse(input_mode=body.input_mode)
