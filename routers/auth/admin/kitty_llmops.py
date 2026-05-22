"""Admin: Kitty architecture manifest (LLMOps tab)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from models.domain.auth import User
from routers.auth.dependencies import require_admin
from services.kitty.http.llmops_manifest import build_kitty_llmops_manifest

router = APIRouter()


@router.get("/admin/kitty-llmops/architecture")
async def get_kitty_llmops_architecture(_admin: User = Depends(require_admin)) -> dict:
    """Return Kitty module map + hub contract for the admin LLMOps tab."""

    _ = _admin
    return build_kitty_llmops_manifest()
