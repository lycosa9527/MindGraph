"""RLS policies — group A (user-owned + knowledge chain).

Revision ID: 0044
Revises: 0043
"""

from typing import Sequence, Union

from db_rls.policy_builder import (
    all_rls_tables,
    downgrade_policies_for_tables,
    upgrade_group_a,
)

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUP_A_TABLES = [
    t
    for t in all_rls_tables()
    if t
    in {
        "diagrams",
        "diagram_snapshots",
        "knowledge_spaces",
        "knowledge_documents",
        "document_chunks",
        "embeddings",
        "knowledge_queries",
        "chunk_attachments",
        "child_chunks",
        "document_batches",
        "document_versions",
        "query_feedback",
        "query_templates",
        "document_relationships",
        "evaluation_datasets",
        "evaluation_results",
        "chunk_test_results",
        "chunk_test_documents",
        "chunk_test_document_chunks",
        "pinned_conversations",
        "user_api_tokens",
        "user_usage_stats",
        "user_activity_log",
        "devices",
        "debate_sessions",
        "debate_participants",
        "debate_messages",
        "debate_judgments",
        "gewe_messages",
        "gewe_contacts",
        "gewe_group_members",
        "library_bookmarks",
        "market_orders",
        "market_payments",
        "market_entitlements",
        "market_subscriptions",
    }
]


def upgrade() -> None:
    upgrade_group_a()


def downgrade() -> None:
    downgrade_policies_for_tables(_GROUP_A_TABLES)
