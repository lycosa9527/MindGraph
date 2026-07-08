"""Case Square RLS: allow panel/system mode for post and like writes (moderation delete).

Revision ID: 0076
Revises: 0075
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.policy_builder import _drop_policy

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POST_WRITE = "author_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"
LIKE_WRITE = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"


def _recreate_write_policies(table: str, write_expr: str) -> None:
    for suffix in ("write", "update", "delete"):
        _drop_policy(table, f"{table}_{suffix}")
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
        _recreate_write_policies("case_square_posts", POST_WRITE)
    if sa.inspect(bind).has_table("case_square_post_likes"):
        _recreate_write_policies("case_square_post_likes", LIKE_WRITE)


def downgrade() -> None:
    bind = op.get_bind()
    legacy_post = "author_id = rls_current_user_id() OR rls_is_panel_mode()"
    legacy_like = "user_id = rls_current_user_id()"
    if sa.inspect(bind).has_table("case_square_posts"):
        _recreate_write_policies("case_square_posts", legacy_post)
    if sa.inspect(bind).has_table("case_square_post_likes"):
        _recreate_write_policies("case_square_post_likes", legacy_like)
