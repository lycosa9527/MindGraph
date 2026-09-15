"""
JSONB flush SQL for workshop live-spec DB writes.

``:name::jsonb`` is not a bind: SQLAlchemy's ``text()`` parser does not see
``val_nodes`` inside ``:val_nodes::jsonb``, so every flush fell back to a
full ``spec`` UPDATE. Use ``CAST(:name AS jsonb)`` instead.

A leftover full-flush path bound ``json.dumps(snapshot)`` through the ORM
JSONB type, which stored a JSON *string* scalar. ``jsonb_set`` then failed
with ``cannot set path in scalar``. Full flush now CAST-parses the dumped
text into an object; partial flush unwraps leftover scalars first.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import FrozenSet

from sqlalchemy import TextClause
from sqlalchemy import text as sql_text

PARTIAL_JSONB_FLUSH_KEYS = frozenset({"nodes", "connections"})

# Unwrap leftover JSON-string scalars so jsonb_set sees an object.
JSONB_SPEC_AS_OBJECT_SQL = (
    "CASE "
    "WHEN spec IS NULL THEN '{}'::jsonb "
    "WHEN jsonb_typeof(spec) = 'object' THEN spec "
    "WHEN jsonb_typeof(spec) = 'string' THEN (spec #>> '{}')::jsonb "
    "ELSE '{}'::jsonb "
    "END"
)


def build_full_jsonb_flush_statement() -> TextClause:
    """Replace the whole ``spec`` column with CAST-parsed JSON text."""
    return sql_text(
        "UPDATE diagrams SET spec = CAST(:p_spec AS jsonb) WHERE id = :p_id AND NOT is_deleted RETURNING id"
    )


def build_partial_jsonb_flush_statement(changed_keys: FrozenSet[str]) -> TextClause:
    """
    UPDATE only the listed top-level spec keys.

    ``changed_keys`` must be a subset of ``PARTIAL_JSONB_FLUSH_KEYS``.
    """
    keys = sorted(key for key in changed_keys if key in PARTIAL_JSONB_FLUSH_KEYS)
    if not keys:
        raise ValueError("partial jsonb flush requires nodes and/or connections")
    expr = JSONB_SPEC_AS_OBJECT_SQL
    for key in keys:
        expr = f"jsonb_set({expr}, '{{{key}}}', CAST(:val_{key} AS jsonb))"
    return sql_text(f"UPDATE diagrams SET spec = {expr} WHERE id = :diagram_id AND NOT is_deleted RETURNING id")
