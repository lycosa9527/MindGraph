"""
Partial ``jsonb_set`` SQL for workshop live-spec DB flush.

``:name::jsonb`` is not a bind: SQLAlchemy's ``text()`` parser does not see
``val_nodes`` inside ``:val_nodes::jsonb``, so every flush fell back to a
full ``spec`` UPDATE. Use ``CAST(:name AS jsonb)`` instead.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import FrozenSet

from sqlalchemy import TextClause
from sqlalchemy import text as sql_text

PARTIAL_JSONB_FLUSH_KEYS = frozenset({"nodes", "connections"})


def build_partial_jsonb_flush_statement(changed_keys: FrozenSet[str]) -> TextClause:
    """
    UPDATE only the listed top-level spec keys.

    ``changed_keys`` must be a subset of ``PARTIAL_JSONB_FLUSH_KEYS``.
    """
    keys = sorted(key for key in changed_keys if key in PARTIAL_JSONB_FLUSH_KEYS)
    if not keys:
        raise ValueError("partial jsonb flush requires nodes and/or connections")
    expr = "COALESCE(spec, '{}'::jsonb)"
    for key in keys:
        expr = f"jsonb_set({expr}, '{{{key}}}', CAST(:val_{key} AS jsonb))"
    return sql_text(f"UPDATE diagrams SET spec = {expr} WHERE id = :diagram_id AND NOT is_deleted RETURNING id")
