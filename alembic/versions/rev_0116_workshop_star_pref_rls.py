"""Workshop star and topic-pref RLS must follow visible channels.

Revision ID: 0116
Revises: 0115
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    WORKSHOP_STAR_EXPR,
    WORKSHOP_TOPIC_PREF_EXPR,
    _create_all_policy,
    _drop_policy,
    _enable_force,
)

revision: str = "0116"
down_revision: Union[str, None] = "0115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_OWNER_EXPR = "rls_user_visible(user_id)"
_TABLES = (
    ("starred_messages", WORKSHOP_STAR_EXPR),
    ("user_topic_preferences", WORKSHOP_TOPIC_PREF_EXPR),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, expr in _TABLES:
        if not inspector.has_table(table):
            continue
        _enable_force(table)
        _drop_policy(table, f"{table}_tenant")
        _create_all_policy(table, f"{table}_tenant", expr)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, _expr in _TABLES:
        if not inspector.has_table(table):
            continue
        _drop_policy(table, f"{table}_tenant")
        _create_all_policy(table, f"{table}_tenant", _OLD_OWNER_EXPR)
