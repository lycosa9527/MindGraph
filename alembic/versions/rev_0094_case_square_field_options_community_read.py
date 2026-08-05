"""Allow authenticated reads of Case Square field options catalog.

Admin field CRUD stays panel-only. Publish/filter UIs load options via
GET /api/showcase/meta under normal user RLS; panel-only SELECT hid all
rows so meta fell back to hardcoded subjects/grades (recommended tags empty).

Matches case_square_post_favorites catalog-read pattern
(rls_community_read_allowed). Greenfield installs get the same policy from
rev_0085; this revision repairs databases created before that correction.

Revision ID: 0094
Revises: 0093
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "case_square_field_options"
_SELECT_POLICY = f"{_TABLE}_select"
_CATALOG_READ = "rls_community_read_allowed()"
_PANEL_ONLY = "rls_is_panel_mode()"


def upgrade() -> None:
    """Open SELECT so authenticated meta/publish can read active field options."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return

    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_SELECT_POLICY}" ON "{_TABLE}"'))
    op.execute(sa.text(f'CREATE POLICY "{_SELECT_POLICY}" ON "{_TABLE}" FOR SELECT USING ({_CATALOG_READ})'))


def downgrade() -> None:
    """Restore panel-only SELECT on field options."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return

    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_SELECT_POLICY}" ON "{_TABLE}"'))
    op.execute(sa.text(f'CREATE POLICY "{_SELECT_POLICY}" ON "{_TABLE}" FOR SELECT USING ({_PANEL_ONLY})'))
