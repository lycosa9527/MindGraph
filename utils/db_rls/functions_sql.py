"""SQL for rev_0042 RLS helper functions (PostgreSQL 18.3).

STABLE only — not LEAKPROOF: bodies use ``current_setting()`` / table reads, which
PostgreSQL does not allow in leakproof functions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


def split_sql_statements(sql: str) -> list[str]:
    """Split multi-statement DDL into individual executable chunks."""
    statements: list[str] = []
    for part in sql.strip().split(";\n\n"):
        piece = part.strip()
        if not piece:
            continue
        statements.append(piece if piece.endswith(";") else f"{piece};")
    return statements


def rls_functions_upgrade_statements() -> list[str]:
    """Return the RLS helper ``CREATE OR REPLACE`` statements in dependency order."""
    return split_sql_statements(RLS_FUNCTIONS_UPGRADE)


def build_grant_rls_functions_to_app_sql() -> str:
    """
    Grant EXECUTE on MindGraph ``rls_*`` helpers to ``mindgraph_app`` only.

    Avoids ``GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public``, which fails when
    ``pg_stat_statements`` (rev 0031) installs functions the migrate role cannot grant.
    """
    return """
DO $$
DECLARE
    fn record;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
        FOR fn IN
            SELECT p.oid::regprocedure AS signature
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname ~ '^rls_'
        LOOP
            EXECUTE format(
                'GRANT EXECUTE ON FUNCTION %s TO mindgraph_app',
                fn.signature
            );
        END LOOP;
    END IF;
END $$;
"""


RLS_FUNCTIONS_UPGRADE = """
CREATE OR REPLACE FUNCTION rls_setting_text(setting_name text)
RETURNS text
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT current_setting(setting_name, true)
$$;

CREATE OR REPLACE FUNCTION rls_mode()
RETURNS text
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT coalesce(rls_setting_text('app.rls_mode'), '')
$$;

CREATE OR REPLACE FUNCTION rls_current_user_id()
RETURNS integer
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT nullif(rls_setting_text('app.user_id'), '')::integer
$$;

CREATE OR REPLACE FUNCTION rls_current_org_id()
RETURNS integer
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT nullif(rls_setting_text('app.organization_id'), '')::integer
$$;

CREATE OR REPLACE FUNCTION rls_is_system_mode()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() = 'system'
$$;

CREATE OR REPLACE FUNCTION rls_is_deny_mode()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() = 'deny'
$$;

CREATE OR REPLACE FUNCTION rls_is_dashboard_mode()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() = 'dashboard'
$$;

CREATE OR REPLACE FUNCTION rls_is_mindbot_service_mode()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() = 'mindbot_service'
$$;

CREATE OR REPLACE FUNCTION rls_allow_public_org_list()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_setting_text('app.allow_public_org_list') = '1'
$$;

CREATE OR REPLACE FUNCTION rls_allow_global_channels()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_setting_text('app.allow_global_channels') = '1'
$$;

CREATE OR REPLACE FUNCTION rls_panel_global_read()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_setting_text('app.panel_global_read') = '1'
$$;

CREATE OR REPLACE FUNCTION rls_is_panel_mode()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() IN ('panel', 'panel_superadmin')
$$;

CREATE OR REPLACE FUNCTION rls_readable_org_ids_text()
RETURNS text
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT nullif(trim(rls_setting_text('app.readable_org_ids')), '')
$$;

