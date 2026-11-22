"""Clip-teaching lessons, timeline chapters, and organization comments.

Revision ID: 0173
Revises: 0172
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.clip_lesson_policies import install_clip_lesson_policies

revision: str = "0173"
down_revision: Union[str, None] = "0172"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LESSONS = "clip_lessons"
_CHAPTERS = "clip_lesson_chapters"
_COMMENTS = "clip_lesson_comments"


def upgrade() -> None:
    """Create the clip-teaching tables and their organization policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_LESSONS):
        op.create_table(
            _LESSONS,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("vod_media_id", sa.String(length=36), nullable=True),
            sa.Column("trim_start_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("trim_end_ms", sa.Integer(), nullable=True),
            sa.Column("deck_key", sa.String(length=256), nullable=True),
            sa.Column("preview_pdf_key", sa.String(length=256), nullable=True),
            sa.Column("preview_status", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["vod_media_id"], ["vod_media.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_clip_lessons_organization_id", _LESSONS, ["organization_id"])
        op.create_index("ix_clip_lessons_owner_id", _LESSONS, ["owner_id"])
        op.create_index("ix_clip_lessons_org_updated", _LESSONS, ["organization_id", "updated_at"])
    if not inspector.has_table(_CHAPTERS):
        op.create_table(
            _CHAPTERS,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("lesson_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=80), nullable=False),
            sa.Column("start_ms", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["lesson_id"], ["clip_lessons.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lesson_id", "start_ms", name="uq_clip_lesson_chapters_start"),
        )
        op.create_index("ix_clip_lesson_chapters_lesson_id", _CHAPTERS, ["lesson_id"])
    if not inspector.has_table(_COMMENTS):
        op.create_table(
            _COMMENTS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("lesson_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["lesson_id"], ["clip_lessons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["clip_lesson_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_clip_lesson_comments_lesson_id", _COMMENTS, ["lesson_id"])
        op.create_index("ix_clip_lesson_comments_user_id", _COMMENTS, ["user_id"])
        op.create_index("ix_clip_lesson_comments_parent_id", _COMMENTS, ["parent_id"])
    install_clip_lesson_policies()


def downgrade() -> None:
    """Drop clip-teaching tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in (_COMMENTS, _CHAPTERS, _LESSONS):
        if inspector.has_table(table):
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
            op.drop_table(table)
            inspector = sa.inspect(bind)
