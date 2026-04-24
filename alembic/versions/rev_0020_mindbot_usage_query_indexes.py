"""MindBot: indexes for usage list/thread queries.

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-16

``ix_mindbot_usage_org_id_desc`` and ``ix_mindbot_usage_dify_conv`` are defined
on the current ORM model and are created by baseline ``0001``. The single-column
``ix_mindbot_usage_dt_conv`` (superseded by 0022) is only created here.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindbot_usage_events"


def _ix_names(conn) -> set[str]:
    return {ix["name"] for ix in sa.inspect(conn).get_indexes(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    idx = _ix_names(bind)

    if "ix_mindbot_usage_org_id_desc" not in idx:
        op.create_index(
            "ix_mindbot_usage_org_id_desc",
            _TABLE,
            ["organization_id", "id"],
        )
    if "ix_mindbot_usage_dt_conv" not in idx:
        op.create_index(
            "ix_mindbot_usage_dt_conv",
            _TABLE,
            ["dingtalk_conversation_id"],
        )
    if "ix_mindbot_usage_dify_conv" not in idx:
        op.create_index(
            "ix_mindbot_usage_dify_conv",
            _TABLE,
            ["dify_conversation_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "ix_mindbot_usage_dify_conv",
        "ix_mindbot_usage_dt_conv",
        "ix_mindbot_usage_org_id_desc",
    ):
        if name in _ix_names(bind):
            op.drop_index(name, table_name=_TABLE)
