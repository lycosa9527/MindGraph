"""RLS helper functions (STABLE; not LEAKPROOF — uses current_setting / table reads).

Revision ID: 0042
Revises: 0041
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from alembic.rls_functions_sql import (
    RLS_FUNCTIONS_DOWNGRADE,
    rls_functions_upgrade_statements,
)

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(sa.text(statement))
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
                    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mindgraph_app;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(RLS_FUNCTIONS_DOWNGRADE))
