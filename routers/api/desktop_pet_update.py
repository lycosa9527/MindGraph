"""GET /api/desktop-pet/update — presigned zip for the logged-in server's COS prefix."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain.auth import User
from services.features.desktop_pet.update_manifest import load_update
from utils.auth import get_current_user

router = APIRouter(prefix="/desktop-pet", tags=["desktop-pet"])


@router.get("/update")
async def desktop_pet_update(
    platform: str = Query(..., pattern="^(windows|mac)$"),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Short-lived download for the newest pet build of this server's environment."""
    if not isinstance(current_user.id, int):
        raise HTTPException(status_code=401, detail="Login required")
    release = load_update(platform)
    if release is None:
        raise HTTPException(status_code=404, detail="No desktop pet build is published")
    return release
