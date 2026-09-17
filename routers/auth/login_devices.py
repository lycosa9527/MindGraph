"""
Account UI: list signed-in devices and kick one offline.

GET  /login-devices
DELETE /login-devices/{device_id}

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models.domain.auth import User
from models.domain.messages import Language, Messages
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.auth.login_devices import (
    LoginDevicesUnavailableError,
    is_login_device_id,
    kick_login_device,
    list_login_devices,
    login_device_to_dict,
)
from utils.auth import (
    compute_device_hash,
    get_client_ip,
    get_current_user,
    require_not_mgat_for_token_mint,
)

router = APIRouter(tags=["Authentication"])


@router.get("/login-devices", dependencies=[Depends(require_not_mgat_for_token_mint)])
async def get_login_devices(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """List browsers that currently hold a session for this account."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "login_devices_list",
        identifier,
        max_requests=30,
        window_seconds=60,
    )
    try:
        devices = await list_login_devices(int(current_user.id), compute_device_hash(request))
    except LoginDevicesUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("login_devices_unavailable", lang=lang),
        ) from exc
    return {"devices": [login_device_to_dict(device) for device in devices]}


@router.delete(
    "/login-devices/{device_id}",
    dependencies=[Depends(require_not_mgat_for_token_mint)],
)
async def delete_login_device(
    device_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Kick one signed-in device: revoke refresh token and invalidate access."""
    if not is_login_device_id(device_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("login_device_invalid", lang=lang),
        )
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "login_devices_kick",
        identifier,
        max_requests=20,
        window_seconds=60,
    )
    current_hash = compute_device_hash(request)
    try:
        kicked = await kick_login_device(
            int(current_user.id),
            device_id,
            get_client_ip(request),
        )
    except LoginDevicesUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("login_devices_unavailable", lang=lang),
        ) from exc
    if not kicked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("login_device_not_found", lang=lang),
        )
    return {
        "ok": True,
        "kicked_current": device_id == current_hash,
    }
