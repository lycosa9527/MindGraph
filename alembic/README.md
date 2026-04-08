# Alembic Database Migrations

This directory contains Alembic migration scripts for MindGraph's PostgreSQL
schema.

## How It Works

On every application startup, `init_db()` automatically:

1. Compares the database's current Alembic revision against the latest
   migration on disk.
2. If they match — logs "Schema is up to date" and skips (fast no-op).
3. If migrations are pending — acquires a Redis distributed lock (so only
   one Gunicorn worker runs DDL), executes `alembic upgrade head`, and
   releases the lock.  Other workers wait and then verify the schema is
   current.
4. Seeds initial organization data if the table is empty.

**You do not need to run `alembic upgrade head` manually** — the app handles
it.  However, you can still run it from the CLI for debugging or CI pipelines.

## Quick Reference

```bash
# Apply all pending migrations (done automatically on startup)
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history

# Generate a new migration after changing ORM models
alembic revision --autogenerate -m "describe the change"

# Roll back the last migration
alembic downgrade -1
```

## Fresh Install

Set `DATABASE_URL` in `.env` and start the app — migrations run automatically:

```bash
python main.py
```

The baseline migration (`0001`) creates all tables from the ORM models.
Migration `0002` adds FTS and JSONB GIN indexes.

## Existing Production Database

If the database already has the correct schema (tables, columns, indexes),
stamp it at the latest revision without executing any DDL:

```bash
alembic stamp head
```

This writes the current revision to the `alembic_version` table so future
migrations apply correctly.  After stamping, the app will see "Schema is up
to date" on every startup.

## Creating New Migrations

1. Modify models in `models/domain/`.
2. If adding a new model file, register it in `models/domain/registry.py`.
3. Generate a migration:

```bash
alembic revision --autogenerate -m "add foo column to bar table"
```

4. **Review** the generated file under `alembic/versions/` — autogenerate
   can miss renames (sees drop + add) and cannot generate data migrations.
5. Commit the migration file to git.
6. On next app startup the migration applies automatically.

## Multi-Worker Safety

When multiple Gunicorn/Uvicorn workers start simultaneously, a Redis
distributed lock (`lock:mindgraph:alembic_migration`) ensures only one
worker executes DDL.  Others poll the `alembic_version` table until the
migration completes (up to 60 seconds).

If Redis is unavailable (dev/single-worker setup), the lock is skipped and
migration runs directly — safe because there is only one process.

## Directory Layout

```
alembic/
├── env.py              # Runtime environment (engine, metadata)
├── script.py.mako      # Template for new migration files
├── versions/           # Migration scripts (ordered by revision chain)
│   ├── rev_0001_baseline_schema.py
│   └── rev_0002_post_baseline_indexes.py
└── README.md           # This file
```
