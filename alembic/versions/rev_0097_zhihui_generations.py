"""ZhiHui (智绘) generation history table + RLS.

Revision ID: 0097
Revises: 0096
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "zhihui_generations"
_ACCESS = "rls_is_panel_mode() OR rls_is_system_mode()"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("enhanced_prompt", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="zh"),
        sa.Column("conversation_id", sa.String(length=100), nullable=True),
        sa.Column("dify_user_id", sa.String(length=256), nullable=True),
        sa.Column("cos_logical_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False, server_default="image/jpeg"),
        sa.Column("size", sa.String(length=32), nullable=True),
        sa.Column("api_key_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zhihui_generations_id", _TABLE, ["id"])
    op.create_index("ix_zhihui_generations_user_id", _TABLE, ["user_id"])
    op.create_index("ix_zhihui_generations_organization_id", _TABLE, ["organization_id"])
    op.create_index("ix_zhihui_generations_created_at", _TABLE, ["created_at"])
    op.create_index("ix_zhihui_generations_created_at_desc", _TABLE, ["created_at"])

    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_write" ON "{_TABLE}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{_TABLE}_update" ON "{_TABLE}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_delete" ON "{_TABLE}" FOR DELETE USING ({_ACCESS})'))


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    for suffix in ("select", "write", "update", "delete"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_{suffix}" ON "{_TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_zhihui_generations_created_at_desc", table_name=_TABLE)
    op.drop_index("ix_zhihui_generations_created_at", table_name=_TABLE)
    op.drop_index("ix_zhihui_generations_organization_id", table_name=_TABLE)
    op.drop_index("ix_zhihui_generations_user_id", table_name=_TABLE)
    op.drop_index("ix_zhihui_generations_id", table_name=_TABLE)
    op.drop_table(_TABLE)
