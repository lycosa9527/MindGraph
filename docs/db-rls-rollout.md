# PostgreSQL RLS rollout

## Code layout

| Path | Purpose |
|------|---------|
| `alembic/migration_support.py` | Registers `rls_functions_sql` / `rls_policy_builder` on `sys.modules` |
| `utils/db/alembic_migration.py` | Import surface for app, tests, and `alembic/env.py` |
| `scripts/db/migration_urls.py` | Auto-resolve `DATABASE_MIGRATION_URL` for `run_migrations.py` |

## Roles

| Role | Env | Purpose |
|------|-----|---------|
| `mindgraph_app` | `DATABASE_URL` | FastAPI/Celery runtime; **no** `BYPASSRLS` |
| `mindgraph_migrate` | `DATABASE_MIGRATION_URL` | Alembic, org seed, admin merge; **BYPASSRLS** |

## Phase 0 (safe on existing DB)

1. Deploy app with `utils/db/rls_context.py` and middleware context wiring.
2. Keep `DATABASE_URL` on legacy `mindgraph_user` until staging proves RLS.
3. `SET LOCAL app.*` is harmless while RLS is disabled.

## Phase 1 (staging)

1. `python scripts/db/run_migrations.py` — starts local Postgres if needed, auto-sets `DATABASE_MIGRATION_URL` (`mindgraph_migrate` / `mindgraph_user`) even when `.env` already has `DATABASE_URL=mindgraph_app`, runs `alembic upgrade head` through 0049, verifies RLS, optionally patches `.env`.
   - **Option 3** — check Alembic revision + RLS status, bootstrap roles if missing, patch `.env`, optional Redis `FLUSHDB`
   - Shortcut: `PYTHONPATH=. python scripts/db/check_migration_status.py` (same as option 3)
   - Subprocess Postgres **stays running** after CLI exit (default). Set `MINDGRAPH_STOP_POSTGRES_ON_EXIT=1` to stop it on exit.
2. Confirm `.env`: `DATABASE_URL` → `mindgraph_app`, `DATABASE_MIGRATION_URL` → `mindgraph_migrate` (script can write these on prompt).
3. Point app at `mindgraph_app` and restart.
4. Run `tests/db/test_rls_*.py` and manual smoke (see plan §L).
5. Flush Redis diagram/user/org caches once.

## Phase 2 (production)

1. Maintenance optional; switch `DATABASE_URL` to `mindgraph_app`.
2. Enable `RLS_CONTEXT_STRICT=1` in staging first; fix any ERROR logs for missing context.
3. Monitor 5xx, empty lists, Celery knowledge queue, MindBot callbacks.

## Rollback

1. Revert app deploy.
2. `alembic downgrade 0041` as migrate role (drops policies).
3. Restore previous `DATABASE_URL` if needed.
4. Flush Redis caches.

## Dump / restore (PG 18.3)

- `pg_dump` uses `--no-policies` (policies come from Alembic, not dumps).
- Restore as `mindgraph_migrate`, then `alembic upgrade head`.
- Admin PG merge (`services/admin/pg_merge_service.py`, `services/admin/pg_merge_staging.py`) restores into a temporary schema and writes to live via `mindgraph_migrate` (BYPASSRLS); never rely on dumped policies or extensions.

## Staging smoke (manual, before prod)

| Check | Expected |
|-------|----------|
| Teacher login + diagram list/create | Library not empty |
| Knowledge upload + Celery | Task completes |
| Workshop channels + message | Org + announce channels |
| School admin users tab | Own org only |
| Expert invites | Invited orgs only |
| Superadmin org stats | With `organization_id` param |
| `GET /organizations` | Registration dropdown |
| Dashboard passkey stats | Non-zero counts |
| MindBot callback URL | 200 + usage row |
| Online collab join | Participant sees shared diagram |
| ESP32 device register + status poll | Register succeeds; status returns watch row |
| Smart Response device admin list | Superadmin sees all devices |

## Lint

```bash
python scripts/lint/lint_rls_session.py
```

Flags bare `AsyncSessionLocal()` outside `user_rls_session` / `actor_rls_session` / `system_rls_session` helpers.
