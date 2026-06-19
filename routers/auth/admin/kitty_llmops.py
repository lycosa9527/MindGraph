"""
Admin: Kitty architecture manifest (LLMOps tab).

Access: super-admin only. Prefer ``require_panel_capability(CAP_SETTINGS_KITTY_LLMOPS)``
over ``require_admin`` when migrating (dependencies.py cookbook).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from routers.auth.dependencies import require_settings_kitty_llmops
from utils.auth.admin_scope import AdminScope
from services.kitty.http.llmops_manifest import build_kitty_llmops_manifest

router = APIRouter()


@router.get("/admin/kitty-llmops/architecture")
async def get_kitty_llmops_architecture(
    _scope: AdminScope = Depends(require_settings_kitty_llmops),
) -> dict:
    """Return Kitty module map + hub contract for the admin LLMOps tab."""
    return build_kitty_llmops_manifest()
