"""Composite and partial indexes for RLS policy columns.

Revision ID: 0048
Revises: 0047
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_table_exists(name: str, table: str, columns: str, *, where: str | None = None) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return
    where_clause = f" WHERE {where}" if where else ""
    op.execute(
        sa.text(
            f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns}){where_clause}'
        )
    )


def upgrade() -> None:
    _create_index_if_table_exists("ix_rls_diagrams_user_id_id", "diagrams", "user_id, id")
    _create_index_if_table_exists(
        "ix_rls_knowledge_documents_space_id", "knowledge_documents", "space_id"
    )
    _create_index_if_table_exists(
        "ix_rls_document_chunks_document_id", "document_chunks", "document_id"
    )
    _create_index_if_table_exists(
        "ix_rls_token_usage_org_created",
        "token_usage",
        "organization_id, created_at DESC",
    )
    _create_index_if_table_exists(
        "ix_rls_mindbot_usage_org_id",
        "mindbot_usage_events",
        "organization_id, id DESC",
    )
    _create_index_if_table_exists(
        "ix_rls_org_mindbot_configs_org_id",
        "organization_mindbot_configs",
        "organization_id",
    )
    _create_index_if_table_exists("ix_rls_users_org_id", "users", "organization_id, id")
    _create_index_if_table_exists(
        "ix_rls_chat_channels_announce",
        "chat_channels",
        "id",
        where="organization_id IS NULL",
    )


def downgrade() -> None:
    for name in (
        "ix_rls_diagrams_user_id_id",
        "ix_rls_knowledge_documents_space_id",
        "ix_rls_document_chunks_document_id",
        "ix_rls_token_usage_org_created",
        "ix_rls_mindbot_usage_org_id",
        "ix_rls_org_mindbot_configs_org_id",
        "ix_rls_users_org_id",
        "ix_rls_chat_channels_announce",
    ):
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))
