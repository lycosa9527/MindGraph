"""Set Beijing Bayi school org display_name for SSO sidebar subtitle.

Uses organization id = 5. No-op where the row does not exist (UPDATE affects 0 rows).

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_ORG_ID = 5
_TARGET_DISPLAY_NAME = "北京八一学校"


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE organizations SET display_name = :display_name WHERE id = :org_id").bindparams(
            org_id=_TARGET_ORG_ID,
            display_name=_TARGET_DISPLAY_NAME,
        )
    )


def downgrade() -> None:
    """Display name history is not tracked; leave row unchanged on downgrade."""
