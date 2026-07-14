"""Case Square tables and RLS policies.

Revision ID: 0084
Revises: 0083
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0084"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMMUNITY_READ = "rls_community_read_allowed()"
POST_WRITE = "author_id = rls_current_user_id() OR rls_is_panel_mode()"
LIKE_WRITE = "user_id = rls_current_user_id()"


def _case_square_rls() -> None:
    tables = [
        ("case_square_posts", COMMUNITY_READ, POST_WRITE),
        ("case_square_post_likes", COMMUNITY_READ, LIKE_WRITE),
    ]
    for table, read_expr, write_expr in tables:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({read_expr})'))
        op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({write_expr})'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({write_expr}) WITH CHECK ({write_expr})'
            )
        )
        op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({write_expr})'))


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("case_square_posts"):
        return

    op.create_table(
        "case_square_posts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("case_type", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=True),
        sa.Column("grade", sa.String(length=50), nullable=True),
        sa.Column("diagram_type", sa.String(length=50), nullable=True),
        sa.Column("spec", pg.JSONB(), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=255), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("is_expert_recommended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expert_recommended_by", sa.Integer(), nullable=True),
        sa.Column("expert_recommended_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["expert_recommended_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_square_posts_author_id", "case_square_posts", ["author_id"])
    op.create_index("ix_case_square_posts_case_type", "case_square_posts", ["case_type"])
    op.create_index("ix_case_square_posts_status", "case_square_posts", ["status"])
    op.create_index("ix_case_square_posts_is_expert_recommended", "case_square_posts", ["is_expert_recommended"])
    op.create_index("ix_case_square_posts_subject", "case_square_posts", ["subject"])
    op.create_index("ix_case_square_posts_grade", "case_square_posts", ["grade"])
    op.create_index("ix_case_square_posts_diagram_type", "case_square_posts", ["diagram_type"])
    op.create_index("ix_case_square_posts_status_created", "case_square_posts", ["status", "created_at"])
    op.create_index(
        "ix_case_square_posts_expert_created",
        "case_square_posts",
        ["is_expert_recommended", "created_at"],
    )

    op.create_table(
        "case_square_post_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["case_square_posts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_square_post_likes_post_id", "case_square_post_likes", ["post_id"])
    op.create_index("ix_case_square_post_likes_user_id", "case_square_post_likes", ["user_id"])
    op.create_index(
        "ix_case_square_post_likes_unique",
        "case_square_post_likes",
        ["post_id", "user_id"],
        unique=True,
    )

    _case_square_rls()

    op.execute(
        sa.text(
            """
            UPDATE thinking_coin_earn_tasks
            SET action_config = '{"route": "/case-square", "icon": "document"}'::jsonb
            WHERE slug = 'publish_case'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("case_square_posts"):
        return
    for table in ("case_square_post_likes", "case_square_posts"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_delete" ON "{table}"'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_update" ON "{table}"'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_write" ON "{table}"'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_select" ON "{table}"'))
    op.drop_table("case_square_post_likes")
    op.drop_table("case_square_posts")
