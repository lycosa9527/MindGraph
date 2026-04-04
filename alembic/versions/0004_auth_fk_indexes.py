"""Add indexes on FK columns, SET NULL on delete, unique invitation_code.

- Index on users.organization_id (used in every org-scoped query)
- Index on api_keys.organization_id (used in org key management)
- SET NULL on both FK constraints so org deletion never blocks
- UNIQUE on organizations.invitation_code to prevent duplicate codes

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


def upgrade() -> None:
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
    op.create_index(_APIKEYS_ORG_IDX, "api_keys", ["organization_id"])

    # -- organizations.invitation_code ----------------------------------------
    op.create_unique_constraint(
        _ORG_INVITE_UQ, "organizations", ["invitation_code"]
    )


def downgrade() -> None:
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
