"""Shared organization resolution for school dashboard routes (admin + manager).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional
import logging

from fastapi import HTTPException, status

from models.domain.auth import User
from models.domain.messages import Language, Messages
from services.auth.school_dashboard_logger import school_dashboard_extra
from services.auth.security_logger import security_log
from utils.auth import is_admin

logger = logging.getLogger(__name__)


def resolve_school_dashboard_org_id(
    organization_id: Optional[int],
    current_user: User,
    lang: Language,
) -> int:
    """
    Enforce school-dashboard org scope: admins must pass ``organization_id`` (any
    school); managers are fixed to ``current_user.organization_id`` and get 403 if
    they pass a different ``organization_id`` query param.
    """
    if is_admin(current_user):
        if organization_id is None:
            logger.warning(
                "[SchoolDashboard] admin request missing organization_id",
                extra=school_dashboard_extra(
                    event="school_scope_admin_org_required",
                    actor_id=current_user.id,
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("school_dashboard_admin_org_required", lang=lang),
            )
        return organization_id
    effective = current_user.organization_id
    if effective is None:
        logger.warning(
            "[SchoolDashboard] manager has no organization",
            extra=school_dashboard_extra(
                event="school_scope_manager_no_org",
                actor_id=current_user.id,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("school_dashboard_manager_no_org", lang=lang),
        )
    if organization_id is not None and organization_id != effective:
        security_log.access_denied(
            user_id=current_user.id,
            resource="school_dashboard_organization",
            reason="manager_org_mismatch",
            ip=None,
        )
        logger.warning(
            "[SchoolDashboard] manager attempted cross-organization access",
            extra=school_dashboard_extra(
                event="school_scope_manager_org_mismatch",
                actor_id=current_user.id,
                org_id=effective,
                sd_requested_org_id=organization_id,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("school_dashboard_manager_cross_org_forbidden", lang=lang),
        )
    return effective
