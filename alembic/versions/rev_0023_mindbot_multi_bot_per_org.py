"""MindBot: allow up to 5 bots per organization.

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-20

Changes
-------
1. Drop the unique constraint ``uq_mindbot_config_organization_id`` on
   ``organization_mindbot_configs.organization_id`` so that a single school
   can register up to 5 independent DingTalk bots.

2. Add a plain B-tree index on ``organization_mindbot_configs.organization_id``
   to replace the implicit index that was provided by the unique constraint.
   Without this, ``list_by_organization_id`` and ``count_by_organization_id``
   would require full table scans.

3. Add ``bot_label VARCHAR(64) NULL`` column so admins can give each bot a
   human-readable name (e.g. "Main Bot", "Admissions Bot").

All operations are wrapped in ``IF EXISTS`` / ``IF NOT EXISTS`` guards so the
migration is safe to apply against both fresh and existing databases.
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop unique constraint (also drops its implicit index)
    op.execute(
        "ALTER TABLE organization_mindbot_configs "
        "DROP CONSTRAINT IF EXISTS uq_mindbot_config_organization_id"
    )

    # 2. Add plain index to maintain fast org-scoped lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mindbot_config_organization_id "
        "ON organization_mindbot_configs (organization_id)"
    )

    # 3. Add optional bot label column
    op.execute(
        "ALTER TABLE organization_mindbot_configs "
        "ADD COLUMN IF NOT EXISTS bot_label VARCHAR(64) NULL"
    )


def downgrade() -> None:
    # Remove bot_label column
    op.execute(
        "ALTER TABLE organization_mindbot_configs "
        "DROP COLUMN IF EXISTS bot_label"
    )

    # Drop plain index
    op.execute(
        "DROP INDEX IF EXISTS ix_mindbot_config_organization_id"
    )

    # Restore unique constraint (will fail if duplicate org rows exist)
    op.execute(
        "ALTER TABLE organization_mindbot_configs "
        "ADD CONSTRAINT uq_mindbot_config_organization_id UNIQUE (organization_id)"
    )
