"""Baseline schema — captures the full table set from ORM models.

Revision ID: 0001
Revises:
Create Date: 2026-04-02

For fresh installs this creates every table via ``Base.metadata.create_all``.
For existing production databases run ``alembic stamp 0001`` to skip execution.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from models.domain.registry import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    from models.domain.registry import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
