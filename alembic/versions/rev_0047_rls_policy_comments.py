"""COMMENT ON POLICY and rollout documentation markers.

Revision ID: 0047
Revises: 0046
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            COMMENT ON FUNCTION rls_org_visible(bigint) IS
                'Tenant org visibility: authenticated same-org, panel readable_org_ids, mindbot_service.';
            COMMENT ON FUNCTION rls_diagram_visible(bigint) IS
                'Diagram row access: owner, same-org workshop/collab, panel modes.';
            """
        )
    )


def downgrade() -> None:
    pass
