"""
Access ``db_rls`` helpers (formerly registered under the PyPI ``alembic`` namespace).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from types import ModuleType

import db_rls.policy_builder as _policy_builder
import db_rls.roles_sql as _roles_sql


def load_rls_policy_builder() -> ModuleType:
    """Return the ``db_rls.policy_builder`` module."""
    return _policy_builder


def load_rls_roles_sql() -> ModuleType:
    """Return the ``db_rls.roles_sql`` module."""
    return _roles_sql
