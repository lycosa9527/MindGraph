"""User email + overseas registration columns (nullable phone, zh flag).

Baseline ``0001`` may already define these columns and constraints on the
``users`` table (current ORM). Each step is applied only when missing so
``upgrade`` succeeds on both legacy databases and fresh ``create_all`` installs.

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


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def _phone_nullable(conn) -> bool:
    for col in sa.inspect(conn).get_columns("users"):
        if col["name"] == "phone":
            return bool(col["nullable"])
    return True


def _has_unique_on_email(conn) -> bool:
    """True if ``email`` is covered by a unique constraint or unique index."""
    insp = sa.inspect(conn)
    for uq in insp.get_unique_constraints("users"):
        if "email" in uq["column_names"]:
            return True
    for ix in insp.get_indexes("users"):
        if ix.get("unique") and "email" in ix.get("column_names", []):
            return True
    return False


def _has_named_unique(conn, name: str) -> bool:
    return any(uq["name"] == name for uq in sa.inspect(conn).get_unique_constraints("users"))


def _has_check_constraint(conn, name: str) -> bool:
    return any(ck["name"] == name for ck in sa.inspect(conn).get_check_constraints("users"))


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    cols = _user_column_names(bind)

    if "email" not in cols:
        op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))

    if "allows_simplified_chinese" not in cols:
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

    if not _phone_nullable(bind):
        op.alter_column(
            "users",
            "phone",
            existing_type=sa.String(length=20),
            nullable=True,
        )

    if not _has_unique_on_email(bind):
        op.create_unique_constraint(_UQ_USERS_EMAIL, "users", ["email"])

    if not _has_check_constraint(bind, _CK_USERS_CONTACT):
        op.create_check_constraint(
            _CK_USERS_CONTACT,
            "users",
            sa.text("(phone IS NOT NULL) OR (email IS NOT NULL)"),
        )

    if "allows_simplified_chinese" in _user_column_names(bind):
        op.alter_column(
            "users",
            "allows_simplified_chinese",
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_check_constraint(bind, _CK_USERS_CONTACT):
        op.drop_constraint(_CK_USERS_CONTACT, "users", type_="check")
    if _has_named_unique(bind, _UQ_USERS_EMAIL):
        op.drop_constraint(_UQ_USERS_EMAIL, "users", type_="unique")
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    cols = _user_column_names(bind)
    if "allows_simplified_chinese" in cols:
        op.drop_column("users", "allows_simplified_chinese")
    if "email" in cols:
        op.drop_column("users", "email")
