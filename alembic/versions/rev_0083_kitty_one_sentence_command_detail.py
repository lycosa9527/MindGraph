"""Add command_detail JSONB for one-sentence diagram activity tracking."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("kitty_one_sentence_turns"):
        return
    columns = {col["name"] for col in inspector.get_columns("kitty_one_sentence_turns")}
    if "command_detail" in columns:
        return
    op.add_column(
        "kitty_one_sentence_turns",
        sa.Column(
            "command_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_kitty_one_sentence_turns_scope_action",
        "kitty_one_sentence_turns",
        ["scope", "action"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
