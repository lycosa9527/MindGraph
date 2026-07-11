"""Add request_id to kitty_one_sentence_turns for tracked chat requests."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("kitty_one_sentence_turns"):
        return
    columns = {col["name"] for col in inspector.get_columns("kitty_one_sentence_turns")}
    if "request_id" in columns:
        return
    op.add_column(
        "kitty_one_sentence_turns",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_kitty_one_sentence_turns_request_id"),
        "kitty_one_sentence_turns",
        ["request_id"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
