# Celery Setup Guide

MindGraph uses **Celery** for background task processing (Knowledge Space document ingestion, MindMate export jobs, and related RAG pipelines). Celery is **required** when Knowledge Space is enabled — the application will not start without a reachable worker and Redis broker.

## Prerequisites

Install and start dependencies first:

| Service | Guide |
|---------|-------|
| **Redis** (broker + result backend) | [REDIS_SETUP.md](REDIS_SETUP.md) |
| **Qdrant** (vector store; server mode for multi-process) | [QDRANT_SETUP.md](QDRANT_SETUP.md) |
| **PostgreSQL** (document metadata, RLS) | [POSTGRES_SETUP.md](POSTGRES_SETUP.md) |

Recommended first-time stack install (Linux):

```bash
conda activate mindgraph
pip install -r requirements.txt
sudo -E env PATH="$PATH" "$(which python)" scripts/setup/setup.py
cp env.example .env   # then edit .env
```

## Python package

Celery is pinned in [requirements.txt](../requirements.txt). Install with the rest of the app:

```bash
conda activate mindgraph
pip install -r requirements.txt
```

Verify:

```bash
python -c "import celery; print(celery.__version__)"
```

## Configuration (`.env`)

Celery uses **Redis DB 1** by default (DB 0 is application cache). See the `CELERY CONFIGURATION` block in [env.example](../env.example):

```bash
REDIS_URL=redis://localhost:6379/0
REDIS_CELERY_DB=1

# Optional overrides (auto-built from REDIS_HOST / REDIS_PORT / REDIS_CELERY_DB if unset)
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Process monitor restarts the worker if it crashes (default on):

```bash
PROCESS_MONITOR_ENABLED=true
CELERY_MANAGED_BY_APP=true   # default — app starts/stops the worker with main.py
```

Do **not** set `CELERY_MANAGED_BY_APP=false` on WSL or production servers unless you are debugging a standalone worker.

## Running Celery (app-managed)

**You do not start Celery manually.** Install the Python package and run the app:

```bash
conda activate mindgraph
python main.py
```

When `FEATURE_KNOWLEDGE_SPACE=true`, the server launcher:

1. Verifies Celery is installed
2. Starts a worker subprocess (or reuses an existing one on the same Redis broker)
3. Registers shutdown cleanup and process-monitor restarts

Expected log lines:

```
[CELERY] Starting Celery worker for background task processing...
[CELERY] Worker started (PID: xxxxx)
```

If a worker is already running:

```
[CELERY] Found 1 existing Celery worker(s):
[CELERY] ✓ Using existing Celery worker(s), skipping startup
```

Worker logs (Linux):

- `logs/celery_worker.log`
- `logs/celery_worker_error.log`

### Manual worker (debug only)

For isolated Celery debugging, not normal WSL/server operation:

```bash
celery -A config.celery worker --loglevel=info
```

Set `CELERY_MANAGED_BY_APP=false` if you run a long-lived external worker and do not want `main.py` to stop it on exit.

## Why Qdrant server mode?

Embedded Qdrant works for single-process dev only. With Celery, FastAPI and workers must share the same Qdrant server — see [QDRANT_SETUP.md](QDRANT_SETUP.md#why-qdrant-server-concurrent-access-for-background-processing).

## RLS and database access

Celery workers import [config/celery.py](../config/celery.py), which bootstraps PostgreSQL RLS migration URLs on startup (`bootstrap_rls_migration_from_env()`). Sync DB paths use `rls_sync_session(for_celery_user)` — ensure `DATABASE_URL` / `DATABASE_MIGRATION_URL` in `.env` match [POSTGRES_SETUP.md](POSTGRES_SETUP.md).

## Troubleshooting

**Redis connection failed**

- Start Redis: `sudo systemctl start redis-server`
- Confirm `REDIS_URL` and broker DB: `redis-cli -n 1 ping` → `PONG`

**No worker / app exits on startup**

- Ensure Redis is running (`sudo systemctl start redis-server`)
- Start the app: `python main.py` (do not rely on a separate manual worker)
- Check `logs/celery_worker_error.log`

**Worker already running but tasks stall**

- Inspect active workers: `celery -A config.celery inspect active`
- Restart: stop old PIDs, then relaunch worker or `python main.py`

**Copy-paste command sheet (all launch deps)**

```bash
python -m services.infrastructure.utils.launch_commands
```

Includes Redis, Qdrant, Celery, PostgreSQL, Playwright, and Tesseract hints in one place.

## COS mirror

When PyPI is unreachable, a publisher host uploads the Celery wheel to COS; consumers install from COS with the same script used for Qdrant:

```bash
python scripts/db/update_stack_from_cos.py
```

Choose **1) Check both** or **2) Update both from COS**. See `COS_SYNC_*` and `CELERY_TARGET_VERSION` in [env.example](../env.example).

## Related files

| File | Role |
|------|------|
| [config/celery.py](../config/celery.py) | Celery app, logging, RLS bootstrap, worker signals |
| [services/infrastructure/process/_celery_manager.py](../services/infrastructure/process/_celery_manager.py) | Subprocess worker launcher used by `main.py` |
| [services/infrastructure/utils/launch_commands.py](../services/infrastructure/utils/launch_commands.py) | Operator cheatsheet |
| [tasks/](../tasks/) | Celery task modules |
