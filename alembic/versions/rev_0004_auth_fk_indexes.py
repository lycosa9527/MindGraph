"""Add indexes on FK columns, SET NULL on delete, unique invitation_code.

- Index on users.organization_id (used in every org-scoped query)
- Index on api_keys.organization_id (used in org key management)
- SET NULL on both FK constraints so org deletion never blocks
- UNIQUE on organizations.invitation_code to prevent duplicate codes

Root cause addressed here
-------------------------
Revision ``0001`` runs ``Base.metadata.create_all()``, which already reflects
current ORM definitions: ``index=True`` on ``organization_id`` and
``unique=True`` on ``invitation_code``. Those objects therefore already exist
on fresh installs before ``0004`` runs. This migration originally issued
unconditional ``CREATE INDEX`` / ``UNIQUE`` again, which fails with duplicate
errors. **Legacy databases** upgraded from older schemas may still lack those
objects, so the migration must remain able to create them.

The robust fix is **not** to remove indexes from the ORM (that would regress
``create_all`` for new projects) nor to delete these steps from ``0004``
(which would strand legacy DBs). We **inspect** the live database and only
create indexes or the named unique constraint when missing.

Foreign-key drop/recreate still runs every time so databases that predate
``ON DELETE SET NULL`` on these FKs are corrected; PostgreSQL accepts replacing
an equivalent FK.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USERS_ORG_FK = "users_organization_id_fkey"
_USERS_ORG_IDX = "ix_users_organization_id"

_APIKEYS_ORG_FK = "api_keys_organization_id_fkey"
_APIKEYS_ORG_IDX = "ix_api_keys_organization_id"

_ORG_INVITE_UQ = "uq_organizations_invitation_code"


def _index_names(conn, table: str) -> set[str]:
    """Return index names for ``table`` (baseline create_all may already define them)."""
    return {ix["name"] for ix in sa.inspect(conn).get_indexes(table)}


def _has_unique_on_invitation_code(conn) -> bool:
    """True if ``organizations.invitation_code`` is already under a unique constraint."""
    for uq in sa.inspect(conn).get_unique_constraints("organizations"):
        if uq["column_names"] == ["invitation_code"]:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    user_indexes = _index_names(bind, "users")
    api_indexes = _index_names(bind, "api_keys")

    # -- users.organization_id ------------------------------------------------
    # Drop old FK (no ondelete), re-create with ON DELETE SET NULL.
    op.drop_constraint(_USERS_ORG_FK, "users", type_="foreignkey")
    op.create_foreign_key(
        _USERS_ORG_FK,
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    if _USERS_ORG_IDX not in user_indexes:
        op.create_index(_USERS_ORG_IDX, "users", ["organization_id"])

    # -- api_keys.organization_id ---------------------------------------------
    op.drop_constraint(_APIKEYS_ORG_FK, "api_keys", type_="foreignkey")
    op.create_foreign_key(
        _APIKEYS_ORG_FK,
        "api_keys",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    if _APIKEYS_ORG_IDX not in api_indexes:
        op.create_index(_APIKEYS_ORG_IDX, "api_keys", ["organization_id"])

    # -- organizations.invitation_code ----------------------------------------
    # Baseline ORM uses unique=True on the column (implicit unique constraint name).
    if not _has_unique_on_invitation_code(bind):
        op.create_unique_constraint(_ORG_INVITE_UQ, "organizations", ["invitation_code"])


def downgrade() -> None:
    bind = op.get_bind()
    uq_names = {c["name"] for c in sa.inspect(bind).get_unique_constraints("organizations")}
    if _ORG_INVITE_UQ in uq_names:
        op.drop_constraint(_ORG_INVITE_UQ, "organizations", type_="unique")

    op.drop_index(_APIKEYS_ORG_IDX, table_name="api_keys")
    op.drop_constraint(_APIKEYS_ORG_FK, "api_keys", type_="foreignkey")
    op.create_foreign_key(
        _APIKEYS_ORG_FK,
        "api_keys",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_index(_USERS_ORG_IDX, table_name="users")
    op.drop_constraint(_USERS_ORG_FK, "users", type_="foreignkey")
    op.create_foreign_key(
        _USERS_ORG_FK,
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
    )
