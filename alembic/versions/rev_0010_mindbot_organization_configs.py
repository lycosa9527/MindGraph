"""MindBot per-organization DingTalk + Dify configuration.

Baseline revision ``0001`` runs ``Base.metadata.create_all``; that may already
create ``organization_mindbot_configs``. Skip ``CREATE TABLE`` when the
relation exists (same pattern as ``0005`` / ``0009``).

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("organization_mindbot_configs"):
        return

    op.create_table(
        "organization_mindbot_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("dingtalk_robot_code", sa.String(length=128), nullable=False),
        sa.Column("dingtalk_app_secret", sa.Text(), nullable=False),
        sa.Column("dingtalk_client_id", sa.String(length=128), nullable=True),
        sa.Column("dify_api_base_url", sa.String(length=512), nullable=False),
        sa.Column("dify_api_key", sa.Text(), nullable=False),
        sa.Column(
            "dify_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_mindbot_config_organization_id"),
        sa.UniqueConstraint("dingtalk_robot_code", name="uq_mindbot_config_robot_code"),
    )
    op.create_index(
        "ix_organization_mindbot_configs_organization_id",
        "organization_mindbot_configs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_mindbot_configs_dingtalk_robot_code",
        "organization_mindbot_configs",
        ["dingtalk_robot_code"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organization_mindbot_configs"):
        return

    op.drop_index(
        "ix_organization_mindbot_configs_dingtalk_robot_code",
        table_name="organization_mindbot_configs",
    )
    op.drop_index(
        "ix_organization_mindbot_configs_organization_id",
        table_name="organization_mindbot_configs",
    )
    op.drop_table("organization_mindbot_configs")
