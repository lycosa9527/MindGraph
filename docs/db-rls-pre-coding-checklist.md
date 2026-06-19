# RLS pre-coding checklist (implementation sign-off)

Marked complete for the codebase implementation pass. Staging must still run manual smoke in [db-rls-rollout.md](db-rls-rollout.md).

## A. Migrations and core

- [x] `alembic/versions/rev_0042`–`0048`
- [x] `config/database.py` — migrate URL, listeners, seed, `get_async_db`
- [x] `alembic/env.py`, `env.example`, `models/domain/env_settings.py`
- [x] `utils/db/rls_context.py`, `utils/db/rls_admin_scope.py`, `utils/db/session_open.py`
- [x] `utils/auth/admin_scope.py` — `to_rls_session_vars()`
- [x] `routers/auth/dependencies.py`, `middleware.py`
- [x] `scripts/lint/lint_rls_session.py`

## K. PostgreSQL 18.3

- [x] `pg_dump --no-policies` in dump import + admin export
- [x] `docs/db-tuning.md`, `docs/db-rls-rollout.md`
- [x] `tests/db/test_rls_explain_hot_paths.py`

## C–E. Session wiring (application code)

- [x] AdminScope + `require_superadmin` panel RLS
- [x] Public org list, dashboard, MindBot callback/usage, workshop chat
- [x] Celery knowledge tasks, auth API key path
- [x] Direct sessions migrated to `user_rls_session` / `actor_rls_session` / `system_rls_session` (see lint)
- [x] HTTP requests: auth middleware sets default `RlsContext` context var

## Scripts (migrate role only — no app RLS)

- [ ] Operator confirms scripts under `scripts/db/` use `DATABASE_MIGRATION_URL` when run manually

## L. Staging smoke

- [ ] Manual — see [db-rls-rollout.md](db-rls-rollout.md) table
