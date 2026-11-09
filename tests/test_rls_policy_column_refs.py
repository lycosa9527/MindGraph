"""Every RLS policy expression must reference columns that exist on the target table."""

from __future__ import annotations

import re

from models.domain.registry import Base
from utils.db.alembic_migration import load_rls_policy_builder
from utils.db_rls.split_policies import EMBEDDINGS_READ_EXPR, EMBEDDINGS_WRITE_EXPR

_RLS_FUNC_ARG = re.compile(r"rls_\w+\((\w+)\)")
_EXISTS_FK = re.compile(r"\.\w+\s*=\s*([a-z_][a-z0-9_]*)(?!\.)\b")
_COMPARE_COL = re.compile(r"(?<![.\w])(\w+)\s*=\s*rls_")

# Leftover tables still have RLS policies after their ORM models were removed.
# Values are the columns those policies reference.
_LEFTOVER_TABLE_COLUMNS: dict[str, set[str]] = {
    "debate_sessions": {"user_id"},
    "debate_participants": {"session_id"},
    "debate_messages": {"session_id"},
    "debate_judgments": {"session_id"},
    "gewe_messages": set(),
    "gewe_contacts": set(),
    "gewe_group_members": set(),
    "community_posts": {"author_id"},
    "community_post_likes": {"user_id"},
    "community_post_comments": {"user_id"},
}


def _table_columns(table_name: str) -> set[str]:
    """Table columns."""
    table = Base.metadata.tables.get(table_name)
    if table is not None:
        return {column.name for column in table.columns}
    leftover = _LEFTOVER_TABLE_COLUMNS.get(table_name)
    assert leftover is not None, f"unknown RLS table: {table_name}"
    return leftover


def _collect_policy_errors(table_name: str, expr: str, columns: set[str]) -> list[str]:
    """Collect policy errors."""
    errors: list[str] = []
    for column in _RLS_FUNC_ARG.findall(expr):
        if column not in columns:
            errors.append(f"{table_name}: rls_*({column}) — column missing")
    for column in _EXISTS_FK.findall(expr):
        if column.startswith("rls_"):
            continue
        if column not in columns:
            errors.append(f"{table_name}: EXISTS join on {column} — column missing")
    for column in _COMPARE_COL.findall(expr):
        if column not in columns:
            errors.append(f"{table_name}: {column} = rls_* — column missing")
    return errors


def test_all_rls_policy_expressions_reference_real_columns():
    """Test all rls policy expressions reference real columns."""
    builder = load_rls_policy_builder()
    errors: list[str] = []
    for table_name, expr in builder.iter_all_table_policies():
        errors.extend(_collect_policy_errors(table_name, expr, _table_columns(table_name)))
    assert not errors, "RLS policy column mismatches:\n" + "\n".join(errors)


def test_token_usage_is_own_rows_for_teachers():
    """Teachers read and write their own usage rows; school totals need a panel session."""
    builder = load_rls_policy_builder()
    expr = dict(builder.iter_all_table_policies())["token_usage"]
    assert "user_id = rls_current_user_id()" in expr
    assert "(rls_is_panel_mode() OR rls_is_mindbot_service_mode()) AND rls_org_visible(organization_id)" in expr
    assert not expr.startswith("rls_org_visible(organization_id) OR")


def test_seminar_file_policy_does_not_treat_hidden_members_as_open():
    """Closed-room visibility is a definer function, not a member-table probe."""
    builder = load_rls_policy_builder()
    expr = builder.MINDMATE_COLLAB_FILE_EXPR
    assert "NOT EXISTS" not in expr
    assert "mindmate_seminar_members" not in expr
    assert "rls_seminar_session_visible(session_id)" in expr


def test_knowledge_embeddings_not_document_scoped():
    """The shared embedding cache is readable when signed in and written only by system mode."""
    assert "document_id" not in EMBEDDINGS_READ_EXPR
    assert "rls_community_read_allowed()" in EMBEDDINGS_READ_EXPR
    assert EMBEDDINGS_WRITE_EXPR == "rls_is_system_mode()"
