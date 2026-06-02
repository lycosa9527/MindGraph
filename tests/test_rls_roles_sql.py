"""RLS role SQL helpers."""

from utils.db.alembic_migration import load_rls_roles_sql

_roles_sql = load_rls_roles_sql()
build_create_roles_sql = _roles_sql.build_create_roles_sql
build_grants_sql = _roles_sql.build_grants_sql
build_migrate_database_privileges_sql = _roles_sql.build_migrate_database_privileges_sql
build_reassign_public_objects_to_migrate_sql = (
    _roles_sql.build_reassign_public_objects_to_migrate_sql
)
build_ensure_postgresql_extensions_sql = _roles_sql.build_ensure_postgresql_extensions_sql


def test_create_roles_sql_includes_both_roles():
    sql = build_create_roles_sql("app_pw", "migrate_pw")
    assert "mindgraph_app" in sql
    assert "mindgraph_migrate" in sql
    assert "BYPASSRLS" in sql


def test_create_roles_sql_skips_alter_bypassrls_when_already_set():
    """Alembic 0043 runs as mindgraph_migrate; must not ALTER self when BYPASSRLS is set."""
    sql = build_create_roles_sql("app_pw", "migrate_pw")
    assert "ELSIF NOT COALESCE" in sql
    assert "rolbypassrls" in sql
    assert "ELSE\n        ALTER ROLE mindgraph_migrate BYPASSRLS" not in sql


def test_grants_sql_targets_both_roles():
    sql = build_grants_sql()
    assert "mindgraph_app" in sql
    assert "mindgraph_migrate" in sql


def test_migrate_database_privileges_sql():
    sql = build_migrate_database_privileges_sql()
    assert "mindgraph_migrate" in sql
    assert "ALTER DATABASE" in sql
    assert "current_database()" in sql


def test_ensure_postgresql_extensions_sql():
    sql = build_ensure_postgresql_extensions_sql()
    assert "pg_stat_statements" in sql
    assert "pg_trgm" in sql
    assert "CREATE EXTENSION IF NOT EXISTS" in sql


def test_reassign_public_objects_sql():
    sql = build_reassign_public_objects_to_migrate_sql()
    assert "REASSIGN OWNED BY" in sql
    assert "mindgraph_user" in sql
    assert "mindgraph_migrate" in sql
    assert "REASSIGN OWNED BY postgres TO" not in sql
    assert "ALTER %s public.%I OWNER TO mindgraph_migrate" in sql
