"""MindBot: per-chat chain-of-thought (1:1, internal group, cross-org group).

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-15

Baseline ``0001`` may already have the per-scope boolean columns. Only migrate
data from the legacy single ``show_chain_of_thought`` column when that column
exists.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"
_COLS_NEW = (
    "show_chain_of_thought_oto",
    "show_chain_of_thought_internal_group",
    "show_chain_of_thought_cross_org_group",
)
_COL_OLD = "show_chain_of_thought"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if "show_chain_of_thought_oto" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "show_chain_of_thought_oto",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "show_chain_of_thought_internal_group" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "show_chain_of_thought_internal_group",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "show_chain_of_thought_cross_org_group" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "show_chain_of_thought_cross_org_group",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if _COL_OLD in cols:
        bind.execute(
            text(
                f"UPDATE {_TABLE} SET "
                "show_chain_of_thought_oto = show_chain_of_thought, "
                "show_chain_of_thought_internal_group = show_chain_of_thought, "
                "show_chain_of_thought_cross_org_group = show_chain_of_thought"
            )
        )
        op.drop_column(_TABLE, _COL_OLD)


def downgrade() -> None:
    bind = op.get_bind()

    if _COL_OLD not in {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}:
        op.add_column(
            _TABLE,
            sa.Column(
                _COL_OLD,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    bind.execute(
        text(
            f"UPDATE {_TABLE} SET {_COL_OLD} = "
            "(show_chain_of_thought_oto OR show_chain_of_thought_internal_group OR "
            "show_chain_of_thought_cross_org_group)"
        )
    )
    for name in reversed(_COLS_NEW):
        cur = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
        if name in cur:
            op.drop_column(_TABLE, name)
