"""Create diagram_snapshots if missing (ORM-backed snapshots).

Baseline ``0001`` may already have created this table via ``create_all``.
Idempotent: skip DDL when ``diagram_snapshots`` exists.

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("diagram_snapshots"):
        return
    op.create_table(
        "diagram_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagram_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("spec", pg.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagram_id", "version_number", name="uq_diagram_snapshot_version"),
    )
    op.create_index("ix_diagram_snapshots_diagram_id", "diagram_snapshots", ["diagram_id"], unique=False)
    op.create_index("ix_diagram_snapshots_user_id", "diagram_snapshots", ["user_id"], unique=False)


def downgrade() -> None:
    if _has_table("diagram_snapshots"):
        op.drop_table("diagram_snapshots")
