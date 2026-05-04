"""Enforce unique active workshop codes.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UNIQUE_INDEX = "ix_diagrams_workshop_code_unique_active"
_OLD_INDEX = "ix_diagrams_workshop_code"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE diagrams
            SET workshop_code = UPPER(TRIM(workshop_code))
            WHERE workshop_code IS NOT NULL
              AND workshop_code <> UPPER(TRIM(workshop_code))
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM diagrams
                    WHERE workshop_code IS NOT NULL
                      AND NOT is_deleted
                    GROUP BY workshop_code
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'duplicate active workshop_code values block migration';
                END IF;
            END
            $$;
            """
        )
    )
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {_UNIQUE_INDEX}
            ON diagrams (workshop_code)
            WHERE workshop_code IS NOT NULL AND NOT is_deleted
            """
        )
        op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{_OLD_INDEX}"')


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_OLD_INDEX}
            ON diagrams (workshop_code)
            """
        )
        op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{_UNIQUE_INDEX}"')
