"""Admin user activity timeline endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Language, Messages
from services.admin.user_usage_activity import activity_to_admin_dict, list_user_usage_activities
from utils.auth.admin_scope import AdminScope, assert_panel_user_readable

from ..dependencies import get_language_dependency, require_global_users_read

router = APIRouter()


@router.get("/admin/users/{user_id}/activity")
async def list_user_activity_admin(
    user_id: int,
    scope: AdminScope = Depends(require_global_users_read),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None),
) -> dict[str, Any]:
    """Paginated curated activity timeline for one user (admin panel)."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", lang),
        )

    await assert_panel_user_readable(scope, user.organization_id, db, lang)

    if (
        source is not None
        and source.strip()
        and source.strip()
        not in (
            "mindgraph",
            "mindmate",
            "dingtalk",
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be mindgraph, mindmate, or dingtalk",
        )

    rows = await list_user_usage_activities(
        db,
        user_id,
        source=source,
        limit=limit,
        before_id=before_id,
    )
    items = [activity_to_admin_dict(row) for row in rows]
    return {
        "items": items,
        "hasMore": len(items) >= limit,
    }
