"""Case Square post favorites (user bookmarks).

Revision ID: 0087
Revises: 0086
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMMUNITY_READ = "rls_community_read_allowed()"
FAVORITE_WRITE = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"


def _favorite_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({COMMUNITY_READ})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({FAVORITE_WRITE})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE '
            f"USING ({FAVORITE_WRITE}) WITH CHECK ({FAVORITE_WRITE})"
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({FAVORITE_WRITE})'))


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("case_square_post_favorites"):
        return

    op.create_table(
        "case_square_post_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["case_square_posts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_case_square_post_favorites_post_id",
        "case_square_post_favorites",
        ["post_id"],
    )
    op.create_index(
        "ix_case_square_post_favorites_user_id",
        "case_square_post_favorites",
        ["user_id"],
    )
    op.create_index(
        "ix_case_square_post_favorites_unique",
        "case_square_post_favorites",
        ["post_id", "user_id"],
        unique=True,
    )
    _favorite_rls("case_square_post_favorites")


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("case_square_post_favorites"):
        op.drop_table("case_square_post_favorites")
