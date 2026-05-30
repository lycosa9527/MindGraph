"""Seven-role user system: widen role column and backfill legacy values.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    cols = {c["name"]: c for c in inspector.get_columns("users")}
    role_col = cols.get("role")
    if role_col is not None:
        current_type = role_col.get("type")
        if isinstance(current_type, sa.String) and getattr(current_type, "length", 30) < 30:
            op.alter_column(
                "users",
                "role",
                existing_type=sa.String(length=20),
                type_=sa.String(length=30),
                existing_nullable=False,
            )

    op.execute(sa.text("UPDATE users SET role = 'superadmin' WHERE role = 'admin'"))
    op.execute(sa.text("UPDATE users SET role = 'school_admin' WHERE role = 'manager'"))
    op.execute(sa.text("UPDATE users SET role = 'teacher' WHERE role = 'user'"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    op.execute(sa.text("UPDATE users SET role = 'user' WHERE role IN ('teacher', 'personal_trial', 'personal_paid')"))
    op.execute(sa.text("UPDATE users SET role = 'manager' WHERE role = 'school_admin'"))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role IN ('superadmin', 'platform_bd', 'expert')"))

    cols = {c["name"]: c for c in inspector.get_columns("users")}
    role_col = cols.get("role")
    if role_col is not None:
        current_type = role_col.get("type")
        if isinstance(current_type, sa.String) and getattr(current_type, "length", 20) >= 30:
            op.alter_column(
                "users",
                "role",
                existing_type=sa.String(length=30),
                type_=sa.String(length=20),
                existing_nullable=False,
            )
