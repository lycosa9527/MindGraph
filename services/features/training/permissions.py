"""
Training follow permission helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from utils.auth.expert_invited_org_ids import load_expert_invited_org_ids
from utils.auth.role_constants import TEACHER_ROLES
from utils.auth.roles import is_expert, is_platform_bd, is_superadmin, is_teacher


def is_org_teacher_target(user: object, org_id: int) -> bool:
    """True when the user is a school teacher in this organization."""
    if not is_teacher(user):
        return False
    user_org = getattr(user, "organization_id", None)
    if user_org is None:
        return False
    return int(user_org) == int(org_id)


def teacher_role_filter_values() -> frozenset[str]:
    """Role slugs stored on teacher rows (canonical + legacy)."""
    return TEACHER_ROLES


def can_lead_any_training(user: object) -> bool:
    """True when the account is visiting staff that may host training."""
    return is_superadmin(user) or is_platform_bd(user) or is_expert(user)


async def can_lead_training(user: object, org_id: int) -> bool:
    """Visiting staff who may start or steer a session for this org."""
    if is_superadmin(user) or is_platform_bd(user):
        return True
    if not is_expert(user):
        return False
    invited = await load_expert_invited_org_ids(int(getattr(user, "id")))
    return int(org_id) in invited


def can_edit_training_course(user: object) -> bool:
    """Shared catalog: any visiting lead may author."""
    return can_lead_any_training(user)


def can_delete_training_course(user: object, course: object) -> bool:
    """System courses stay; experts delete only their own drafts."""
    if getattr(course, "is_system", False):
        return False
    if not can_lead_any_training(user):
        return False
    if is_superadmin(user) or is_platform_bd(user):
        return True
    owner_id = getattr(course, "owner_id", None)
    user_id = getattr(user, "id", None)
    if owner_id is None or user_id is None:
        return False
    return int(owner_id) == int(user_id)
