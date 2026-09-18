"""Add instruction_images to learning_assignments.

Revision ID: 0122
Revises: 0121
Create Date: 2026-09-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0122"
down_revision: Union[str, None] = "0121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_assignments"):
        return
    cols = {c["name"] for c in inspector.get_columns("learning_assignments")}
    if "instruction_images" not in cols:
        op.add_column(
            "learning_assignments",
            sa.Column(
                "instruction_images",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_assignments"):
        return
    cols = {c["name"] for c in inspector.get_columns("learning_assignments")}
    if "instruction_images" in cols:
        op.drop_column("learning_assignments", "instruction_images")
