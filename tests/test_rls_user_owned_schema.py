"""USER_OWNED_TABLES must expose a user_id column on the ORM model."""

from models.domain.registry import Base
from utils.db.alembic_migration import load_rls_policy_builder

builder = load_rls_policy_builder()


def test_user_owned_tables_have_user_id_column():
    missing = []
    for table_name in builder.USER_OWNED_TABLES:
        table = Base.metadata.tables.get(table_name)
        assert table is not None, f"unknown table in USER_OWNED_TABLES: {table_name}"
        if "user_id" not in table.c:
            missing.append(table_name)
    assert not missing, f"USER_OWNED_TABLES without user_id column: {missing}"


def test_child_tables_not_in_user_owned():
    child_tables = {t for t, _ in builder.DEBATE_CHILD_TABLES}
    child_tables.update(t for t, _ in builder.MARKET_CHILD_TABLES)
    child_tables.update(t for t, _ in builder.KNOWLEDGE_SPACE_CHILD_TABLES)
    child_tables.update(builder.GEWE_TABLES)
    child_tables.add("devices")
    overlap = child_tables & set(builder.USER_OWNED_TABLES)
    assert not overlap, f"child/admin tables incorrectly listed as user-owned: {overlap}"
