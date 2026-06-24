"""One MindGraph user per DingTalk staff link within an org."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("dingtalk_staff_links"):
        return

    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("dingtalk_staff_links")}
    if "uq_dingtalk_staff_links_org_user" in unique_names:
        return

    # Keep the newest link per (organization_id, user_id) before adding uniqueness.
    op.execute(
        sa.text(
            """
            DELETE FROM dingtalk_staff_links AS older
            USING dingtalk_staff_links AS keep
            WHERE older.organization_id = keep.organization_id
              AND older.user_id = keep.user_id
              AND older.id < keep.id
            """
        )
    )

    op.create_unique_constraint(
        "uq_dingtalk_staff_links_org_user",
        "dingtalk_staff_links",
        ["organization_id", "user_id"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
