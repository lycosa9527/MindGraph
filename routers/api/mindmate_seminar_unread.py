"""GET /api/mindmate/seminar/unread-summary for the desktop pet badge."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from models.domain.auth import User
from services.features.mindmate_seminar.unread_summary import summarize_live_unread
from utils.auth import get_current_user

router = APIRouter(prefix="/mindmate/seminar", tags=["mindmate-seminar"])


@router.get("/unread-summary")
async def seminar_unread_summary(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """How many seminar lines this person has not read, across live rooms they can enter."""
    return await summarize_live_unread(current_user.id)
