"""Tencent VOD catalog table.

Revision ID: 0113
Revises: 0112
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0113"
down_revision: Union[str, None] = "0112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCESS = "rls_is_system_mode()"
_TABLE = "vod_media"


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({_ACCESS})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("file_id", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("cover_file_id", sa.String(length=64), nullable=True),
            sa.Column("class_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source_context", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "file_id", name="uq_vod_media_org_file_id"),
        )
        op.create_index("ix_vod_media_id", _TABLE, ["id"])
        op.create_index("ix_vod_media_organization_id", _TABLE, ["organization_id"])
        op.create_index("ix_vod_media_owner_id", _TABLE, ["owner_id"])
        op.create_index("ix_vod_media_status", _TABLE, ["status"])
        op.create_index(
            "ix_vod_media_org_status_updated",
            _TABLE,
            ["organization_id", "status", "updated_at"],
        )

    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        _enable_rls(_TABLE)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    for suffix in ("select", "write", "update", "delete"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_{suffix}" ON "{_TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_vod_media_org_status_updated", table_name=_TABLE)
    op.drop_index("ix_vod_media_status", table_name=_TABLE)
    op.drop_index("ix_vod_media_owner_id", table_name=_TABLE)
    op.drop_index("ix_vod_media_organization_id", table_name=_TABLE)
    op.drop_index("ix_vod_media_id", table_name=_TABLE)
    op.drop_table(_TABLE)
