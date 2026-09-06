"""Permissions for org training follow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.features.training.permissions import (
    can_delete_training_course,
    can_edit_training_course,
    can_lead_any_training,
    can_lead_training,
    is_org_teacher_target,
)
from utils.auth.roles import FEATURE_KEY_TO_CONFIG_ATTR, FEATURE_KEYS_WITH_ORG_ACCESS


def _user(role: str, *, user_id: int = 1, org_id: int | None = 10) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role=role, organization_id=org_id, name=role)


def test_training_flag_is_global_only() -> None:
    """FEATURE_TRAINING is mapped and not org-grant gated in v1."""
    assert FEATURE_KEY_TO_CONFIG_ATTR["feature_training"] == "FEATURE_TRAINING"
    assert "feature_training" not in FEATURE_KEYS_WITH_ORG_ACCESS


def test_teacher_is_org_target_and_cannot_lead() -> None:
    """School teachers are pulled; they cannot host."""
    teacher = _user("teacher", org_id=10)
    assert is_org_teacher_target(teacher, 10) is True
    assert is_org_teacher_target(teacher, 11) is False
    assert can_lead_any_training(teacher) is False


def test_legacy_user_role_is_teacher_target() -> None:
    """Legacy user role is treated as a teacher."""
    assert is_org_teacher_target(_user("user", org_id=4), 4) is True


def test_school_admin_is_not_pulled() -> None:
    """school_admin is not a teacher target."""
    admin = _user("school_admin", org_id=10)
    assert is_org_teacher_target(admin, 10) is False
    assert can_lead_any_training(admin) is False


def test_platform_staff_are_not_teacher_targets() -> None:
    """Visiting staff are not pulled as org teachers."""
    assert is_org_teacher_target(_user("superadmin", org_id=None), 10) is False
    assert is_org_teacher_target(_user("platform_bd", org_id=None), 10) is False
    assert is_org_teacher_target(_user("expert", org_id=None), 10) is False


def test_superadmin_and_bd_may_lead_any_org() -> None:
    """Superadmin and platform BD may lead any school."""
    assert can_lead_any_training(_user("superadmin", org_id=None)) is True
    assert can_lead_any_training(_user("platform_bd", org_id=None)) is True


@pytest.mark.asyncio
async def test_expert_cannot_lead_non_invited_org() -> None:
    """Experts may lead invited orgs only."""
    expert = _user("expert", user_id=9, org_id=None)
    with patch(
        "services.features.training.permissions.load_expert_invited_org_ids",
        new=AsyncMock(return_value={22}),
    ):
        assert await can_lead_training(expert, 99) is False
        assert await can_lead_training(expert, 22) is True


@pytest.mark.asyncio
async def test_teacher_cannot_lead_own_org() -> None:
    """Teachers cannot start or steer."""
    teacher = _user("teacher", org_id=10)
    assert await can_lead_training(teacher, 10) is False


def test_shared_catalog_edit_and_owned_delete() -> None:
    """Visiting staff share edits; experts delete only their own drafts."""
    draft = SimpleNamespace(is_system=False, owner_id=9)
    seed = SimpleNamespace(is_system=True, owner_id=None)
    expert = _user("expert", user_id=9)
    other = _user("expert", user_id=8)
    admin = _user("superadmin", user_id=1)
    assert can_edit_training_course(expert) is True
    assert can_delete_training_course(expert, draft) is True
    assert can_delete_training_course(other, draft) is False
    assert can_delete_training_course(admin, draft) is True
    assert can_delete_training_course(admin, seed) is False
