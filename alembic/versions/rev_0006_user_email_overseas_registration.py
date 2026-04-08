"""User email + overseas registration columns (nullable phone, zh flag).

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CK_USERS_CONTACT = "ck_users_phone_or_email"
_UQ_USERS_EMAIL = "uq_users_email"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    if dialect == "sqlite":
        op.add_column(
            "users",
            sa.Column(
                "allows_simplified_chinese",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
        )
    else:
        op.add_column(
            "users",
            sa.Column(
                "allows_simplified_chinese",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(length=20),
        nullable=True,
    )

    op.create_unique_constraint(_UQ_USERS_EMAIL, "users", ["email"])
    op.create_check_constraint(
        _CK_USERS_CONTACT,
        "users",
        sa.text("(phone IS NOT NULL) OR (email IS NOT NULL)"),
    )

    op.alter_column(
        "users",
        "allows_simplified_chinese",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(_CK_USERS_CONTACT, "users", type_="check")
    op.drop_constraint(_UQ_USERS_EMAIL, "users", type_="unique")
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.drop_column("users", "allows_simplified_chinese")
    op.drop_column("users", "email")
