"""Shared role ordering for admin/school org member lists.

Order: 超级管理员 → 学校管理员 → 专家 → 教研员 → 学校版 (teacher).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import case
from sqlalchemy.sql.elements import ColumnElement

from models.domain.auth import User
from utils.auth.role_constants import (
    LEGACY_ROLE_ADMIN,
    LEGACY_ROLE_MANAGER,
    LEGACY_ROLE_USER,
    ROLE_EXPERT,
    ROLE_PLATFORM_BD,
    ROLE_SCHOOL_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
)

# 超级管理员 → 学校管理员 → 专家 → 教研员 → 学校版
_ORG_MEMBER_ROLE_SORT_RANK: tuple[tuple[tuple[str, ...], int], ...] = (
    ((ROLE_SUPERADMIN, LEGACY_ROLE_ADMIN), 0),
    ((ROLE_SCHOOL_ADMIN, LEGACY_ROLE_MANAGER), 1),
    ((ROLE_EXPERT,), 2),
    ((ROLE_PLATFORM_BD,), 3),
    ((ROLE_TEACHER, LEGACY_ROLE_USER), 4),
)


def org_member_role_sort_key() -> ColumnElement[int]:
    """SQL CASE rank for organization member lists (school dashboard / school modal)."""
    whens = [(User.role.in_(roles), rank) for roles, rank in _ORG_MEMBER_ROLE_SORT_RANK]
    return case(*whens, else_=5)
