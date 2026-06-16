"""Alembic environment configuration for SQLAlchemy migrations.

Uses a **sync** connection (via ``NullPool``) so that ``alembic upgrade``
works both from the CLI *and* when called programmatically inside a running
async event loop (FastAPI lifespan).
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from config.database import _normalise_db_url
from models.domain.registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _alembic_database_url() -> str:
    """Prefer live ``DATABASE_MIGRATION_URL`` (set by run_migrations / startup bootstrap)."""
    raw = os.getenv("DATABASE_MIGRATION_URL") or os.getenv("DATABASE_URL", "")
    if raw:
        return _normalise_db_url(raw)
    from config.database import DATABASE_MIGRATION_URL

    return DATABASE_MIGRATION_URL


config.set_main_option("sqlalchemy.url", _alembic_database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database.

    A dedicated sync engine with ``NullPool`` is created for the migration
    run and disposed immediately after.  This avoids conflicts with the
    application's connection pool and works regardless of whether an async
    event loop is already running.
    """
    database_url = config.get_main_option("sqlalchemy.url")
    if database_url is None:
        raise RuntimeError("sqlalchemy.url is not configured for Alembic migrations")
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
