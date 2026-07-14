"""Diagram archive folders and diagrams.folder_id.

Revision ID: 0088
Revises: 0087
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0088"
down_revision: Union[str, None] = "0087"
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

    if not inspector.has_table("diagram_folders"):
        op.create_table(
            "diagram_folders",
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
            "ix_diagram_folders_user_sort",
            "diagram_folders",
            ["user_id", "sort_order"],
        )
        _folder_rls("diagram_folders")

    diagram_cols = {c["name"] for c in inspector.get_columns("diagrams")}
    if "folder_id" not in diagram_cols:
        op.add_column(
            "diagrams",
            sa.Column("folder_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_diagrams_folder_id",
            "diagrams",
            "diagram_folders",
            ["folder_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_diagrams_folder_id", "diagrams", ["folder_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    diagram_cols = {c["name"] for c in inspector.get_columns("diagrams")}
    if "folder_id" in diagram_cols:
        op.drop_index("ix_diagrams_folder_id", table_name="diagrams")
        op.drop_constraint("fk_diagrams_folder_id", "diagrams", type_="foreignkey")
        op.drop_column("diagrams", "folder_id")

    if inspector.has_table("diagram_folders"):
        op.drop_index("ix_diagram_folders_user_sort", table_name="diagram_folders")
        op.drop_table("diagram_folders")
