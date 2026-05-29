"""Shared organization resolution for school dashboard routes (admin + manager).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from models.domain.auth import User
from models.domain.messages import Language
from utils.auth import is_admin
from utils.auth.admin_scope import build_admin_scope, resolve_effective_org_id


def resolve_school_dashboard_org_id(
    organization_id: Optional[int],
    current_user: User,
    lang: Language,
) -> int:
    """
    Enforce school-dashboard org scope via AdminScope.

    Superadmin must pass organization_id; school_admin is locked to their org.
    """
    scope = build_admin_scope(current_user, organization_id=organization_id, lang=lang)
    return resolve_effective_org_id(
        scope,
        organization_id,
        lang,
        require_org_for_superadmin=is_admin(current_user),
    )
