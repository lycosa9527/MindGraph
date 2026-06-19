# PostgreSQL Setup Guide for Ubuntu

MindGraph uses **PostgreSQL 18** with **row-level security (RLS)**. The recommended setup path is the migration CLI (`scripts/db/run_migrations.py`), which creates RLS roles, runs Alembic, patches `.env`, and can restore from `backup/`.

For Alembic / RLS internals, see [`alembic/README.md`](../alembic/README.md).

## Why PostgreSQL 18?

PostgreSQL 18 (released September 2025) brings significant performance improvements relevant to MindGraph:

| Improvement | Benefit for MindGraph |
|-------------|----------------------|
| **Up to 3× faster I/O** | Faster diagram loads, auth queries, knowledge space lookups |
| **Skip scan on indexes** | Faster user/diagram searches and filtered queries |
| **Parallel GIN index builds** | Faster full-text search setup |

**Bottom line**: PostgreSQL 18 delivers faster I/O and better query planning for MindGraph's relational data.

## Prerequisites

Before running MindGraph against PostgreSQL:

1. **Python driver** (required for startup checks and migrations):

   ```bash
   pip install psycopg2-binary
   ```

   Or install from project requirements inside your conda/venv.

2. **`.env` file** at the project root (copy from `env.example` if missing):

   ```bash
   cp -n env.example .env
   ```

3. **PostgreSQL client tools** (`psql`, `pg_dump`, `pg_restore`) — included with `postgresql-client-18`.

## Install PostgreSQL 18 (Ubuntu / WSL)

Use the official PostgreSQL APT repository.

**Step 1: Install required packages**

```bash
sudo apt-get install lsb-release curl ca-certificates
```

**Step 2: Add official PostgreSQL repository**

```bash
sudo install -d /usr/share/postgresql-common/pgdg

sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc

echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | \
  sudo tee /etc/apt/sources.list.d/pgdg.list
```

**Step 3: Update and install PostgreSQL 18**

```bash
sudo apt-get update
sudo apt-get install postgresql-18 postgresql-client-18
```

**Step 4: Enable and start PostgreSQL**

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

**Step 5: Verify installation**

```bash
psql --version
sudo -u postgres psql -c "SELECT version();"
```

## Quick start (recommended)

On a **fresh PostgreSQL install**, the migration CLI creates the database, RLS roles, and schema for you (via `sudo -u postgres` peer auth on the Unix socket — no `postgres` role password needed on Ubuntu).

```bash
# From project root, with .env present
cd ~/MindGraph
conda activate python313   # or your venv
PYTHONPATH=. python scripts/db/run_migrations.py
```

Choose **option 4 — Full local setup**. The script will:

- Confirm PostgreSQL is reachable on `POSTGRESQL_PORT` (default `5432`)
- Create **`mindgraph_app`** and **`mindgraph_migrate`** via `sudo -u postgres psql` (enter your Linux password when prompted)
- Run `alembic upgrade head` and seed organizations
- Offer to write **`DATABASE_URL`** / **`DATABASE_MIGRATION_URL`** into `.env`
- Offer to flush Redis (recommended after URL changes)

Then start the app:

```bash
python main.py
```

### Restore from backup instead of empty DB

If you have dumps under `backup/` (or `BACKUP_DIR` in `.env`):

```bash
PYTHONPATH=. python scripts/db/run_migrations.py
```

1. **Option 4** — roles + schema (if the database is empty)
2. **Option 2** — import `mindgraph.postgresql.*.dump` (+ matching `*.dump.manifest.json`)

Stop the MindGraph app before choosing **execute** on import.

## RLS database roles

After setup, MindGraph uses separate PostgreSQL roles for migrations vs runtime:

| Role | Purpose | Used in |
|------|---------|---------|
| **`mindgraph_migrate`** | Alembic DDL, `BYPASSRLS` | `DATABASE_MIGRATION_URL` |
| **`mindgraph_app`** | Application queries; RLS policies enforce tenant isolation | `DATABASE_URL` (production cutover) |
| **`mindgraph_user`** | Legacy dev URL in `env.example`; upgraded to RLS roles by the CLI | Initial `.env` before option 4 patches URLs |

Default passwords match `env.example` (`mindgraph_password`). Override with:

```bash
MINDGRAPH_APP_PASSWORD=your_app_secret
MINDGRAPH_MIGRATE_PASSWORD=your_migrate_secret
```

**Do not** point `DATABASE_MIGRATION_URL` at `mindgraph_app` — Alembic needs a migrate-capable role.

## Configuration (`.env`)

Minimal settings for **external PostgreSQL** (systemd service, not app subprocess):

```bash
POSTGRESQL_MANAGED_BY_APP=false

# After full local setup (option 4), prefer RLS URLs:
DATABASE_URL=postgresql://mindgraph_app:mindgraph_password@localhost:5432/mindgraph
DATABASE_MIGRATION_URL=postgresql://mindgraph_migrate:mindgraph_password@localhost:5432/mindgraph

POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=mindgraph
```

