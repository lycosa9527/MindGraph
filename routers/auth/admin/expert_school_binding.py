"""
Admin API: bind platform experts to a school.

GET/PUT /admin/organizations/{org_id}/expert-bindings

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.messages import Language, Messages
from routers.auth.dependencies import (
    get_async_db_with_request_rls as panel_db,
    get_language_dependency,
    require_global_organizations_edit,
    require_organizations_read,
)
from services.auth.expert_live_membership import refresh_expert_live_membership
from services.auth.expert_school_binding import (
    ExpertBindingError,
    apply_expert_school_binding,
    list_expert_school_binding,
)
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_panel_permissions import CAP_TAB_ORGANIZATIONS_EDIT
from utils.auth.admin_scope import AdminScope, assert_panel_org_readable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/organizations", tags=["Admin Expert Binding"])


class ExpertBindingOption(BaseModel):
    """One expert account in the school binding picker."""

    id: int
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class ExpertBindingResponse(BaseModel):
    """Experts bound to this school, and the picker rows the caller may see."""

    bound_user_ids: list[int]
    experts: list[ExpertBindingOption]


class ExpertBindingUpdate(BaseModel):
    """Replacement set of expert user ids for one school."""

    user_ids: list[int] = Field(default_factory=list, max_length=200)


def _binding_http_error(exc: ExpertBindingError, lang: Language, org_id: int) -> HTTPException:
    """Map a binding error onto an HTTP response."""
    if exc.code == "organization_not_found":
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", org_id, lang=lang),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Messages.error("invalid_request", lang=lang),
    )


@router.get("/{org_id}/expert-bindings", response_model=ExpertBindingResponse)
async def get_expert_school_binding(
    org_id: int,
    scope: AdminScope = Depends(require_organizations_read),
    db: AsyncSession = Depends(panel_db),
    lang: Language = Depends(get_language_dependency),
):
    """List experts bound to this school. Editors also receive every expert account."""
    await assert_panel_org_readable(scope, org_id, db, lang)
    try:
        payload = await list_expert_school_binding(
            db,
            org_id,
            include_all_experts=scope.has_capability(CAP_TAB_ORGANIZATIONS_EDIT),
        )
    except ExpertBindingError as exc:
        raise _binding_http_error(exc, lang, org_id) from exc
    except DATABASE_ERRORS as exc:
        logger.error("[ExpertBinding] Load failed for org %s: %s", org_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("invalid_request", lang=lang),
        ) from exc
    return payload


@router.put("/{org_id}/expert-bindings", response_model=ExpertBindingResponse)
async def put_expert_school_binding(
    org_id: int,
    body: ExpertBindingUpdate,
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(panel_db),
    lang: Language = Depends(get_language_dependency),
):
    """Replace this school's expert bindings. Other schools are left unchanged."""
    try:
        changed = await apply_expert_school_binding(db, org_id, body.user_ids)
        await refresh_expert_live_membership(changed)
        payload = await list_expert_school_binding(
            db,
            org_id,
            include_all_experts=scope.has_capability(CAP_TAB_ORGANIZATIONS_EDIT),
        )
    except ExpertBindingError as exc:
        raise _binding_http_error(exc, lang, org_id) from exc
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[ExpertBinding] Save failed for org %s: %s", org_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("invalid_request", lang=lang),
        ) from exc
    return payload
