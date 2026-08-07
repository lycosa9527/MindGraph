"""ZhiHui access control: CAP_FEATURE_ZHIHUI is superadmin-only."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.auth.admin_panel_permissions import (
    CAP_FEATURE_ZHIHUI,
    ROLE_PANEL_CAPABILITIES,
    user_panel_capabilities,
)
from utils.auth.role_constants import (
    ROLE_EXPERT,
    ROLE_PLATFORM_BD,
    ROLE_SCHOOL_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
)


def test_zhihui_capability_superadmin_only() -> None:
    """School managers / teachers / BD / expert must not receive feature.zhihui."""
    assert CAP_FEATURE_ZHIHUI in ROLE_PANEL_CAPABILITIES[ROLE_SUPERADMIN]
    for role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER, ROLE_PLATFORM_BD, ROLE_EXPERT):
        assert CAP_FEATURE_ZHIHUI not in ROLE_PANEL_CAPABILITIES[role]


def test_user_panel_capabilities_teacher_excludes_zhihui() -> None:
    """Teacher role must not get feature.zhihui via user_panel_capabilities."""
    user = MagicMock()
    user.role = ROLE_TEACHER
    assert CAP_FEATURE_ZHIHUI not in user_panel_capabilities(user)


def test_user_panel_capabilities_superadmin_includes_zhihui() -> None:
    """Superadmin receives feature.zhihui via user_panel_capabilities."""
    user = MagicMock()
    user.role = ROLE_SUPERADMIN
    assert CAP_FEATURE_ZHIHUI in user_panel_capabilities(user)
