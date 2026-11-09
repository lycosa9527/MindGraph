"""Reapply the current row-level security catalog.

Dumps from 0166 omit policies. This revision installs them. Later dumps
already contain the policies; ``alembic upgrade head`` is then a no-op
and this function is not run again.

Revision ID: 0167
Revises: 0166
"""

from typing import Sequence, Union

from utils.db_rls.catalog_reapply import reapply_current_rls_policies

revision: str = "0167"
down_revision: Union[str, None] = "0166"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop and recreate the current policy catalog."""
    reapply_current_rls_policies()


def downgrade() -> None:
    """Leave policies in place.

    The catalog is the security state 0166 was supposed to have. Removing it
    would turn row security off for every restored table.
    """
