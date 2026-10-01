"""Learning Space tables and student user columns.

Revision ID: 0121
Revises: 0120
Create Date: 2026-09-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0121"
down_revision: Union[str, None] = "0120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCESS = "rls_is_system_mode() OR rls_is_panel_mode() OR rls_current_user_id() IS NOT NULL"
_TABLES = (
    "learning_pilot_teachers",
    "learning_classes",
    "learning_assignments",
    "learning_submissions",
)


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({_ACCESS})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("learning_pilot_teachers"):
        op.create_table(
            "learning_pilot_teachers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("teacher_user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("teacher_user_id"),
        )
        op.create_index("ix_learning_pilot_teachers_teacher_user_id", "learning_pilot_teachers", ["teacher_user_id"])
        op.create_index("ix_learning_pilot_teachers_organization_id", "learning_pilot_teachers", ["organization_id"])

    if not inspector.has_table("learning_classes"):
        op.create_table(
            "learning_classes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("class_code", sa.String(length=16), nullable=False),
            sa.Column("teacher_user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("max_students", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("class_code"),
        )
        op.create_index("ix_learning_classes_class_code", "learning_classes", ["class_code"])
        op.create_index("ix_learning_classes_teacher_user_id", "learning_classes", ["teacher_user_id"])
        op.create_index("ix_learning_classes_organization_id", "learning_classes", ["organization_id"])

    # users.learning_class_id needs learning_classes to exist first
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "learning_class_id" not in user_cols:
        op.add_column("users", sa.Column("learning_class_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_users_learning_class_id",
            "users",
            "learning_classes",
            ["learning_class_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_users_learning_class_id", "users", ["learning_class_id"])
    if "must_change_password" not in user_cols:
        op.add_column(
            "users",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_learning_class_name_student "
            "ON users (learning_class_id, name) "
            "WHERE role = 'student' AND learning_class_id IS NOT NULL AND name IS NOT NULL"
        )
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_assignments"):
        op.create_table(
            "learning_assignments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("class_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
            sa.Column("template_diagram_id", sa.String(length=36), nullable=False),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column(
                "ai_permissions",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["class_id"], ["learning_classes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_learning_assignments_class_id", "learning_assignments", ["class_id"])
        op.create_index("ix_learning_assignments_template_diagram_id", "learning_assignments", ["template_diagram_id"])
        op.create_index("ix_learning_assignments_created_by", "learning_assignments", ["created_by"])

    if not inspector.has_table("learning_submissions"):
        op.create_table(
            "learning_submissions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("assignment_id", sa.Integer(), nullable=False),
            sa.Column("student_user_id", sa.Integer(), nullable=False),
            sa.Column("diagram_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("due_at_override", sa.DateTime(), nullable=True),
            sa.Column("snapshot_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["assignment_id"], ["learning_assignments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assignment_id", "student_user_id", name="uq_learning_submission_assignment_student"),
        )
        op.create_index("ix_learning_submissions_assignment_id", "learning_submissions", ["assignment_id"])
        op.create_index("ix_learning_submissions_student", "learning_submissions", ["student_user_id"])
        op.create_index("ix_learning_submissions_diagram_id", "learning_submissions", ["diagram_id"])

    inspector = sa.inspect(bind)
    for table in _TABLES:
        if inspector.has_table(table):
            _enable_rls(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in reversed(_TABLES):
        if not inspector.has_table(table):
            continue
        for suffix in ("select", "write", "update", "delete"):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_{suffix}" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    if inspector.has_table("learning_submissions"):
        op.drop_table("learning_submissions")
    if inspector.has_table("learning_assignments"):
        op.drop_table("learning_assignments")

    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_learning_class_name_student"))
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "must_change_password" in user_cols:
        op.drop_column("users", "must_change_password")
    if "learning_class_id" in user_cols:
        op.drop_constraint("fk_users_learning_class_id", "users", type_="foreignkey")
        op.drop_index("ix_users_learning_class_id", table_name="users")
        op.drop_column("users", "learning_class_id")

    if inspector.has_table("learning_classes"):
        op.drop_table("learning_classes")
    if inspector.has_table("learning_pilot_teachers"):
        op.drop_table("learning_pilot_teachers")
