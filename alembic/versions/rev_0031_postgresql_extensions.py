"""Ensure optional PostgreSQL extensions for observability and text search.

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-09

Runs ``CREATE EXTENSION IF NOT EXISTS`` for ``pg_stat_statements`` and
``pg_trgm``. Each statement runs in its own savepoint so insufficient
privilege on one extension does not abort the migration. Managed databases
often require a superuser or DBA to create extensions; the app role may lack
that right — in that case apply this revision with an admin URL or create
the extensions manually, then re-run migrations.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

_EXTENSION_SQL: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS pg_stat_statements",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
)


def upgrade() -> None:
    bind = op.get_bind()
    for sql in _EXTENSION_SQL:
        try:
            with bind.begin_nested():
                bind.execute(text(sql))
        except ProgrammingError as exc:
            logger.warning("[alembic 0031] Could not run %r (continuing): %s", sql, exc)


def downgrade() -> None:
    """Extensions are left in place; dropping them can break dependents."""
