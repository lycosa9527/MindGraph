"""Allow compose-draft workshop attachments under RLS.

Revision ID: 0115
Revises: 0114
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    WORKSHOP_ATTACHMENT_EXPR,
    _create_all_policy,
    _drop_policy,
)

revision: str = "0115"
down_revision: Union[str, None] = "0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "file_attachments"
_POLICY = "file_attachments_tenant"
_OLD_EXPR = (
    "("
    "message_id IS NOT NULL AND EXISTS ("
    "SELECT 1 FROM chat_messages m "
    "JOIN chat_channels c ON c.id = m.channel_id "
    "WHERE m.id = message_id AND rls_chat_channel_visible(c.organization_id)"
    ")"
    ") OR ("
    "dm_id IS NOT NULL AND EXISTS ("
    "SELECT 1 FROM direct_messages d "
    "WHERE d.id = dm_id AND ("
    "rls_user_visible(d.sender_id) OR rls_user_visible(d.recipient_id)"
    ")"
    ")"
    ")"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    _drop_policy(_TABLE, _POLICY)
    _create_all_policy(_TABLE, _POLICY, WORKSHOP_ATTACHMENT_EXPR)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    _drop_policy(_TABLE, _POLICY)
    _create_all_policy(_TABLE, _POLICY, _OLD_EXPR)
