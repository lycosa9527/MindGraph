"""
Device-bound mobile or desktop shell.

GET and PUT live under ``/api/auth`` so the httpOnly ``mg_device`` cookie is sent.
The cookie id is stored with the signed-in user's choice and overrides automatic
mobile detection on that browser.

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
from services.auth.client_shell_device import load_client_shell, save_client_shell
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.config import REFRESH_TOKEN_EXPIRY_DAYS
from utils.auth.request_helpers import is_https
from utils.auth.tokens import DEVICE_COOKIE_NAME, assign_device_id, read_device_cookie

router = APIRouter()

ClientShellName = Literal["mobile", "desktop"]


class ClientShellDeviceBody(BaseModel):
    """PUT body."""

    shell: ClientShellName


class ClientShellDeviceResponse(BaseModel):
    """Stored shell for this browser."""

    shell: ClientShellName


def _shell_name(shell: str) -> ClientShellName:
    """Map a stored string onto the response literal."""
    if shell == "mobile":
        return "mobile"
    if shell == "desktop":
        return "desktop"
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to load client shell",
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


@router.get("/client-shell", response_model=ClientShellDeviceResponse)
async def get_client_shell(
    request: Request,
    response: Response,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return this browser's locked shell."""
    device_id = _device_id_for_request(request, response)
    try:
        shell = await load_client_shell(db, device_id)
    except DATABASE_ERRORS as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load client shell",
        ) from exc
    if shell is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client shell not set",
        )
    return ClientShellDeviceResponse(shell=_shell_name(shell))


@router.put("/client-shell", response_model=ClientShellDeviceResponse)
async def put_client_shell(
    body: ClientShellDeviceBody,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Store this browser's shell with the signed-in user and device id."""
    device_id = _device_id_for_request(request, response)
    try:
        await save_client_shell(db, device_id, body.shell, current_user.id)
    except DATABASE_ERRORS as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save client shell",
        ) from exc
    return ClientShellDeviceResponse(shell=body.shell)
