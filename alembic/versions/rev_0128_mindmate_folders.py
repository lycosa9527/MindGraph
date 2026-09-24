"""MindMate conversation folders.

Revision ID: 0128
Revises: 0127
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0128"
down_revision: Union[str, None] = "0127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FOLDER_ACCESS = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"


def _folder_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({FOLDER_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({FOLDER_ACCESS})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE '
            f"USING ({FOLDER_ACCESS}) WITH CHECK ({FOLDER_ACCESS})"
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({FOLDER_ACCESS})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("mindmate_folders"):
        op.create_table(
            "mindmate_folders",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_mindmate_folders_user_sort",
            "mindmate_folders",
            ["user_id", "sort_order"],
        )
        _folder_rls("mindmate_folders")

    if not inspector.has_table("mindmate_conversation_folders"):
        op.create_table(
            "mindmate_conversation_folders",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.String(length=128), nullable=False),
            sa.Column("folder_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["folder_id"], ["mindmate_folders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "conversation_id", name="uq_mindmate_conv_folder_user_conv"),
        )
        op.create_index(
            "ix_mindmate_conv_folder_folder",
            "mindmate_conversation_folders",
            ["folder_id"],
        )
        _folder_rls("mindmate_conversation_folders")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("mindmate_conversation_folders"):
        op.drop_index("ix_mindmate_conv_folder_folder", table_name="mindmate_conversation_folders")
        op.drop_table("mindmate_conversation_folders")

    if inspector.has_table("mindmate_folders"):
        op.drop_index("ix_mindmate_folders_user_sort", table_name="mindmate_folders")
        op.drop_table("mindmate_folders")
