"""Drop unused Knowledge Space lab tables.

Revision ID: 0166
Revises: 0165
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0166"
down_revision: Union[str, None] = "0165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "evaluation_results",
    "query_feedback",
    "query_templates",
    "document_relationships",
    "evaluation_datasets",
    "knowledge_queries",
)
_ENUMS = ("feedback_type",)


def _drop_tables() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if inspector.has_table(table):
            op.drop_table(table)


def _drop_enums() -> None:
    for name in _ENUMS:
        op.execute(sa.text(f'DROP TYPE IF EXISTS "{name}"'))


def upgrade() -> None:
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    _drop_tables()
    _drop_enums()


def downgrade() -> None:
    """Knowledge Space lab tables are not restored."""
