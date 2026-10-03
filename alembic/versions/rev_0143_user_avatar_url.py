"""Widen users.avatar so a COS image URL can be stored.

Revision ID: 0143
Revises: 0142
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0143"
down_revision: Union[str, None] = "0142"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "avatar",
        existing_type=sa.String(length=50),
        type_=sa.String(length=512),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "avatar",
        existing_type=sa.String(length=512),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
