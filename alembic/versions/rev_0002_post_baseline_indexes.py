"""Post-baseline indexes: FTS GIN and JSONB GIN indexes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-02

These indexes are not captured by SQLAlchemy model definitions but were
maintained by the legacy custom migration system.  All statements are
idempotent (IF NOT EXISTS).
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FTS_GIN_INDEXES = (
    (
        "ix_chat_messages_fts_content",
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_fts_content "
        "ON chat_messages USING gin (to_tsvector('simple', content))",
    ),
    (
        "ix_direct_messages_fts_content",
        "CREATE INDEX IF NOT EXISTS ix_direct_messages_fts_content "
        "ON direct_messages USING gin (to_tsvector('simple', content))",
    ),
)

_JSONB_GIN_INDEXES = (
    ("ix_diagrams_spec_gin", "diagrams", "spec"),
    ("ix_community_posts_spec_gin", "community_posts", "spec"),
    ("ix_shared_diagrams_diagram_data_gin", "shared_diagrams", "diagram_data"),
    ("ix_gewe_contacts_extra_data_gin", "gewe_contacts", "extra_data"),
    ("ix_gewe_group_members_extra_data_gin", "gewe_group_members", "extra_data"),
    ("ix_knowledge_spaces_processing_rules_gin", "knowledge_spaces", "processing_rules"),
    ("ix_knowledge_documents_doc_metadata_gin", "knowledge_documents", "doc_metadata"),
    ("ix_knowledge_documents_tags_gin", "knowledge_documents", "tags"),
    ("ix_knowledge_documents_custom_fields_gin", "knowledge_documents", "custom_fields"),
    ("ix_knowledge_queries_source_context_gin", "knowledge_queries", "source_context"),
    ("ix_child_chunks_meta_data_gin", "child_chunks", "meta_data"),
    ("ix_document_versions_change_summary_gin", "document_versions", "change_summary"),
    ("ix_query_feedback_relevant_chunk_ids_gin", "query_feedback", "relevant_chunk_ids"),
    ("ix_query_feedback_irrelevant_chunk_ids_gin", "query_feedback", "irrelevant_chunk_ids"),
    ("ix_query_templates_parameters_gin", "query_templates", "parameters"),
    ("ix_evaluation_datasets_queries_gin", "evaluation_datasets", "queries"),
    ("ix_evaluation_results_metrics_gin", "evaluation_results", "metrics"),
    ("ix_chunk_test_results_document_ids_gin", "chunk_test_results", "document_ids"),
    ("ix_chunk_test_results_chunk_stats_gin", "chunk_test_results", "chunk_stats"),
    ("ix_chunk_test_results_retrieval_metrics_gin", "chunk_test_results", "retrieval_metrics"),
    ("ix_chunk_test_results_comparison_summary_gin", "chunk_test_results", "comparison_summary"),
    ("ix_chunk_test_results_evaluation_results_gin", "chunk_test_results", "evaluation_results"),
    ("ix_chunk_test_results_completed_methods_gin", "chunk_test_results", "completed_methods"),
    ("ix_chunk_test_documents_meta_data_gin", "chunk_test_documents", "meta_data"),
    ("ix_chunk_test_document_chunks_meta_data_gin", "chunk_test_document_chunks", "meta_data"),
    ("ix_debate_judgments_scores_gin", "debate_judgments", "scores"),
    ("ix_library_danmaku_text_bbox_gin", "library_danmaku", "text_bbox"),
    ("ix_teacher_usage_config_config_value_gin", "teacher_usage_config", "config_value"),
    ("ix_chat_messages_mentioned_user_ids_gin", "chat_messages", "mentioned_user_ids"),
    ("ix_direct_messages_mentioned_user_ids_gin", "direct_messages", "mentioned_user_ids"),
)


def upgrade() -> None:
    conn = op.get_bind()

    for _name, stmt in _FTS_GIN_INDEXES:
        conn.execute(text(stmt))

    for idx_name, table_name, column_name in _JSONB_GIN_INDEXES:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} USING gin ({column_name})"))


def downgrade() -> None:
    conn = op.get_bind()

    for idx_name, _table_name, _column_name in reversed(_JSONB_GIN_INDEXES):
        conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))

    for name, _stmt in reversed(_FTS_GIN_INDEXES):
        conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
