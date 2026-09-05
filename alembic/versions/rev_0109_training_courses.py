"""Training course catalog, steps, and COS assets.

Revision ID: 0109
Revises: 0108
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0109"
down_revision: Union[str, None] = "0108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCESS = "rls_is_system_mode()"
_TABLES = ("training_courses", "training_course_steps", "training_course_assets")

DOUBLE_BUBBLE_COURSE_ID = "6f2a1c90-db01-4000-8000-00000000db01"
DOUBLE_BUBBLE_STEP_ID = "6f2a1c90-db01-4000-8000-00000000db02"


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
    if not inspector.has_table("training_courses"):
        op.create_table(
            "training_courses",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("title", pg.JSONB(), nullable=False),
            sa.Column("description", pg.JSONB(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("cover_asset_id", sa.String(length=36), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_training_courses_id", "training_courses", ["id"])
        op.create_index("ix_training_courses_owner_id", "training_courses", ["owner_id"])
        op.create_index("ix_training_courses_status", "training_courses", ["status"])
        op.create_index("ix_training_courses_is_system", "training_courses", ["is_system"])
        op.create_index("ix_training_courses_status_updated", "training_courses", ["status", "updated_at"])

    if not inspector.has_table("training_course_steps"):
        op.create_table(
            "training_course_steps",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("step_type", sa.String(length=20), nullable=False),
            sa.Column("payload", pg.JSONB(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["training_courses.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_training_course_steps_id", "training_course_steps", ["id"])
        op.create_index("ix_training_course_steps_course_id", "training_course_steps", ["course_id"])
        op.create_index(
            "ix_training_course_steps_course_pos",
            "training_course_steps",
            ["course_id", "position"],
        )

    if not inspector.has_table("training_course_assets"):
        op.create_table(
            "training_course_assets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("logical_key", sa.String(length=512), nullable=False),
            sa.Column("mime", sa.String(length=128), nullable=False),
            sa.Column("bytes_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["course_id"], ["training_courses.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_training_course_assets_id", "training_course_assets", ["id"])
        op.create_index("ix_training_course_assets_course_id", "training_course_assets", ["course_id"])
        op.create_index(
            "ix_training_course_assets_course_role",
            "training_course_assets",
            ["course_id", "role"],
        )

    op.execute(
        sa.text(
            """
            INSERT INTO training_courses (
                id, owner_id, title, description, status, is_system, created_at, updated_at
            ) VALUES (
                :id, NULL,
                '{"zh": "双气泡图教程", "en": "Double Bubble Map tutorial"}'::jsonb,
                '{"zh": "对比辨析两个对象。", "en": "Compare and contrast two topics."}'::jsonb,
                'ready', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=DOUBLE_BUBBLE_COURSE_ID)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO training_course_steps (id, course_id, position, step_type, payload)
            VALUES (
                :step_id, :course_id, 0, 'canvas',
                '{"diagram_type": "double_bubble_map", "topic_options": [
                    {"id": "ice-water", "label": "ice vs water", "item_a": "ice", "item_b": "water"},
                    {"id": "ipv4-ipv6", "label": "IPv4 vs IPv6", "item_a": "IPv4", "item_b": "IPv6"}
                ], "overlays": []}'::jsonb
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(step_id=DOUBLE_BUBBLE_STEP_ID, course_id=DOUBLE_BUBBLE_COURSE_ID)
    )

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
    if inspector.has_table("training_course_assets"):
        op.drop_index("ix_training_course_assets_course_role", table_name="training_course_assets")
        op.drop_index("ix_training_course_assets_course_id", table_name="training_course_assets")
        op.drop_index("ix_training_course_assets_id", table_name="training_course_assets")
        op.drop_table("training_course_assets")
    if inspector.has_table("training_course_steps"):
        op.drop_index("ix_training_course_steps_course_pos", table_name="training_course_steps")
        op.drop_index("ix_training_course_steps_course_id", table_name="training_course_steps")
        op.drop_index("ix_training_course_steps_id", table_name="training_course_steps")
        op.drop_table("training_course_steps")
    if inspector.has_table("training_courses"):
        op.drop_index("ix_training_courses_status_updated", table_name="training_courses")
        op.drop_index("ix_training_courses_is_system", table_name="training_courses")
        op.drop_index("ix_training_courses_status", table_name="training_courses")
        op.drop_index("ix_training_courses_owner_id", table_name="training_courses")
        op.drop_index("ix_training_courses_id", table_name="training_courses")
        op.drop_table("training_courses")
