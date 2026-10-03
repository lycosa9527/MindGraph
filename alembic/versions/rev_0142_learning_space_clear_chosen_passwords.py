"""Drop clear-text copies of passwords students have already chosen.

Revision ID: 0142
Revises: 0141
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0142"
down_revision: Union[str, None] = "0141"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET learning_space_login_password = NULL
            WHERE must_change_password IS NOT TRUE
            """
        )
    )


def downgrade() -> None:
    """Chosen passwords are not restored."""
