# Database tuning (PostgreSQL 18.3)

## Connection pools

See `config/database.py` and `env.example` for per-worker pool sizing vs `max_connections`.

## RLS hot paths

After enabling RLS, use `tests/db/test_rls_explain_hot_paths.py` (as `mindgraph_app`) to ensure indexed paths on `user_id` and `organization_id`.

Compare `pg_stat_statements` p95 before/after on:

- `/api/diagrams` list
- Admin token usage stats
- Knowledge document list

## PG 18 async I/O (optional post-rollout)

In `postgresql.conf` (staging first):

- `io_method = 'io_uring'` (or `'worker'` if io_uring unavailable)
- Tune `io_combine_limit` per workload

Restart required; document changes per environment.