When `POSTGRESQL_MANAGED_BY_APP=true` (default), the app reuses an existing server on `POSTGRESQL_PORT` or starts a local subprocess.

**Superuser URL (optional)** — if `sudo -u postgres` is unavailable:

```bash
PG_ADMIN_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres
```

**Backup folder** (for option 2 import):

```bash
BACKUP_DIR=backup
```

## Migration CLI reference

```bash
PYTHONPATH=. python scripts/db/run_migrations.py
```

| Option | Action |
|--------|--------|
| 1 | Alembic `upgrade head` only |
| 2 | Import backup from `BACKUP_DIR` |
| 3 | Check Alembic revision + RLS status; patch `.env`; flush Redis |
| 4 | **Full local setup** (recommended on fresh install) |
| 5 | Quit |

Status-only shortcut:

```bash
PYTHONPATH=. python scripts/db/check_migration_status.py
```

Standalone dump/import (no menu):

```bash
PYTHONPATH=. python scripts/db/dump_import_postgres.py
```

## Manual setup (alternative)

Only needed if you cannot use the migration CLI.

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE mindgraph;
\c mindgraph
-- Roles are normally created by run_migrations.py / Alembic rev 0043.
-- To create manually, see alembic/rls_roles_sql.py and alembic/README.md.
\q
```

For production, use strong passwords and update `.env` accordingly.

## Verify installation

After option 4 (or manual setup):

```bash
# App runtime role
PGPASSWORD=mindgraph_password psql -h localhost -U mindgraph_app -d mindgraph -c "SELECT 1;"

# Migration role
PGPASSWORD=mindgraph_password psql -h localhost -U mindgraph_migrate -d mindgraph -c "SELECT 1;"
```

Check RLS rollout:

```bash
PYTHONPATH=. python scripts/db/check_migration_status.py
```

Expected: Alembic at head (0053+) and `RLS rollout check: OK`.

## Troubleshooting

### `password authentication failed for user "mindgraph_migrate"` or `"postgres"`

On a **clean install**, MindGraph roles do not exist yet. Do **not** create `mindgraph_user` manually from older docs.

1. Ensure PostgreSQL is running: `sudo systemctl start postgresql`
2. Run `PYTHONPATH=. python scripts/db/run_migrations.py` → **option 4**
3. Enter your **Linux password** when `sudo` prompts (not the PostgreSQL `postgres` role password)

If you see `Password for user postgres:` repeatedly, the script was connecting over TCP (`127.0.0.1`) instead of the Unix socket. Update to the latest `scripts/db/rls_roles_bootstrap.py`, or set `PG_ADMIN_URL` in `.env`:

```bash
PG_ADMIN_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres
```

### `PostgreSQL Python package not installed`

```bash
pip install psycopg2-binary
```

### `sudo postgres psql failed` / no sudo

Set `PG_ADMIN_URL` in `.env` to a superuser connection string (see Configuration above), then retry option 4.

### App refuses to start — RLS roles not ready

```bash
PYTHONPATH=. python scripts/db/run_migrations.py
```

Run **option 3** (status) or **option 4** (full setup). Ensure `.env` has `DATABASE_URL` pointing at `mindgraph_app` after cutover.

## Production tuning (PostgreSQL 18)

PostgreSQL 18 defaults to `io_method = worker`. Example `postgresql.conf` for a dedicated host:

```ini
io_method = worker
max_connections = 150
effective_cache_size = 12GB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
```

**MindGraph pool alignment** (see `env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_ASYNC_POOL_SIZE` | `25` | Async connections per worker |
| `DATABASE_ASYNC_MAX_OVERFLOW` | `10` | Burst headroom per worker |
| `POSTGRESQL_MAX_CONNECTIONS` | `175` | Managed subprocess / pool ceiling |
| `DATABASE_POOL_HARD_ASSERT` | `0` | Set `1` to abort startup when pools exceed `max_connections` |

## Managing PostgreSQL service

```bash
sudo systemctl start postgresql
sudo systemctl stop postgresql
sudo systemctl restart postgresql
sudo systemctl status postgresql
```

## View PostgreSQL logs

```bash
sudo journalctl -u postgresql -f
sudo journalctl -u postgresql -n 100
sudo tail -f /var/log/postgresql/postgresql-18-main.log
```

## Migration from SQLite

After PostgreSQL and RLS setup:

```bash
# DATABASE_URL must point to PostgreSQL in .env
PYTHONPATH=. python scripts/db/migrate_sqlite_to_postgresql.py
```

## Supported Ubuntu versions

The official PostgreSQL APT repository supports Ubuntu Noble (24.04), Jammy (22.04), Focal (20.04), and Mantic (23.10).
