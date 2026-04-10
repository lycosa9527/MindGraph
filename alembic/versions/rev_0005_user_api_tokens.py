"""Create user_api_tokens table for OpenClaw / programmatic user tokens.

Baseline revision ``0001`` runs ``create_all`` from the ORM; that may already
create ``user_api_tokens``. Skip ``CREATE TABLE`` when the relation exists so
fresh installs do not duplicate the table (same pattern as ``0004``).

Downgrade drops the table if present; if the table was created by ``0001`` and
this upgrade was a no-op, downgrading still removes the table—avoid
``alembic downgrade`` on ORM-first DBs without a backup.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("user_api_tokens"):
        return

    op.create_table(
        "user_api_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_api_tokens_user_id"),
        sa.UniqueConstraint("token_hash", name="uq_user_api_tokens_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("user_api_tokens")
