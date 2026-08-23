"""Index oauth_user_links for unscoped WeChat login lookup.

Revision ID: 0106
Revises: 0105
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: Union[str, None] = "0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("oauth_user_links"):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("oauth_user_links")}
    if "ix_oauth_user_links_provider_external" in indexes:
        return
    op.create_index(
        "ix_oauth_user_links_provider_external",
        "oauth_user_links",
        ["provider", "external_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("oauth_user_links"):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("oauth_user_links")}
    if "ix_oauth_user_links_provider_external" not in indexes:
        return
    op.drop_index("ix_oauth_user_links_provider_external", table_name="oauth_user_links")
