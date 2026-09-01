"""Super-admin school dashboard feature-usage analytics.

GET /admin/stats/school/feature-usage

Panel RLS is pinned by ``require_panel_capability`` before the session opens.
This handler refreshes SET LOCAL after org resolve and never opens a system session.
School isolation is the current-member ``user_id`` list, not RLS global-read.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.messages import Language
from routers.auth.admin.school_scope import resolve_school_dashboard_org_id_scoped
from routers.auth.dependencies import (
    get_async_db_with_request_rls,
    get_language_dependency,
    require_panel_capability,
)
from services.admin.school_feature_usage_stats import build_school_feature_usage
from services.admin.school_feature_usage_types import SchoolFeatureUsagePayload
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_panel_permissions import CAP_TAB_SCHOOL_DASHBOARD_FEATURE_USAGE_VIEW
from utils.auth.admin_scope import AdminScope
from utils.db.rls_context import RlsContext, apply_rls_context_async, set_rls_context

router = APIRouter()


@router.get("/admin/stats/school/feature-usage")
async def get_school_feature_usage(
    request: Request,
    organization_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SCHOOL_DASHBOARD_FEATURE_USAGE_VIEW)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    lang: Language = Depends(get_language_dependency),
) -> SchoolFeatureUsagePayload:
    """Return selected-school module access, process, and judgement cards."""
    effective_org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    panel_ctx = replace(
        RlsContext.from_admin_scope(scope),
        organization_id=effective_org_id,
    )
    request.state.rls_context = panel_ctx
    set_rls_context(panel_ctx)
    await apply_rls_context_async(db, panel_ctx)
    try:
        return await build_school_feature_usage(db, effective_org_id, year)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid year",
        ) from exc
    except DATABASE_ERRORS as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load feature usage",
        ) from exc
