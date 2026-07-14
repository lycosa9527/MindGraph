"""Case Square admin: grants, field options, audit, proxy publish columns.

Revision ID: 0085
Revises: 0084
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0085"
down_revision: Union[str, None] = "0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PANEL_RW = "rls_is_panel_mode()"

SUBJECTS = [
    "数学",
    "语文",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "政治",
    "信息技术",
    "跨学科",
    "其他",
]

GRADES = [
    "一年级",
    "二年级",
    "三年级",
    "四年级",
    "五年级",
    "六年级",
    "七年级",
    "八年级",
    "九年级",
    "高一",
    "高二",
    "高三",
]

RECOMMENDED_TAGS = [
    "思维训练",
    "项目化学习",
    "大单元教学",
    "跨学科",
    "双减",
    "素养导向",
]


def _panel_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({PANEL_RW})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({PANEL_RW})'))
    op.execute(
        sa.text(f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({PANEL_RW}) WITH CHECK ({PANEL_RW})')
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({PANEL_RW})'))


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("case_square_posts"):
        return

    with op.batch_alter_table("case_square_posts") as batch:
        batch.add_column(
            sa.Column("submitted_by_id", sa.Integer(), nullable=True),
        )
        batch.add_column(
            sa.Column("publish_source", sa.String(length=20), server_default="self", nullable=False),
        )
        batch.add_column(sa.Column("attribution", pg.JSONB(), nullable=True))
        batch.create_foreign_key(
            "fk_case_square_posts_submitted_by_id",
            "users",
            ["submitted_by_id"],
            ["id"],
        )

    op.execute(sa.text("UPDATE case_square_posts SET submitted_by_id = author_id WHERE submitted_by_id IS NULL"))
    op.alter_column("case_square_posts", "submitted_by_id", nullable=False)
    op.create_index("ix_case_square_posts_submitted_by_id", "case_square_posts", ["submitted_by_id"])
    op.create_index("ix_case_square_posts_publish_source", "case_square_posts", ["publish_source"])

    if not sa.inspect(bind).has_table("case_square_staff_grants"):
        op.create_table(
            "case_square_staff_grants",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("permissions", pg.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("granted_by", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_case_square_staff_grants_user_id"),
        )
        op.create_index("ix_case_square_staff_grants_user_id", "case_square_staff_grants", ["user_id"])
        _panel_rls("case_square_staff_grants")

    if not sa.inspect(bind).has_table("case_square_field_options"):
        op.create_table(
            "case_square_field_options",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("category", sa.String(length=30), nullable=False),
            sa.Column("value", sa.String(length=100), nullable=False),
            sa.Column("label_zh", sa.String(length=100), nullable=True),
            sa.Column("label_en", sa.String(length=100), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("category", "value", name="uq_case_square_field_options_category_value"),
        )
        op.create_index(
            "ix_case_square_field_options_category_sort",
            "case_square_field_options",
            ["category", "sort_order"],
        )
        _panel_rls("case_square_field_options")

        field_table = sa.table(
            "case_square_field_options",
            sa.column("category", sa.String),
            sa.column("value", sa.String),
            sa.column("label_zh", sa.String),
            sa.column("sort_order", sa.Integer),
            sa.column("is_active", sa.Boolean),
        )
        rows = []
        for idx, value in enumerate(SUBJECTS):
            rows.append(
                {"category": "subject", "value": value, "label_zh": value, "sort_order": idx, "is_active": True}
            )
        for idx, value in enumerate(GRADES):
            rows.append({"category": "grade", "value": value, "label_zh": value, "sort_order": idx, "is_active": True})
        for idx, value in enumerate(RECOMMENDED_TAGS):
            rows.append(
                {
                    "category": "recommended_tag",
                    "value": value,
                    "label_zh": value,
                    "sort_order": idx,
                    "is_active": True,
                }
            )
        op.bulk_insert(field_table, rows)

    if not sa.inspect(bind).has_table("case_square_audit_log"):
        op.create_table(
            "case_square_audit_log",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("post_id", sa.String(length=36), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("payload", pg.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_case_square_audit_log_post_id", "case_square_audit_log", ["post_id"])
        op.create_index("ix_case_square_audit_log_actor_id", "case_square_audit_log", ["actor_id"])
        op.create_index("ix_case_square_audit_log_action", "case_square_audit_log", ["action"])
        op.create_index("ix_case_square_audit_log_created_at", "case_square_audit_log", ["created_at"])
        _panel_rls("case_square_audit_log")


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "case_square_audit_log",
        "case_square_field_options",
        "case_square_staff_grants",
    ):
        if sa.inspect(bind).has_table(table):
            op.drop_table(table)

    if sa.inspect(bind).has_table("case_square_posts"):
        with op.batch_alter_table("case_square_posts") as batch:
            batch.drop_index("ix_case_square_posts_publish_source")
            batch.drop_index("ix_case_square_posts_submitted_by_id")
            batch.drop_constraint("fk_case_square_posts_submitted_by_id", type_="foreignkey")
            batch.drop_column("attribution")
            batch.drop_column("publish_source")
            batch.drop_column("submitted_by_id")
