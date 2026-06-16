"""Create mindgraph_app / mindgraph_migrate roles and grants (no RLS enable).

Revision ID: 0043
Revises: 0042
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from db_rls.roles_sql import build_create_roles_sql, build_grants_sql

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PASSWORD = "mindgraph_password"


def upgrade() -> None:
    app_password = os.getenv("MINDGRAPH_APP_PASSWORD", _DEFAULT_PASSWORD)
    migrate_password = os.getenv("MINDGRAPH_MIGRATE_PASSWORD", _DEFAULT_PASSWORD)
    try:
        op.execute(sa.text(build_create_roles_sql(app_password, migrate_password)))
    except Exception as exc:
        if "insufficient_privilege" in str(exc).lower():
            raise RuntimeError(
                "Could not create mindgraph_app/mindgraph_migrate (need CREATEROLE or superuser). "
                "Bootstrap roles first: python scripts/db/run_migrations.py → option 4"
            ) from exc
        raise
    op.execute(sa.text(build_grants_sql()))


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
                    REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM mindgraph_app;
                    REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM mindgraph_app;
                    REVOKE USAGE ON SCHEMA public FROM mindgraph_app;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END $$;
            """
        )
    )
