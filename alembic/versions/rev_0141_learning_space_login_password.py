"""Store classroom student login passwords for teacher roster lookup.

Revision ID: 0141
Revises: 0140
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from services.learning_space.passwords import initial_password_from_name

revision: str = "0141"
down_revision: Union[str, None] = "0140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "learning_space_login_password" not in ucols:
        op.add_column(
            "users",
            sa.Column("learning_space_login_password", sa.String(length=128), nullable=True),
        )

    rows = bind.execute(
        sa.text(
            """
            SELECT id, name, learning_space_login_password
            FROM users
            WHERE role = 'student' AND learning_class_id IS NOT NULL
            """
        )
    ).all()
    for row in rows:
        if (row.learning_space_login_password or "").strip():
            continue
        plain = initial_password_from_name(row.name or "")
        bind.execute(
            sa.text(
                """
                UPDATE users
                SET learning_space_login_password = :plain
                WHERE id = :user_id
                """
            ),
            {"plain": plain, "user_id": int(row.id)},
        )


def downgrade() -> None:
    """Additive-only; dropping may discard teacher-visible password snapshots."""
