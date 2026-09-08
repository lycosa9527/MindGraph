"""Fix workshop RLS: topic-less messages and DM attachments.

Revision ID: 0111
Revises: 0110
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    WORKSHOP_CHANNEL_EXPR,
    WORKSHOP_CHILD,
    WORKSHOP_ROOT,
    _create_all_policy,
    _drop_policy,
    _enable_force,
)

revision: str = "0111"
down_revision: Union[str, None] = "0110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_MESSAGE_EXPR = (
    "EXISTS (SELECT 1 FROM chat_topics t "
    "JOIN chat_channels c ON c.id = t.channel_id "
    "WHERE t.id = topic_id AND rls_chat_channel_visible(c.organization_id))"
)
_OLD_REACTION_EXPR = (
    "EXISTS (SELECT 1 FROM chat_messages m "
    "JOIN chat_topics t ON t.id = m.topic_id "
    "JOIN chat_channels c ON c.id = t.channel_id "
    "WHERE m.id = message_id AND rls_chat_channel_visible(c.organization_id))"
)
_OLD_ATTACHMENT_EXPR = _OLD_REACTION_EXPR


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(WORKSHOP_ROOT):
        _enable_force(WORKSHOP_ROOT)
        _drop_policy(WORKSHOP_ROOT, "chat_channels_tenant")
        _create_all_policy(WORKSHOP_ROOT, "chat_channels_tenant", WORKSHOP_CHANNEL_EXPR)
    for table, expr in WORKSHOP_CHILD:
        if not inspector.has_table(table):
            continue
        _enable_force(table)
        _drop_policy(table, f"{table}_tenant")
        _create_all_policy(table, f"{table}_tenant", expr)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    old_exprs = {
        "chat_messages": _OLD_MESSAGE_EXPR,
        "message_reactions": _OLD_REACTION_EXPR,
        "file_attachments": _OLD_ATTACHMENT_EXPR,
    }
    for table, expr in old_exprs.items():
        if not inspector.has_table(table):
            continue
        _drop_policy(table, f"{table}_tenant")
        _create_all_policy(table, f"{table}_tenant", expr)
