"""VOD folders and required-course completion.

Revision ID: 0130
Revises: 0129
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0130"
down_revision: Union[str, None] = "0129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCESS = "rls_is_system_mode()"


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({_ACCESS})'))


def _disable_rls(table: str) -> None:
    for suffix in ("select", "write", "update", "delete"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_{suffix}" ON "{table}"'))
    op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("vod_folders"):
        op.create_table(
            "vod_folders",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "name", name="uq_vod_folders_org_name"),
        )
        op.create_index("ix_vod_folders_id", "vod_folders", ["id"])
        op.create_index("ix_vod_folders_organization_id", "vod_folders", ["organization_id"])
        op.create_index("ix_vod_folders_org_name", "vod_folders", ["organization_id", "name"])
    inspector = sa.inspect(bind)
    if inspector.has_table("vod_folders"):
        _enable_rls("vod_folders")

    inspector = sa.inspect(bind)
    if inspector.has_table("vod_media"):
        columns = {column["name"] for column in inspector.get_columns("vod_media")}
        if "folder_id" not in columns:
            op.add_column("vod_media", sa.Column("folder_id", sa.String(length=36), nullable=True))
            op.create_index("ix_vod_media_folder_id", "vod_media", ["folder_id"])
            op.create_foreign_key(
                "fk_vod_media_folder_id",
                "vod_media",
                "vod_folders",
                ["folder_id"],
                ["id"],
                ondelete="SET NULL",
            )

    inspector = sa.inspect(bind)
    if not inspector.has_table("training_course_completions"):
        op.create_table(
            "training_course_completions",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["course_id"], ["training_courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("user_id", "course_id"),
        )
        op.create_index(
            "ix_training_course_completions_course_id",
            "training_course_completions",
            ["course_id"],
        )
    inspector = sa.inspect(bind)
    if inspector.has_table("training_course_completions"):
        _enable_rls("training_course_completions")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("training_course_completions"):
        _disable_rls("training_course_completions")
        op.drop_index("ix_training_course_completions_course_id", table_name="training_course_completions")
        op.drop_table("training_course_completions")
    inspector = sa.inspect(bind)
    if inspector.has_table("vod_media"):
        columns = {column["name"] for column in inspector.get_columns("vod_media")}
        if "folder_id" in columns:
            op.drop_constraint("fk_vod_media_folder_id", "vod_media", type_="foreignkey")
            op.drop_index("ix_vod_media_folder_id", table_name="vod_media")
            op.drop_column("vod_media", "folder_id")
    inspector = sa.inspect(bind)
    if inspector.has_table("vod_folders"):
        _disable_rls("vod_folders")
        op.drop_index("ix_vod_folders_org_name", table_name="vod_folders")
        op.drop_index("ix_vod_folders_organization_id", table_name="vod_folders")
        op.drop_index("ix_vod_folders_id", table_name="vod_folders")
        op.drop_table("vod_folders")
