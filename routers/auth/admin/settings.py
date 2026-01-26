"""
Admin Settings Management Endpoints
===================================

Admin-only settings management endpoints:
- GET /admin/settings - Get system settings
- PUT /admin/settings - Update system settings

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status

from models.domain.auth import User
from models.domain.messages import Messages
from ..dependencies import get_language_dependency, require_admin





logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/settings", dependencies=[Depends(require_admin)])
async def get_settings_admin():
    """Get system settings from .env (ADMIN ONLY)"""
    env_path = ".env"
    settings = {}

    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Skip critical settings (JWT_SECRET_KEY is now auto-managed via Redis)
                    if key in ['DATABASE_URL']:
                        continue

                    if 'PASSWORD' in key or 'SECRET' in key or 'PASSKEY' in key:
                        settings[key] = "******"
                    else:
                        settings[key] = value

    return settings


@router.put("/admin/settings", dependencies=[Depends(require_admin)])
async def update_settings_admin(
    request: dict,
    current_user: User = Depends(require_admin),
    lang: str = Depends(get_language_dependency)
):
    """Update system settings in .env (ADMIN ONLY)"""
    # JWT_SECRET_KEY is now auto-managed via Redis (not in .env)
    forbidden_keys = ['DATABASE_URL']
    for key in request:
        if key in forbidden_keys:
            error_msg = Messages.error("cannot_modify_field_via_api", lang, key)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    env_path = ".env"
    lines = []

    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    updated_keys = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in request:
                lines[i] = f"{key}={request[key]}\n"
                updated_keys.add(key)

    for key, value in request.items():
        if key not in updated_keys:
            lines.append(f"{key}={value}\n")

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    updated_keys_list = list(request.keys())
    logger.warning("Admin %s updated .env settings: %s", current_user.phone, updated_keys_list)

    return {
        "message": Messages.success("settings_updated", lang),
        "warning": Messages.warning("server_restart_required", lang),
        "updated_keys": list(request.keys())
    }
