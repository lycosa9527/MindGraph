"""ZhiHui conversations + generation slide fields; backfill one conversation per generation.

Revision ID: 0098
Revises: 0097
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError
from sqlalchemy.dialects import postgresql

revision: str = "0098"
down_revision: Union[str, None] = "0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONV = "zhihui_conversations"
_GEN = "zhihui_generations"
_ACCESS = "rls_is_panel_mode() OR rls_is_system_mode()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_CONV):
        op.create_table(
            _CONV,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("mode", sa.String(length=16), nullable=False, server_default="image"),
            sa.Column("title", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("diagram_id", sa.String(length=36), nullable=True),
            sa.Column("diagram_title", sa.String(length=256), nullable=True),
            sa.Column("style_seed", sa.Text(), nullable=True),
            sa.Column("planner_model", sa.String(length=64), nullable=True),
            sa.Column("image_model", sa.String(length=64), nullable=True),
            sa.Column("lesson_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="complete"),
            sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("celery_task_id", sa.String(length=64), nullable=True),
            sa.Column("language", sa.String(length=16), nullable=False, server_default="zh"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_zhihui_conversations_id", _CONV, ["id"])
        op.create_index("ix_zhihui_conversations_user_id", _CONV, ["user_id"])
        op.create_index("ix_zhihui_conversations_organization_id", _CONV, ["organization_id"])
        op.create_index("ix_zhihui_conversations_mode", _CONV, ["mode"])
        op.create_index("ix_zhihui_conversations_diagram_id", _CONV, ["diagram_id"])
        op.create_index("ix_zhihui_conversations_status", _CONV, ["status"])
        op.create_index("ix_zhihui_conversations_created_at", _CONV, ["created_at"])
        op.create_index("ix_zhihui_conversations_updated_at", _CONV, ["updated_at"])
        op.create_index("ix_zhihui_conversations_updated_at_desc", _CONV, ["updated_at"])

        op.execute(sa.text(f'ALTER TABLE "{_CONV}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_CONV}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{_CONV}_select" ON "{_CONV}" FOR SELECT USING ({_ACCESS})'))
        op.execute(sa.text(f'CREATE POLICY "{_CONV}_write" ON "{_CONV}" FOR INSERT WITH CHECK ({_ACCESS})'))
        op.execute(
            sa.text(f'CREATE POLICY "{_CONV}_update" ON "{_CONV}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
        )
        op.execute(sa.text(f'CREATE POLICY "{_CONV}_delete" ON "{_CONV}" FOR DELETE USING ({_ACCESS})'))

    if not inspector.has_table(_GEN):
        return

    gen_cols = {col["name"] for col in inspector.get_columns(_GEN)}
    if "dify_conversation_id" not in gen_cols:
        op.add_column(
            _GEN,
            sa.Column("dify_conversation_id", sa.String(length=100), nullable=True),
        )
    if "slide_index" not in gen_cols:
        op.add_column(_GEN, sa.Column("slide_index", sa.Integer(), nullable=True))
    if "slide_title" not in gen_cols:
        op.add_column(_GEN, sa.Column("slide_title", sa.String(length=256), nullable=True))
    if "focus_node_ids" not in gen_cols:
        op.add_column(
            _GEN,
            sa.Column("focus_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    # Preserve prior Dify conversation ids, then re-point conversation_id to ZhiHui conversations.
    op.execute(
        sa.text(
            f'UPDATE "{_GEN}" SET dify_conversation_id = conversation_id '
            "WHERE conversation_id IS NOT NULL AND dify_conversation_id IS NULL"
        )
    )
    op.execute(sa.text(f'UPDATE "{_GEN}" SET conversation_id = NULL'))

    # Drop legacy index/FK-less wide conversation_id, recreate as 36-char FK.
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(_GEN)}
    if "ix_zhihui_generations_conversation_id" in existing_indexes:
        op.drop_index("ix_zhihui_generations_conversation_id", table_name=_GEN)

    op.alter_column(
        _GEN,
        "conversation_id",
        existing_type=sa.String(length=100),
        type_=sa.String(length=36),
        existing_nullable=True,
    )
    op.create_index("ix_zhihui_generations_conversation_id", _GEN, ["conversation_id"])

    # Backfill: one complete image conversation per existing generation.
    op.execute(
        sa.text(
            f"""
            WITH missing AS (
                SELECT g.id AS generation_id, gen_random_uuid()::text AS conversation_id
                FROM "{_GEN}" g
                WHERE g.conversation_id IS NULL
            ),
            inserted AS (
                INSERT INTO "{_CONV}" (
                    id, user_id, organization_id, mode, title, status, language,
                    image_model, created_at, updated_at
                )
                SELECT
                    m.conversation_id,
                    g.user_id,
                    g.organization_id,
                    'image',
                    LEFT(TRIM(BOTH FROM COALESCE(g.prompt, '')), 256),
                    'complete',
                    COALESCE(NULLIF(g.language, ''), 'zh'),
                    'qwen-image-3.0',
                    COALESCE(g.created_at, CURRENT_TIMESTAMP),
                    COALESCE(g.created_at, CURRENT_TIMESTAMP)
                FROM missing m
                JOIN "{_GEN}" g ON g.id = m.generation_id
                RETURNING id
            )
            UPDATE "{_GEN}" AS g
            SET conversation_id = m.conversation_id, slide_index = COALESCE(g.slide_index, 0)
            FROM missing m
            WHERE g.id = m.generation_id
            """
        )
    )

    # Re-inspect after column alters / backfill — start-of-upgrade inspector is stale.
    inspector = sa.inspect(bind)
    fks = {fk["name"] for fk in inspector.get_foreign_keys(_GEN)}
    if "fk_zhihui_generations_conversation_id" not in fks:
        op.create_foreign_key(
            "fk_zhihui_generations_conversation_id",
            _GEN,
            _CONV,
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_GEN):
        fks = {fk["name"] for fk in inspector.get_foreign_keys(_GEN)}
        if "fk_zhihui_generations_conversation_id" in fks:
            op.drop_constraint("fk_zhihui_generations_conversation_id", _GEN, type_="foreignkey")
        gen_cols = {col["name"] for col in inspector.get_columns(_GEN)}
        for col in ("focus_node_ids", "slide_title", "slide_index", "dify_conversation_id"):
            if col in gen_cols:
                op.drop_column(_GEN, col)
        op.alter_column(
            _GEN,
            "conversation_id",
            existing_type=sa.String(length=36),
            type_=sa.String(length=100),
            existing_nullable=True,
        )

    if inspector.has_table(_CONV):
        for suffix in ("select", "write", "update", "delete"):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "{_CONV}_{suffix}" ON "{_CONV}"'))
        op.execute(sa.text(f'ALTER TABLE "{_CONV}" DISABLE ROW LEVEL SECURITY'))
        for idx in (
            "ix_zhihui_conversations_updated_at_desc",
            "ix_zhihui_conversations_updated_at",
            "ix_zhihui_conversations_created_at",
            "ix_zhihui_conversations_status",
            "ix_zhihui_conversations_diagram_id",
            "ix_zhihui_conversations_mode",
            "ix_zhihui_conversations_organization_id",
            "ix_zhihui_conversations_user_id",
            "ix_zhihui_conversations_id",
        ):
            try:
                op.drop_index(idx, table_name=_CONV)
            except DBAPIError:
                pass
        op.drop_table(_CONV)
