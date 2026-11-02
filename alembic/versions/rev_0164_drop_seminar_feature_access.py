"""Drop leftover MindMate seminar feature-access rows.

Seminar and diagram online collaboration are regular services. Rows left from
``feature_mindmate_seminar`` and the older ``feature_mindmate_collab`` key no
longer gate anything.

Revision ID: 0164
Revises: 0163
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0164"
down_revision: Union[str, None] = "0163"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KEYS = ("feature_mindmate_seminar", "feature_mindmate_collab")
_TABLES = (
    "feature_access_org_grants",
    "feature_access_user_grants",
    "feature_access_rules",
)


def _delete_from(table: str) -> None:
    statement = sa.text(f'DELETE FROM "{table}" WHERE feature_key IN (:seminar_key, :collab_key)').bindparams(
        seminar_key=_KEYS[0], collab_key=_KEYS[1]
    )
    op.execute(statement)


def _delete_keys() -> None:
    inspector = sa.inspect(op.get_bind())
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    for table in _TABLES:
        if inspector.has_table(table):
            _delete_from(table)


def upgrade() -> None:
    _delete_keys()


def downgrade() -> None:
    """The keys are not restored. Seminar is no longer a feature grant."""
