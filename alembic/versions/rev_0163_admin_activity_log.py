"""Admin activity log for system settings.

Revision ID: 0163
Revises: 0162
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0163"
down_revision: Union[str, None] = "0162"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "admin_activity_log"

_SELECT_USING = (
    "rls_is_system_mode() OR ("
    "rls_is_panel_mode() AND coalesce(rls_setting_text('app.role'), '') IN ('superadmin', 'admin')"
    ")"
)


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("actor_label", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("http_method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_activity_log_created_at", _TABLE, ["created_at"])
    op.create_index("ix_admin_activity_log_action", _TABLE, ["action"])
    op.create_index("ix_admin_activity_log_actor_role", _TABLE, ["actor_role"])
    op.create_index("ix_admin_activity_log_actor_user_id", _TABLE, ["actor_user_id"])
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_SELECT_USING})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_insert" ON "{_TABLE}" FOR INSERT WITH CHECK (rls_is_system_mode())'))


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_insert" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_select" ON "{_TABLE}"'))
    op.drop_index("ix_admin_activity_log_actor_user_id", table_name=_TABLE)
    op.drop_index("ix_admin_activity_log_actor_role", table_name=_TABLE)
    op.drop_index("ix_admin_activity_log_action", table_name=_TABLE)
    op.drop_index("ix_admin_activity_log_created_at", table_name=_TABLE)
    op.drop_table(_TABLE)
