"""Drop unused per-school WeChat login toggle.

WeChat QR login is platform-wide (FEATURE_OAUTH_LOGIN + AppID/Secret).
DingTalk stays on organization_oauth_configs.

Revision ID: 0105
Revises: 0104
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("organization_oauth_configs"):
        return
    columns = {col["name"] for col in inspector.get_columns("organization_oauth_configs")}
    if "wechat_login_enabled" not in columns:
        return
    op.drop_column("organization_oauth_configs", "wechat_login_enabled")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("organization_oauth_configs"):
        return
    columns = {col["name"] for col in inspector.get_columns("organization_oauth_configs")}
    if "wechat_login_enabled" in columns:
        return
    op.add_column(
        "organization_oauth_configs",
        sa.Column(
            "wechat_login_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
