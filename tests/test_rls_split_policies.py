"""Tables whose read rule is wider than their write rule get four policies."""

from __future__ import annotations

from utils.db_rls import split_policies
from utils.db_rls.policy_builder import USER_OWNED_TABLES, all_rls_tables, iter_all_table_policies


class _Inspector:
    """Report a fixed set of public tables."""

    def __init__(self, present: set[str]) -> None:
        self._present = present

    def has_table(self, table_name: str, schema: str | None = None) -> bool:
        """Match SQLAlchemy's inspector signature."""
        return table_name in self._present and schema in (None, "public")


def _run_upgrade(monkeypatch, present: set[str]) -> str:
    executed: list[str] = []

    def _bind() -> object:
        return object()

    def _inspect(_bind_arg: object) -> _Inspector:
        return _Inspector(present)

    def _execute(statement: object) -> None:
        executed.append(str(statement))

    monkeypatch.setattr(split_policies.op, "get_bind", _bind)
    monkeypatch.setattr(split_policies.sa, "inspect", _inspect)
    monkeypatch.setattr(split_policies.op, "execute", _execute)
    split_policies.upgrade_split_policies()
    return "\n".join(executed)


def test_diagram_share_and_workshop_are_read_only() -> None:
    """Share recipients and workshop joiners read the diagram; only the owner writes it."""
    assert "rls_diagram_shared_with_current_user(id)" in split_policies.DIAGRAM_READ_EXPR
    assert "rls_diagram_workshop_visible" in split_policies.DIAGRAM_READ_EXPR
    assert split_policies.DIAGRAM_WRITE_EXPR == "rls_diagram_visible(user_id)"


def test_upgrade_replaces_single_policy_with_four(monkeypatch) -> None:
    """The old FOR ALL policy is dropped and select/insert/update/delete are created."""
    sql = _run_upgrade(monkeypatch, {"diagrams"})
    assert 'DROP POLICY IF EXISTS "diagrams_tenant" ON "diagrams"' in sql
    assert 'CREATE POLICY "diagrams_select" ON "diagrams" FOR SELECT' in sql
    assert 'CREATE POLICY "diagrams_write" ON "diagrams" FOR INSERT WITH CHECK (rls_diagram_visible(user_id))' in sql
    assert 'CREATE POLICY "diagrams_update" ON "diagrams" FOR UPDATE USING (rls_diagram_visible(user_id))' in sql
    assert 'CREATE POLICY "diagrams_delete" ON "diagrams" FOR DELETE USING (rls_diagram_visible(user_id))' in sql
    assert "FOR ALL" not in sql


def test_upgrade_skips_missing_tables(monkeypatch) -> None:
    """A table created by a later revision is left alone."""
    sql = _run_upgrade(monkeypatch, {"embeddings"})
    assert '"embeddings_select"' in sql
    assert "diagrams" not in sql
    assert "teacher_usage_config" not in sql


def test_split_tables_are_not_also_in_for_all_groups() -> None:
    """A split table must not get a second, wider FOR ALL policy from the group builders."""
    split = set(split_policies.split_policy_tables())
    assert not split & set(USER_OWNED_TABLES)
    assert all_rls_tables().count("diagrams") == 1
    exprs = [expr for table, expr in iter_all_table_policies() if table == "teacher_usage_config"]
    assert exprs == [
        split_policies.TEACHER_USAGE_CONFIG_READ_EXPR,
        split_policies.TEACHER_USAGE_CONFIG_WRITE_EXPR,
    ]
