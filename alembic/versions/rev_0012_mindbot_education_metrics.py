"""MindBot usage: educational research columns.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-13

Baseline ``0001`` runs ``Base.metadata.create_all`` and may already create
``dingtalk_chat_scope``, ``inbound_msg_type``, and ``conversation_user_turn`` on
``mindbot_usage_events`` (they exist on the ORM). Only add what is missing so
fresh installs do not fail with ``DuplicateColumn`` — same idea as ``0004`` /
``0008``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindbot_usage_events"
_INDEX = "ix_mindbot_usage_events_chat_scope_org"


def _column_names(conn, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def _index_names(conn, table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(conn).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _column_names(bind, _TABLE)

    if "dingtalk_chat_scope" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_chat_scope", sa.String(length=16), nullable=True),
        )
    if "inbound_msg_type" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("inbound_msg_type", sa.String(length=32), nullable=True),
        )
    if "conversation_user_turn" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("conversation_user_turn", sa.Integer(), nullable=True),
        )

    if _INDEX not in _index_names(bind, _TABLE):
        op.create_index(
            _INDEX,
            _TABLE,
            ["dingtalk_chat_scope", "organization_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _INDEX in _index_names(bind, _TABLE):
        op.drop_index(_INDEX, table_name=_TABLE)

    cols = _column_names(bind, _TABLE)
    if "conversation_user_turn" in cols:
        op.drop_column(_TABLE, "conversation_user_turn")
    if "inbound_msg_type" in cols:
        op.drop_column(_TABLE, "inbound_msg_type")
    if "dingtalk_chat_scope" in cols:
        op.drop_column(_TABLE, "dingtalk_chat_scope")
