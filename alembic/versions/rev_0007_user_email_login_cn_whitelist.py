"""Add email_login_whitelisted_from_cn for CN GeoIP email login policy.

Baseline ORM may already include this column (revision ``0001``). Skip adding
when present.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    cols = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "email_login_whitelisted_from_cn" not in cols:
        if dialect == "sqlite":
            op.add_column(
                "users",
                sa.Column(
                    "email_login_whitelisted_from_cn",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
        else:
            op.add_column(
                "users",
                sa.Column(
                    "email_login_whitelisted_from_cn",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

    op.alter_column(
        "users",
        "email_login_whitelisted_from_cn",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "email_login_whitelisted_from_cn" in cols:
        op.drop_column("users", "email_login_whitelisted_from_cn")
