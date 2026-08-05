"""Case Square cover/PDF job manifesto (cold status per post).

Revision ID: 0092
Revises: 0091
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "case_square_cover_jobs"
_COMMUNITY_READ = "rls_community_read_allowed() OR rls_is_panel_mode() OR rls_is_system_mode()"
_JOB_WRITE = (
    "EXISTS ("
    "SELECT 1 FROM case_square_posts p "
    "WHERE p.id = post_id AND ("
    "p.author_id = rls_current_user_id() "
    "OR rls_is_panel_mode() "
    "OR rls_is_system_mode()"
    "))"
)


def _cover_job_rls() -> None:
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_COMMUNITY_READ})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_write" ON "{_TABLE}" FOR INSERT WITH CHECK ({_JOB_WRITE})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_TABLE}_update" ON "{_TABLE}" FOR UPDATE USING ({_JOB_WRITE}) WITH CHECK ({_JOB_WRITE})'
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_delete" ON "{_TABLE}" FOR DELETE USING ({_JOB_WRITE})'))


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.String(length=32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("attachment_key", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["case_square_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.create_index(f"ix_{_TABLE}_status", _TABLE, ["status"])
    op.create_index(f"ix_{_TABLE}_status_updated", _TABLE, ["status", "updated_at"])
    _cover_job_rls()


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    for suffix in ("delete", "update", "write", "select"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_{suffix}" ON "{_TABLE}"'))
    op.drop_index(f"ix_{_TABLE}_status_updated", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_status", table_name=_TABLE)
    op.drop_table(_TABLE)
