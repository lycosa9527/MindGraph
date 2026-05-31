"""Shared organization resolution for school dashboard routes (admin + manager).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.messages import Language
from utils.auth import is_admin
from utils.auth.admin_scope import AdminScope, assert_panel_org_readable, resolve_effective_org_id


async def resolve_school_dashboard_org_id_scoped(
    scope: AdminScope,
    organization_id: Optional[int],
    db: AsyncSession,
    lang: Language,
) -> int:
    """Resolve school dashboard org and enforce invited-org read scope for BD / expert."""
    org_id = resolve_effective_org_id(
        scope,
        organization_id,
        lang,
        require_org_for_superadmin=is_admin(scope.actor),
    )
    await assert_panel_org_readable(scope, org_id, db, lang)
    return org_id
