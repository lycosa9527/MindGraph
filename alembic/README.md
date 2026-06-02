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
# Preferred: operator CLI (starts PG, resolves migrate URL, verifies RLS)
PYTHONPATH=. python scripts/db/run_migrations.py

# Manual Alembic (same env as the app — not ~/.local/bin/alembic on another Python)
export PYTHONPATH="${PWD}:${PYTHONPATH}"
# load .env first; set DATABASE_MIGRATION_URL or mindgraph_user URL
python -m alembic upgrade head

# Check current revision
python -m alembic current
```

## PostgreSQL RLS (revisions 0042–0049)

Row-level security uses two database roles:

- **`mindgraph_migrate`** — `DATABASE_MIGRATION_URL`; runs Alembic with `BYPASSRLS`.
- **`mindgraph_app`** — production `DATABASE_URL` after cutover; policies enforce tenant isolation.

**Operator entry point:** `python scripts/db/run_migrations.py` auto-resolves the migrate URL,
verifies RLS through 0049, can patch `.env`, and optionally flush Redis (option 3 or after migrate).
Shortcut: `PYTHONPATH=. python scripts/db/check_migration_status.py`. `main.py` also auto-resolves
`DATABASE_MIGRATION_URL` on startup when only `mindgraph_app` is configured.

RLS SQL helpers live in `alembic/rls_functions_sql.py` and `alembic/rls_policy_builder.py`.
They are registered via [`alembic/migration_support.py`](migration_support.py) (PyPI `alembic`
name clash). `alembic/env.py` loads that module directly — not via `utils.db` — to avoid
importing the FastAPI/RLS stack during CLI migrations.

Never enable RLS without policies in the same migration. See [`docs/db-rls-rollout.md`](../docs/db-rls-rollout.md).

`pg_dump` backups use `--no-policies`; restore as migrate, then `alembic upgrade head`.

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
