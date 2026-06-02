"""Every RLS policy expression must reference columns that exist on the target table."""

from __future__ import annotations

import re

from models.domain.registry import Base
from utils.db.alembic_migration import load_rls_policy_builder

_RLS_FUNC_ARG = re.compile(r"rls_\w+\((\w+)\)")
_EXISTS_FK = re.compile(r"\.\w+\s*=\s*([a-z_][a-z0-9_]*)(?!\.)\b")
_COMPARE_COL = re.compile(r"(\w+)\s*=\s*rls_")


def _table_columns(table_name: str) -> set[str]:
    table = Base.metadata.tables.get(table_name)
    assert table is not None, f"unknown RLS table: {table_name}"
    return {column.name for column in table.columns}


def _collect_policy_errors(table_name: str, expr: str, columns: set[str]) -> list[str]:
    errors: list[str] = []
    for column in _RLS_FUNC_ARG.findall(expr):
        if column not in columns:
            errors.append(f"{table_name}: rls_*({column}) — column missing")
    for column in _EXISTS_FK.findall(expr):
        if column not in columns:
            errors.append(f"{table_name}: EXISTS join on {column} — column missing")
    for column in _COMPARE_COL.findall(expr):
        if column not in columns:
            errors.append(f"{table_name}: {column} = rls_* — column missing")
    return errors


def test_all_rls_policy_expressions_reference_real_columns():
    builder = load_rls_policy_builder()
    errors: list[str] = []
    for table_name, expr in builder.iter_all_table_policies():
        errors.extend(_collect_policy_errors(table_name, expr, _table_columns(table_name)))
    assert not errors, "RLS policy column mismatches:\n" + "\n".join(errors)


def test_knowledge_embeddings_not_document_scoped():
    builder = load_rls_policy_builder()
    embedding_expr = dict(builder.KNOWLEDGE_SPACE_CHILD_TABLES)["embeddings"]
    assert "document_id" not in embedding_expr
    assert builder.EMBEDDINGS_EXPR in embedding_expr
