"""Drop RAG chunk-test tables and leftover feature grants.

Revision ID: 0165
Revises: 0164
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0165"
down_revision: Union[str, None] = "0164"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "chunk_test_document_chunks",
    "chunk_test_documents",
    "chunk_test_results",
)
_ENUMS = ("chunk_test_document_status", "chunk_test_status")
_GRANT_TABLES = (
    "feature_access_org_grants",
    "feature_access_user_grants",
    "feature_access_rules",
)
_FEATURE_KEY = "feature_rag_chunk_test"


def _drop_tables() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if inspector.has_table(table):
            op.drop_table(table)


def _drop_enums() -> None:
    for name in _ENUMS:
        op.execute(sa.text(f'DROP TYPE IF EXISTS "{name}"'))


def _delete_feature_grants() -> None:
    inspector = sa.inspect(op.get_bind())
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    for table in _GRANT_TABLES:
        if inspector.has_table(table):
            op.execute(
                sa.text(f'DELETE FROM "{table}" WHERE feature_key = :feature_key').bindparams(feature_key=_FEATURE_KEY)
            )


def upgrade() -> None:
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    _drop_tables()
    _drop_enums()
    _delete_feature_grants()


def downgrade() -> None:
    """Chunk test is not restored."""
