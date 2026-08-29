"""Store recoverable mgat_ ciphertext so the account modal can show it.

Revision ID: 0107
Revises: 0106
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0107"
down_revision: Union[str, None] = "0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector is None or not inspector.has_table("user_api_tokens"):
        return
    columns = {column["name"] for column in inspector.get_columns("user_api_tokens")}
    if "token_ciphertext" in columns:
        return
    op.add_column(
        "user_api_tokens",
        sa.Column("token_ciphertext", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector is None or not inspector.has_table("user_api_tokens"):
        return
    columns = {column["name"] for column in inspector.get_columns("user_api_tokens")}
    if "token_ciphertext" not in columns:
        return
    op.drop_column("user_api_tokens", "token_ciphertext")