CREATE OR REPLACE FUNCTION rls_org_id_in_readable_list(target_org_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT target_org_id IS NOT NULL
        AND rls_readable_org_ids_text() IS NOT NULL
        AND target_org_id::text = ANY (
            string_to_array(rls_readable_org_ids_text(), ',')
        )
$$;

CREATE OR REPLACE FUNCTION rls_lookup_org_invited_by_user_id(target_org_id bigint)
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT invited_by_user_id FROM organizations WHERE id = target_org_id
$$;

CREATE OR REPLACE FUNCTION rls_panel_legacy_org_visible(target_org_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT coalesce(rls_setting_text('app.role'), '') <> 'expert'
        AND target_org_id IS NOT NULL
        AND rls_lookup_org_invited_by_user_id(target_org_id) IS NULL
$$;

CREATE OR REPLACE FUNCTION rls_panel_org_invited_by_actor(invited_by bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_is_panel_mode()
        AND invited_by IS NOT NULL
        AND rls_current_user_id() IS NOT NULL
        AND invited_by = rls_current_user_id()
$$;

CREATE OR REPLACE FUNCTION rls_org_visible(target_org_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN rls_is_system_mode() OR rls_is_dashboard_mode() THEN true
        WHEN rls_is_deny_mode() THEN false
        WHEN rls_is_mindbot_service_mode() THEN (
            target_org_id IS NOT NULL
            AND target_org_id = rls_current_org_id()
        )
        WHEN rls_is_panel_mode() THEN (
            rls_panel_global_read()
            OR (target_org_id IS NOT NULL AND rls_org_id_in_readable_list(target_org_id))
            OR (target_org_id IS NOT NULL AND rls_panel_legacy_org_visible(target_org_id))
            OR (target_org_id IS NOT NULL AND target_org_id = rls_current_org_id())
        )
        WHEN rls_mode() = 'public' AND rls_allow_public_org_list() THEN true
        ELSE (
            target_org_id IS NOT NULL
            AND rls_current_org_id() IS NOT NULL
            AND target_org_id = rls_current_org_id()
        )
    END
$$;

CREATE OR REPLACE FUNCTION rls_lookup_user_organization_id(target_user_id bigint)
RETURNS bigint
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT organization_id FROM users WHERE id = target_user_id
$$;

CREATE OR REPLACE FUNCTION rls_same_org_users(target_user_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT target_user_id IS NOT NULL
        AND rls_current_user_id() IS NOT NULL
        AND rls_lookup_user_organization_id(rls_current_user_id()) IS NOT NULL
        AND rls_lookup_user_organization_id(target_user_id)
            = rls_lookup_user_organization_id(rls_current_user_id())
$$;

CREATE OR REPLACE FUNCTION rls_user_visible(target_user_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN rls_is_system_mode() OR rls_is_dashboard_mode() THEN true
        WHEN rls_is_deny_mode() THEN false
        WHEN target_user_id IS NULL THEN false
        WHEN target_user_id = rls_current_user_id() THEN true
        WHEN rls_is_panel_mode() THEN (
            rls_panel_global_read()
            OR rls_org_visible(rls_lookup_user_organization_id(target_user_id))
        )
        ELSE rls_same_org_users(target_user_id)
    END
$$;

CREATE OR REPLACE FUNCTION rls_diagram_visible(owner_user_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN rls_is_system_mode() THEN true
        WHEN rls_is_deny_mode() THEN false
        WHEN owner_user_id = rls_current_user_id() THEN true
        WHEN rls_panel_global_read() THEN true
        WHEN rls_is_panel_mode() THEN (
            owner_user_id IS NOT NULL
            AND rls_org_visible(rls_lookup_user_organization_id(owner_user_id))
        )
        ELSE rls_same_org_users(owner_user_id)
    END
$$;

CREATE OR REPLACE FUNCTION rls_knowledge_space_visible(space_id integer)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM knowledge_spaces ks
        WHERE ks.id = space_id
          AND rls_diagram_visible(ks.user_id)
    )
$$;

CREATE OR REPLACE FUNCTION rls_knowledge_document_visible(doc_id integer)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM knowledge_documents kd
        JOIN knowledge_spaces ks ON ks.id = kd.space_id
        WHERE kd.id = doc_id
          AND rls_diagram_visible(ks.user_id)
    )
$$;

CREATE OR REPLACE FUNCTION rls_mindbot_callback_token_visible(token_value text)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_is_mindbot_service_mode()
        AND rls_setting_text('app.mindbot_callback_token') IS NOT NULL
        AND token_value = rls_setting_text('app.mindbot_callback_token')
$$;

CREATE OR REPLACE FUNCTION rls_chat_channel_visible(channel_org_id bigint)
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN rls_is_system_mode() THEN true
        WHEN rls_is_deny_mode() THEN false
        WHEN channel_org_id IS NULL THEN rls_allow_global_channels() OR rls_is_panel_mode()
        ELSE rls_org_visible(channel_org_id)
    END
$$;

CREATE OR REPLACE FUNCTION rls_community_read_allowed()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_mode() IN (
        'authenticated', 'panel', 'panel_superadmin', 'system'
    )
$$;

CREATE OR REPLACE FUNCTION rls_platform_admin_only()
RETURNS boolean
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT rls_is_panel_mode()
        OR rls_mode() = 'panel_superadmin'
        OR rls_is_system_mode()
$$;
"""

RLS_FUNCTIONS_DOWNGRADE = """
DROP FUNCTION IF EXISTS rls_platform_admin_only();
DROP FUNCTION IF EXISTS rls_community_read_allowed();
DROP FUNCTION IF EXISTS rls_chat_channel_visible(bigint);
DROP FUNCTION IF EXISTS rls_mindbot_callback_token_visible(text);
DROP FUNCTION IF EXISTS rls_knowledge_document_visible(integer);
DROP FUNCTION IF EXISTS rls_knowledge_space_visible(integer);
DROP FUNCTION IF EXISTS rls_diagram_visible(bigint);
DROP FUNCTION IF EXISTS rls_user_visible(bigint);
DROP FUNCTION IF EXISTS rls_panel_org_invited_by_actor(bigint);
DROP FUNCTION IF EXISTS rls_lookup_org_invited_by_user_id(bigint);
DROP FUNCTION IF EXISTS rls_lookup_user_organization_id(bigint);
DROP FUNCTION IF EXISTS rls_same_org_users(bigint);
DROP FUNCTION IF EXISTS rls_org_visible(bigint);
DROP FUNCTION IF EXISTS rls_panel_legacy_org_visible(bigint);
DROP FUNCTION IF EXISTS rls_org_id_in_readable_list(bigint);
DROP FUNCTION IF EXISTS rls_readable_org_ids_text();
DROP FUNCTION IF EXISTS rls_is_panel_mode();
DROP FUNCTION IF EXISTS rls_panel_global_read();
DROP FUNCTION IF EXISTS rls_allow_global_channels();
DROP FUNCTION IF EXISTS rls_allow_public_org_list();
DROP FUNCTION IF EXISTS rls_is_mindbot_service_mode();
DROP FUNCTION IF EXISTS rls_is_dashboard_mode();
DROP FUNCTION IF EXISTS rls_is_deny_mode();
DROP FUNCTION IF EXISTS rls_is_system_mode();
DROP FUNCTION IF EXISTS rls_current_org_id();
DROP FUNCTION IF EXISTS rls_current_user_id();
DROP FUNCTION IF EXISTS rls_mode();
DROP FUNCTION IF EXISTS rls_setting_text(text);
"""
