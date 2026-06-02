"""SQL to create mindgraph_app / mindgraph_migrate roles (rev 0043 + bootstrap)."""

from __future__ import annotations

from alembic.rls_functions_sql import build_grant_rls_functions_to_app_sql


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def build_create_roles_sql(app_password: str, migrate_password: str) -> str:
    """Create login roles when missing (requires CREATEROLE or superuser)."""
    app_pw = _sql_escape(app_password)
    migrate_pw = _sql_escape(migrate_password)
    return f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
        CREATE ROLE mindgraph_app LOGIN PASSWORD '{app_pw}';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate') THEN
        CREATE ROLE mindgraph_migrate LOGIN PASSWORD '{migrate_pw}' BYPASSRLS;
    ELSIF NOT COALESCE(
        (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'mindgraph_migrate'),
        false
    ) THEN
        ALTER ROLE mindgraph_migrate BYPASSRLS;
    END IF;
END $$;
"""


def build_grants_sql() -> str:
    """Grant schema/table access to RLS roles (safe to re-run)."""
    return """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
        GRANT USAGE ON SCHEMA public TO mindgraph_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mindgraph_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mindgraph_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mindgraph_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO mindgraph_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate') THEN
        GRANT ALL PRIVILEGES ON SCHEMA public TO mindgraph_migrate;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mindgraph_migrate;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mindgraph_migrate;
    END IF;
END $$;
""" + build_grant_rls_functions_to_app_sql()


def build_ensure_migrate_bypassrls_sql() -> str:
    """Apply BYPASSRLS to mindgraph_migrate only when missing (superuser-only ALTER)."""
    return """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate')
       AND NOT COALESCE(
           (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'mindgraph_migrate'),
           false
       ) THEN
        ALTER ROLE mindgraph_migrate BYPASSRLS;
    END IF;
END $$;
"""


def build_migrate_database_privileges_sql() -> str:
    """
    Let mindgraph_migrate run DDL on the current database (Alembic / CREATE SCHEMA).

    Must run as a superuser (e.g. sudo -u postgres psql), not as mindgraph_migrate.
    """
    return """
DO $$
DECLARE
    dbname text := current_database();
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate') THEN
        EXECUTE format('GRANT CREATE ON DATABASE %I TO mindgraph_migrate', dbname);
        EXECUTE format('ALTER DATABASE %I OWNER TO mindgraph_migrate', dbname);
    END IF;
END $$;
"""


def build_reassign_public_objects_to_migrate_sql() -> str:
    """
    Move legacy-owned public objects to mindgraph_migrate (required before RLS DDL in 0044+).

    Uses ``REASSIGN OWNED BY mindgraph_user`` (and mindgraph_app when present), then
    per-object ``ALTER … OWNER`` for remaining public tables.  Never ``REASSIGN OWNED BY
    postgres`` — that hits database-system objects and fails.
    Must run as superuser (sudo -u postgres psql).
    """
    return """
DO $$
DECLARE
    role_name text;
    obj RECORD;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate') THEN
        RETURN;
    END IF;

    FOREACH role_name IN ARRAY ARRAY['mindgraph_user', 'mindgraph_app']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REASSIGN OWNED BY %I TO mindgraph_migrate', role_name);
        END IF;
    END LOOP;

    FOR obj IN
        SELECT c.relname AS obj_name,
               CASE c.relkind
                   WHEN 'S' THEN 'SEQUENCE'
                   WHEN 'v' THEN 'VIEW'
                   WHEN 'm' THEN 'MATERIALIZED VIEW'
                   ELSE 'TABLE'
               END AS obj_kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'S', 'v', 'm')
          AND pg_get_userbyid(c.relowner) IS DISTINCT FROM 'mindgraph_migrate'
    LOOP
        EXECUTE format(
            'ALTER %s public.%I OWNER TO mindgraph_migrate',
            obj.obj_kind,
            obj.obj_name
        );
    END LOOP;

    ALTER SCHEMA public OWNER TO mindgraph_migrate;
END $$;
"""


def build_ensure_postgresql_extensions_sql() -> str:
    """
    Optional observability / search extensions (same as Alembic rev 0031).

    Requires superuser; run via sudo -u postgres psql on the app database.
    """
    return """
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
"""
