"""Alembic environment configuration for SQLAlchemy migrations.

Uses a **sync** connection (via ``NullPool``) so that ``alembic upgrade``
works both from the CLI *and* when called programmatically inside a running
async event loop (FastAPI lifespan).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from config.database import DATABASE_URL
from models.domain.registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
