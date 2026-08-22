"""Tag legacy Voice Notes diagrams with source_channel.

Revision ID: 0104
Revises: 0103
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TITLE_PREFIX = "voice recording_"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("diagrams"):
        return
    columns = {column["name"] for column in inspector.get_columns("diagrams")}
    if "source_channel" not in columns:
        return
    op.execute(
        sa.text(
            """
            UPDATE diagrams
            SET source_channel = 'voice_notes'
            WHERE source_channel IS NULL
              AND starts_with(lower(title), :prefix)
            """
        ).bindparams(prefix=_TITLE_PREFIX)
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("diagrams"):
        return
    columns = {column["name"] for column in inspector.get_columns("diagrams")}
    if "source_channel" not in columns:
        return
    op.execute(
        sa.text(
            """
            UPDATE diagrams
            SET source_channel = NULL
            WHERE source_channel = 'voice_notes'
              AND starts_with(lower(title), :prefix)
            """
        ).bindparams(prefix=_TITLE_PREFIX)
    )
