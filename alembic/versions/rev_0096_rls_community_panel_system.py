"""RLS: community posts/likes/comments allow panel and system writes.

Authenticated like/comment counters update another author's post row.
Moderation and user-delete cascades remove other users' likes/comments.
Match case-square engagement policies (rev_0086).

Revision ID: 0096
Revises: 0095
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.policy_builder import _drop_policy

revision: str = "0096"
down_revision: Union[str, None] = "0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POST_WRITE = "author_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"
LIKE_WRITE = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"
COMMENT_WRITE = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"

_LEGACY_POST = "author_id = rls_current_user_id() OR rls_is_panel_mode()"
_LEGACY_LIKE = "user_id = rls_current_user_id()"
_LEGACY_COMMENT = "user_id = rls_current_user_id() OR rls_is_panel_mode()"


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
    inspector = sa.inspect(bind)
    if inspector.has_table("community_posts"):
        _recreate_write_policies("community_posts", POST_WRITE)
    if inspector.has_table("community_post_likes"):
        _recreate_write_policies("community_post_likes", LIKE_WRITE)
    if inspector.has_table("community_post_comments"):
        _recreate_write_policies("community_post_comments", COMMENT_WRITE)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("community_posts"):
        _recreate_write_policies("community_posts", _LEGACY_POST)
    if inspector.has_table("community_post_likes"):
        _recreate_write_policies("community_post_likes", _LEGACY_LIKE)
    if inspector.has_table("community_post_comments"):
        _recreate_write_policies("community_post_comments", _LEGACY_COMMENT)
