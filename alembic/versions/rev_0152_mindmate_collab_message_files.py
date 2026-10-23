"""Hide seminar chat attachments from the shared resource list.

Revision ID: 0152
Revises: 0151
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0152"
down_revision: Union[str, None] = "0151"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_background_files"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "listed" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("listed", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "listed" in cols:
        op.drop_column(_TABLE, "listed")
