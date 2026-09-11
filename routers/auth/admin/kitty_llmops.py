"""
Admin: Kitty architecture manifest + thin device / session strip.

Access: super-admin only. Prefer ``require_panel_capability(CAP_SETTINGS_KITTY_LLMOPS)``
over ``require_admin`` when migrating (dependencies.py cookbook).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from routers.auth.dependencies import require_settings_kitty_llmops
from services.kitty.http.llmops_manifest import build_kitty_llmops_manifest
from services.kitty.session.device_hello import (
    list_hello_devices,
    list_live_voice_sessions,
    load_user_kitty_defaults,
    save_user_kitty_defaults,
)
from services.kitty.session.listen_modes import normalize_listen_mode
from utils.auth.admin_scope import AdminScope

router = APIRouter()


class KittyUserDefaultsBody(BaseModel):
    """Per-user Kitty listen / TTS defaults."""

    listen_mode: Optional[str] = Field(default=None, max_length=16)
    tts_enabled: Optional[bool] = None


@router.get("/admin/kitty-llmops/architecture")
async def get_kitty_llmops_architecture(
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict:
    """Return Kitty module map + hub contract for the admin LLMOps tab."""
    return build_kitty_llmops_manifest()


@router.get("/admin/kitty-llmops/devices")
async def get_kitty_llmops_devices(
    user_id: Optional[int] = Query(default=None, ge=1),
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict[str, Any]:
    """Watches / phones that completed hello (id, last seen, listen_mode)."""
    return {"devices": await list_hello_devices(user_id=user_id)}


@router.get("/admin/kitty-llmops/sessions")
async def get_kitty_llmops_sessions(
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict[str, Any]:
    """In-process voice sessions: phase, listen_mode, lane (no secrets)."""
    return {"sessions": list_live_voice_sessions()}


@router.get("/admin/kitty-llmops/defaults/{user_id}")
async def get_kitty_llmops_defaults(
    user_id: int,
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict[str, Any]:
    """Per-user listen_mode / TTS defaults."""
    return await load_user_kitty_defaults(user_id)


@router.put("/admin/kitty-llmops/defaults/{user_id}")
async def put_kitty_llmops_defaults(
    user_id: int,
    body: KittyUserDefaultsBody,
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict[str, Any]:
    """Update per-user Kitty defaults."""
    listen = normalize_listen_mode(body.listen_mode) if body.listen_mode is not None else None
    return await save_user_kitty_defaults(
        user_id,
        listen_mode=listen,
        tts_enabled=body.tts_enabled,
    )
