"""Rotate the invitation code shown on the school dashboard.

School managers are locked to their own organization. Superadmins pass
``organization_id`` for the school they are previewing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from routers.auth.dependencies import (
    get_async_db_with_request_rls as panel_mutate_db,
    get_language_dependency,
    require_panel_capability,
)
from services.auth.rotate_invitation_code import rotate_organization_invitation_code
from utils.auth.admin_panel_permissions import CAP_TAB_USERS_EDIT
from utils.auth.admin_scope import AdminScope

from .school_scope import resolve_school_dashboard_org_id_scoped

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/admin/school/invitation-code/rotate")
async def rotate_school_invitation_code(
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(panel_mutate_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Issue a new school invitation code and retire the current one."""
    current_user = scope.actor
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )

    new_code = await rotate_organization_invitation_code(db, org, lang)
    logger.info(
        "User %s rotated invitation code for org %s",
        current_user.phone,
        org.code,
    )
    return {
        "id": org.id,
        "invitation_code": new_code,
    }
