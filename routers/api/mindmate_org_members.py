"""
School roster for MindMate seminar member pickers.

This path is intentionally outside ``/api/mindmate/seminar`` and ``/api/chat``.
Those prefixes are feature-gated, so a signed-in teacher with colleagues could
not open the seminar member dialog while collab or workshop chat was off.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.workshop_chat.dependencies import resolve_social_org_id
from services.features.org_member_models import OrgMembersPage
from services.features.org_member_roster import fetch_org_members_page
from utils.auth import get_current_user

router = APIRouter(tags=["mindmate"])


@router.get("/mindmate/org-members", response_model=OrgMembersPage)
async def list_mindmate_org_members(
    request: Request,
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> OrgMembersPage:
    """List the caller's school colleagues, including the caller."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "mindmate_org_members",
        identifier,
        max_requests=60,
        window_seconds=60,
    )
    effective_org_id = await resolve_social_org_id(db, current_user, None)
    return await fetch_org_members_page(
        db,
        effective_org_id,
        q=q or "",
        limit=limit,
        offset=offset,
    )
