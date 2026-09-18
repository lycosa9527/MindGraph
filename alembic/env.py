"""Alembic environment configuration for SQLAlchemy migrations.

Uses a **sync** connection (via ``NullPool``) so that ``alembic upgrade``
works both from the CLI *and* when called programmatically inside a running
async event loop (FastAPI lifespan).
"""

import os
from logging.config import fileConfig

import sqlalchemy as sa
from sqlalchemy import create_engine, pool

from alembic import context
from alembic.operations import Operations

from config.database import DATABASE_MIGRATION_URL, _normalise_db_url
from models.domain.registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _alembic_database_url() -> str:
    """Prefer live ``DATABASE_MIGRATION_URL`` (set by run_migrations / startup bootstrap)."""
    raw = os.getenv("DATABASE_MIGRATION_URL") or os.getenv("DATABASE_URL", "")
    if raw:
        return _normalise_db_url(raw)
    return DATABASE_MIGRATION_URL


config.set_main_option("sqlalchemy.url", _alembic_database_url())

target_metadata = Base.metadata

_ORIG_ADD_COLUMN = Operations.add_column
_ORIG_CREATE_INDEX = Operations.create_index
_ORIG_CREATE_TABLE = Operations.create_table


def _install_idempotent_schema_ops() -> None:
    """Skip ADD COLUMN / CREATE INDEX / CREATE TABLE when 0001 baseline already applied them."""

    def add_column(self, table_name, column, schema=None, **kw):
        inspector = sa.inspect(self.get_bind())
        if inspector.has_table(table_name, schema=schema):
            names = {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
            if getattr(column, "name", None) in names:
                return None
        return _ORIG_ADD_COLUMN(self, table_name, column, schema=schema, **kw)

    def create_index(self, index_name, table_name, columns, schema=None, unique=False, **kw):
        inspector = sa.inspect(self.get_bind())
        if inspector.has_table(table_name, schema=schema):
            existing = {ix["name"] for ix in inspector.get_indexes(table_name, schema=schema)}
            if index_name in existing:
                return None
        return _ORIG_CREATE_INDEX(self, index_name, table_name, columns, schema=schema, unique=unique, **kw)

    def create_table(self, table_name, *columns, **kw):
        schema = kw.get("schema")
        inspector = sa.inspect(self.get_bind())
        if inspector.has_table(table_name, schema=schema):
            return None
        return _ORIG_CREATE_TABLE(self, table_name, *columns, **kw)

    Operations.add_column = add_column
    Operations.create_index = create_index
    setattr(Operations, "create_table", create_table)


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
    _install_idempotent_schema_ops()
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
