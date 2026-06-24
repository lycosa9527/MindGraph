"""Add File Center package fields on document_batches and diagrams.

Revision ID: 0070
Revises: 0069
Create Date: 2026-06-22

A DocumentBatch doubles as a named knowledge "package" scoped to one diagram:
``name``, ``diagram_id`` (FK diagrams.id), and ``source`` identify the package.
``diagrams.knowledge_package_id`` links a diagram back to its package so RAG
retrieval can be scoped to the package's documents.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(conn, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("document_batches"):
        batch_columns = _column_names(bind, "document_batches")
        if "name" not in batch_columns:
            op.add_column(
                "document_batches",
                sa.Column("name", sa.String(length=200), nullable=True),
            )
        if "diagram_id" not in batch_columns:
            op.add_column(
                "document_batches",
                sa.Column(
                    "diagram_id",
                    sa.String(length=36),
                    sa.ForeignKey("diagrams.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index(
                "ix_document_batches_diagram_id",
                "document_batches",
                ["diagram_id"],
            )
        if "source" not in batch_columns:
            op.add_column(
                "document_batches",
                sa.Column("source", sa.String(length=32), nullable=True),
            )

    if inspector.has_table("diagrams"):
        diagram_columns = _column_names(bind, "diagrams")
        if "knowledge_package_id" not in diagram_columns:
            op.add_column(
                "diagrams",
                sa.Column(
                    "knowledge_package_id",
                    sa.Integer(),
                    sa.ForeignKey("document_batches.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index(
                "ix_diagrams_knowledge_package_id",
                "diagrams",
                ["knowledge_package_id"],
            )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
