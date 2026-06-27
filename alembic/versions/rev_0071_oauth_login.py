"""OAuth QR login: organization_oauth_configs and oauth_user_links.

Revision ID: 0071
Revises: 0070
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("organization_oauth_configs"):
        op.create_table(
            "organization_oauth_configs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column(
                "wechat_login_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "dingtalk_login_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("dingtalk_login_app_key", sa.String(length=128), nullable=True),
            sa.Column("dingtalk_login_app_secret", sa.Text(), nullable=True),
            sa.Column("dingtalk_corp_id", sa.String(length=128), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", name="uq_organization_oauth_configs_org"),
        )
        op.create_index(
            "ix_organization_oauth_configs_organization_id",
            "organization_oauth_configs",
            ["organization_id"],
        )

    if not inspector.has_table("oauth_user_links"):
        op.create_table(
            "oauth_user_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("external_id", sa.String(length=128), nullable=False),
            sa.Column("openid", sa.String(length=128), nullable=True),
            sa.Column("nickname", sa.String(length=128), nullable=True),
            sa.Column(
                "linked_via",
                sa.String(length=32),
                nullable=False,
                server_default="self",
            ),
            sa.Column(
                "linked_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "provider",
                "external_id",
                name="uq_oauth_user_links_org_provider_external",
            ),
            sa.UniqueConstraint(
                "organization_id",
                "user_id",
                "provider",
                name="uq_oauth_user_links_org_user_provider",
            ),
        )
        op.create_index(
            "ix_oauth_user_links_organization_id",
            "oauth_user_links",
            ["organization_id"],
        )
        op.create_index(
            "ix_oauth_user_links_user_id",
            "oauth_user_links",
            ["user_id"],
        )
        op.create_index(
            "ix_oauth_user_links_user_org",
            "oauth_user_links",
            ["user_id", "organization_id"],
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
