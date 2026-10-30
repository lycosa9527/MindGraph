"""GET /api/mindmate/seminar/unread-summary for the desktop pet badge."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from models.domain.auth import User
from models.domain.messages import Language
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_seminar.unread_summary import summarize_live_unread
from utils.auth import get_current_user, user_has_feature_access
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter(prefix="/mindmate/seminar", tags=["mindmate-seminar"])


@router.get("/unread-summary")
async def seminar_unread_summary(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, object]:
    """How many seminar lines this person has not read, across live rooms they can enter."""
    if not await user_has_feature_access(current_user, "feature_mindmate_seminar"):
        raise HTTPException(status_code=404, detail="Feature is disabled")
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(db, current_user, TIER_FEATURE_ONLINE_COLLAB, lang)
    return await summarize_live_unread(current_user.id)
