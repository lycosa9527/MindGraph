"""Generate ENABLE ROW LEVEL SECURITY + policies per table group."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


def _enable_force(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))


def _drop_policy(table: str, name: str) -> None:
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{name}" ON "{table}"'))


def _create_all_policy(table: str, name: str, using_expr: str, check_expr: str | None = None) -> None:
    check_sql = check_expr if check_expr is not None else using_expr
    op.execute(
        sa.text(
            f'CREATE POLICY "{name}" ON "{table}" FOR ALL '
            f"USING ({using_expr}) WITH CHECK ({check_sql})"
        )
    )


# Group A — user_id column (or diagram/knowledge helpers)
USER_OWNED_EXPR = "rls_diagram_visible(user_id)"
DEVICE_EXPR = (
    "(student_id IS NULL AND (rls_is_panel_mode() OR rls_is_system_mode())) "
    "OR rls_diagram_visible(student_id)"
)
USER_OWNED_TABLES = [
    "diagrams",
    "diagram_snapshots",
    "knowledge_spaces",
    "pinned_conversations",
    "user_api_tokens",
    "user_usage_stats",
    "user_activity_log",
    "debate_sessions",
    "library_bookmarks",
    "market_orders",
    "market_entitlements",
    "market_subscriptions",
]

MARKET_CHILD_TABLES = [
    (
        "market_payments",
        (
            "EXISTS (SELECT 1 FROM market_orders mo "
            "WHERE mo.id = order_id AND rls_diagram_visible(mo.user_id))"
        ),
    ),
]

GEWE_TABLES = [
    "gewe_messages",
    "gewe_contacts",
    "gewe_group_members",
]
GEWE_EXPR = "rls_platform_admin_only()"

USER_OR_SPACE_VISIBLE = (
    "(space_id IS NOT NULL AND rls_knowledge_space_visible(space_id)) "
    "OR (space_id IS NULL AND rls_user_visible(user_id))"
)
EMBEDDINGS_EXPR = "rls_is_system_mode() OR rls_community_read_allowed()"
DIRECT_MESSAGE_EXPR = "rls_user_visible(sender_id) OR rls_user_visible(recipient_id)"
COMMUNITY_POST_WRITE = "author_id = rls_current_user_id() OR rls_is_panel_mode()"

KNOWLEDGE_DOCUMENT_EXPR = "rls_knowledge_document_visible(id)"
KNOWLEDGE_SPACE_CHILD_TABLES = [
    ("knowledge_documents", "rls_knowledge_space_visible(space_id)"),
    ("document_chunks", "rls_knowledge_document_visible(document_id)"),
    ("embeddings", EMBEDDINGS_EXPR),
    ("knowledge_queries", "rls_knowledge_space_visible(space_id)"),
    (
        "chunk_attachments",
        (
            "EXISTS (SELECT 1 FROM document_chunks dc "
            "WHERE dc.id = chunk_id AND rls_knowledge_document_visible(dc.document_id))"
        ),
    ),
    (
        "child_chunks",
        (
            "EXISTS (SELECT 1 FROM document_chunks dc "
            "WHERE dc.id = parent_chunk_id AND rls_knowledge_document_visible(dc.document_id))"
        ),
    ),
    ("document_batches", "rls_diagram_visible(user_id)"),
    ("document_versions", "rls_knowledge_document_visible(document_id)"),
    ("query_feedback", "rls_knowledge_space_visible(space_id)"),
    ("query_templates", USER_OR_SPACE_VISIBLE),
    (
        "document_relationships",
        (
            "rls_knowledge_document_visible(source_document_id) "
            "OR rls_knowledge_document_visible(target_document_id)"
        ),
    ),
    ("evaluation_datasets", USER_OR_SPACE_VISIBLE),
    (
        "evaluation_results",
        (
            "EXISTS (SELECT 1 FROM evaluation_datasets ed WHERE ed.id = dataset_id AND ("
            "(ed.space_id IS NOT NULL AND rls_knowledge_space_visible(ed.space_id)) "
            "OR (ed.space_id IS NULL AND rls_user_visible(ed.user_id))))"
        ),
    ),
    ("chunk_test_results", "rls_diagram_visible(user_id)"),
    ("chunk_test_documents", "rls_diagram_visible(user_id)"),
    (
        "chunk_test_document_chunks",
        (
            "EXISTS (SELECT 1 FROM chunk_test_documents ctd "
            "WHERE ctd.id = document_id AND rls_diagram_visible(ctd.user_id))"
        ),
    ),
]

DEBATE_CHILD_TABLES = [
    ("debate_participants", (
        "EXISTS (SELECT 1 FROM debate_sessions ds "
        "WHERE ds.id = session_id AND rls_diagram_visible(ds.user_id))"
    )),
    ("debate_messages", (
        "EXISTS (SELECT 1 FROM debate_sessions ds "
        "WHERE ds.id = session_id AND rls_diagram_visible(ds.user_id))"
    )),
    ("debate_judgments", (
        "EXISTS (SELECT 1 FROM debate_sessions ds "
        "WHERE ds.id = session_id AND rls_diagram_visible(ds.user_id))"
    )),
]

# Group B — organization_id
ORG_TABLES = [
    "token_usage",
    "mindbot_usage_events",
    "organization_mindbot_configs",
    "shared_diagrams",
    "feature_access_org_grants",
]

SHARED_DIAGRAM_CHILD = [
    (
        "shared_diagram_likes",
        "EXISTS (SELECT 1 FROM shared_diagrams sd "
        "WHERE sd.id = diagram_id AND rls_org_visible(sd.organization_id))",
    ),
    (
        "shared_diagram_comments",
        "EXISTS (SELECT 1 FROM shared_diagrams sd "
        "WHERE sd.id = diagram_id AND rls_org_visible(sd.organization_id))",
    ),
]

ORG_EXPR = "rls_org_visible(organization_id)"
MINDBOT_CONFIG_EXPR = (
    "rls_org_visible(organization_id) "
    "OR rls_mindbot_callback_token_visible(public_callback_token)"
)
MINDBOT_USAGE_EXPR = "rls_org_visible(organization_id)"

WORKSHOP_ROOT = "chat_channels"
WORKSHOP_CHANNEL_EXPR = "rls_chat_channel_visible(organization_id)"
WORKSHOP_CHILD = [
    ("channel_members", (
        "EXISTS (SELECT 1 FROM chat_channels c "
        "WHERE c.id = channel_id AND rls_chat_channel_visible(c.organization_id))"
    )),
    ("chat_topics", (
        "EXISTS (SELECT 1 FROM chat_channels c "
        "WHERE c.id = channel_id AND rls_chat_channel_visible(c.organization_id))"
    )),
    ("chat_messages", (
        "EXISTS (SELECT 1 FROM chat_topics t "
        "JOIN chat_channels c ON c.id = t.channel_id "
        "WHERE t.id = topic_id AND rls_chat_channel_visible(c.organization_id))"
    )),
    ("direct_messages", DIRECT_MESSAGE_EXPR),
    ("message_reactions", (
        "EXISTS (SELECT 1 FROM chat_messages m "
        "JOIN chat_topics t ON t.id = m.topic_id "
        "JOIN chat_channels c ON c.id = t.channel_id "
        "WHERE m.id = message_id AND rls_chat_channel_visible(c.organization_id))"
    )),
    ("starred_messages", "rls_user_visible(user_id)"),
    ("file_attachments", (
        "EXISTS (SELECT 1 FROM chat_messages m "
        "JOIN chat_topics t ON t.id = m.topic_id "
        "JOIN chat_channels c ON c.id = t.channel_id "
        "WHERE m.id = message_id AND rls_chat_channel_visible(c.organization_id))"
    )),
    ("user_topic_preferences", "rls_user_visible(user_id)"),
]

# Group C
USERS_EXPR = "rls_user_visible(id)"
ORGS_EXPR = (
    "(rls_mode() = 'public' AND rls_allow_public_org_list()) "
    "OR rls_org_visible(id) "
    "OR (rls_is_panel_mode() AND (rls_panel_global_read() OR rls_org_id_in_readable_list(id) "
    "OR rls_panel_legacy_org_visible(id)))"
)

# Group D
COMMUNITY_READ = "rls_community_read_allowed()"
COMMUNITY_WRITE = "user_id = rls_current_user_id() OR rls_is_panel_mode()"
LIBRARY_DOC_READ = "rls_community_read_allowed()"
LIBRARY_DOC_WRITE = "rls_platform_admin_only()"

# Group E
PLATFORM_ADMIN = "rls_platform_admin_only()"


def upgrade_devices_policy() -> None:
    """devices use student_id, not user_id."""
    _enable_force("devices")
    _create_all_policy("devices", "devices_tenant", DEVICE_EXPR)


def upgrade_gewe_policies() -> None:
    """Gewe tables are keyed by app_id; admin/system paths only (no user_id column)."""
    for table in GEWE_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", GEWE_EXPR)


def upgrade_group_a() -> None:
    for table in USER_OWNED_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", USER_OWNED_EXPR)
    upgrade_devices_policy()
    upgrade_gewe_policies()
    for table, expr in KNOWLEDGE_SPACE_CHILD_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", expr)
    for table, expr in DEBATE_CHILD_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", expr)
    for table, expr in MARKET_CHILD_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", expr)


def upgrade_group_b() -> None:
    for table in ORG_TABLES:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", _org_table_expr(table))
    for table, expr in SHARED_DIAGRAM_CHILD:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", expr)
    _enable_force(WORKSHOP_ROOT)
    _create_all_policy(WORKSHOP_ROOT, "chat_channels_tenant", WORKSHOP_CHANNEL_EXPR)
    for table, expr in WORKSHOP_CHILD:
        _enable_force(table)
        _create_all_policy(table, f"{table}_tenant", expr)


def upgrade_group_cde() -> None:
    _enable_force("users")
    _create_all_policy("users", "users_tenant", USERS_EXPR)
    _enable_force("organizations")
    _create_all_policy("organizations", "organizations_tenant", ORGS_EXPR)

    community_tables = [
        ("community_posts", COMMUNITY_READ, COMMUNITY_POST_WRITE),
        ("community_post_likes", COMMUNITY_READ, "user_id = rls_current_user_id()"),
        ("community_post_comments", COMMUNITY_READ, COMMUNITY_WRITE),
    ]
    for table, read_expr, write_expr in community_tables:
        _enable_force(table)
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({read_expr})'
            )
        )
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT '
                f"WITH CHECK ({write_expr})"
            )
        )
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE '
                f"USING ({write_expr}) WITH CHECK ({write_expr})"
            )
        )
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({write_expr})'
            )
        )

    library_tables = [
        ("library_documents", LIBRARY_DOC_READ, LIBRARY_DOC_WRITE),
        ("library_danmaku", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
        ("library_danmaku_likes", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
        ("library_danmaku_replies", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
    ]
    for table, read_expr, write_expr in library_tables:
        _enable_force(table)
        op.execute(
            sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({read_expr})')
        )
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_mutate" ON "{table}" FOR ALL '
                f"USING ({write_expr}) WITH CHECK ({write_expr})"
            )
        )

    platform_tables = [
        "api_keys",
        "update_notifications",
        "feature_access_rules",
        "feature_access_user_grants",
        "teacher_usage_config",
        "dashboard_activities",
        "market_listings",
    ]
    for table in platform_tables:
        _enable_force(table)
        _create_all_policy(table, f"{table}_admin", PLATFORM_ADMIN)

    _enable_force("update_notification_dismissed")
    _create_all_policy(
        "update_notification_dismissed",
        "update_notification_dismissed_tenant",
        "user_id = rls_current_user_id() OR rls_is_panel_mode()",
    )


def downgrade_policies_for_tables(tables: list[str]) -> None:
    for table in tables:
        op.execute(
            sa.text(
                f"""
                DO $$
                DECLARE pol record;
                BEGIN
                    FOR pol IN
                        SELECT policyname FROM pg_policies
                        WHERE schemaname = 'public' AND tablename = '{table}'
                    LOOP
                        EXECUTE format(
                            'DROP POLICY IF EXISTS %I ON %I',
                            pol.policyname,
                            '{table}'
                        );
                    END LOOP;
                END $$;
                """
            )
        )
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))


def _org_table_expr(table: str) -> str:
    if table == "organization_mindbot_configs":
        return MINDBOT_CONFIG_EXPR
    if table == "mindbot_usage_events":
        return MINDBOT_USAGE_EXPR
    if table == "feature_access_org_grants":
        return f"{ORG_EXPR} OR rls_platform_admin_only()"
    return ORG_EXPR


def iter_all_table_policies() -> list[tuple[str, str]]:
    """Every (table, policy expression) pair for schema validation tests."""
    rows: list[tuple[str, str]] = []
    rows.extend((table, USER_OWNED_EXPR) for table in USER_OWNED_TABLES)
    rows.append(("devices", DEVICE_EXPR))
    rows.extend((table, GEWE_EXPR) for table in GEWE_TABLES)
    rows.extend(KNOWLEDGE_SPACE_CHILD_TABLES)
    rows.extend(DEBATE_CHILD_TABLES)
    rows.extend(MARKET_CHILD_TABLES)
    for table in ORG_TABLES:
        rows.append((table, _org_table_expr(table)))
    rows.extend(SHARED_DIAGRAM_CHILD)
    rows.append((WORKSHOP_ROOT, WORKSHOP_CHANNEL_EXPR))
    rows.extend(WORKSHOP_CHILD)
    rows.append(("users", USERS_EXPR))
    rows.append(("organizations", ORGS_EXPR))
    rows.append(("community_posts", COMMUNITY_READ))
    rows.append(("community_posts", COMMUNITY_POST_WRITE))
    rows.append(("community_post_likes", COMMUNITY_READ))
    rows.append(("community_post_likes", "user_id = rls_current_user_id()"))
    rows.append(("community_post_comments", COMMUNITY_READ))
    rows.append(("community_post_comments", COMMUNITY_WRITE))
    for table, read_expr, write_expr in (
        ("library_documents", LIBRARY_DOC_READ, LIBRARY_DOC_WRITE),
        ("library_danmaku", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
        ("library_danmaku_likes", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
        ("library_danmaku_replies", LIBRARY_DOC_READ, "user_id = rls_current_user_id()"),
    ):
        rows.append((table, read_expr))
        rows.append((table, write_expr))
    for table in (
        "api_keys",
        "update_notifications",
        "feature_access_rules",
        "feature_access_user_grants",
        "teacher_usage_config",
        "dashboard_activities",
        "market_listings",
    ):
        rows.append((table, PLATFORM_ADMIN))
    rows.append(
        (
            "update_notification_dismissed",
            "user_id = rls_current_user_id() OR rls_is_panel_mode()",
        )
    )
    return rows


def all_rls_tables() -> list[str]:
    tables = list(USER_OWNED_TABLES)
    tables.extend(GEWE_TABLES)
    tables.append("devices")
    tables.extend(t for t, _ in KNOWLEDGE_SPACE_CHILD_TABLES)
    tables.extend(t for t, _ in DEBATE_CHILD_TABLES)
    tables.extend(t for t, _ in MARKET_CHILD_TABLES)
    tables.extend(ORG_TABLES)
    tables.extend(t for t, _ in SHARED_DIAGRAM_CHILD)
    tables.append(WORKSHOP_ROOT)
    tables.extend(t for t, _ in WORKSHOP_CHILD)
    tables.extend(["users", "organizations"])
    tables.extend(
        [
            "community_posts",
            "community_post_likes",
            "community_post_comments",
            "library_documents",
            "library_danmaku",
            "library_danmaku_likes",
            "library_danmaku_replies",
            "api_keys",
            "update_notifications",
            "update_notification_dismissed",
            "feature_access_rules",
            "feature_access_user_grants",
            "feature_access_org_grants",
            "teacher_usage_config",
            "dashboard_activities",
            "market_listings",
        ]
    )
    return tables
