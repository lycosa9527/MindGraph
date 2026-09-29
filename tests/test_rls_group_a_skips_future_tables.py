"""Revisions 0044–0046 must not touch tables created by later migrations."""

from utils.db_rls import policy_builder


class _Inspector:
    """Report only the tables present on an upgraded database at revision 0043."""

    def __init__(self, present: set[str]) -> None:
        self._present = present

    def has_table(self, table_name: str, schema: str | None = None) -> bool:
        """Match SQLAlchemy's inspector signature."""
        return table_name in self._present and schema in (None, "public")


def test_upgrade_group_a_skips_tables_created_after_0044(monkeypatch) -> None:
    """user_usage_activities and kitty tables receive RLS in their own revisions."""
    executed: list[str] = []
    present = {"diagrams"}
    inspector = _Inspector(present)

    def _bind() -> object:
        return object()

    def _inspect(_bind_arg: object) -> _Inspector:
        return inspector

    def _execute(statement: object) -> None:
        executed.append(str(statement))

    monkeypatch.setattr(policy_builder.op, "get_bind", _bind)
    monkeypatch.setattr(policy_builder.sa, "inspect", _inspect)
    monkeypatch.setattr(policy_builder.op, "execute", _execute)

    policy_builder.upgrade_group_a()

    sql = "\n".join(executed)
    assert 'ALTER TABLE "diagrams" ENABLE ROW LEVEL SECURITY' in sql
    assert "user_usage_activities" not in sql
    assert "kitty_one_sentence_sessions" not in sql
    assert "kitty_one_sentence_turns" not in sql


def test_upgrade_group_cde_skips_missing_community_tables(monkeypatch) -> None:
    """Group C custom policies must not ALTER a community table that is not created yet."""
    executed: list[str] = []
    inspector = _Inspector({"users", "organizations"})

    def _bind() -> object:
        return object()

    def _inspect(_bind_arg: object) -> _Inspector:
        return inspector

    def _execute(statement: object) -> None:
        executed.append(str(statement))

    monkeypatch.setattr(policy_builder.op, "get_bind", _bind)
    monkeypatch.setattr(policy_builder.sa, "inspect", _inspect)
    monkeypatch.setattr(policy_builder.op, "execute", _execute)

    policy_builder.upgrade_group_cde()

    sql = "\n".join(executed)
    assert 'ALTER TABLE "users" ENABLE ROW LEVEL SECURITY' in sql
    assert "community_posts" not in sql
    assert "library_documents" not in sql
    assert "market_listings" not in sql
