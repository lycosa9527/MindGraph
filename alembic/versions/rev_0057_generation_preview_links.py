"""Durable generate_dingtalk preview → library diagram links."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("generation_preview_links"):
        return
    op.create_table(
        "generation_preview_links",
        sa.Column("preview_id", sa.String(length=8), nullable=False),
        sa.Column("diagram_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("skip_reason", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="zh"),
        sa.Column("diagram_type", sa.String(length=64), nullable=False, server_default="mind_map"),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="Diagram"),
        sa.Column("spec", pg.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("preview_id"),
    )
    op.create_index(
        "ix_generation_preview_links_diagram_id",
        "generation_preview_links",
        ["diagram_id"],
    )
    op.create_index(
        "ix_generation_preview_links_user_id",
        "generation_preview_links",
        ["user_id"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
