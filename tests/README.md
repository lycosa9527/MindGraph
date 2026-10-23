# Tests

Pytest collects `tests/`. Vitest collects `frontend/tests/`. Both trees stay flat on purpose: a new test sits next to the suite it extends.

## Layout

| Path | Role |
|------|------|
| `tests/test_*.py` | Backend unit tests (most files) |
| `tests/auth/` | Auth, admin, and school HTTP |
| `tests/db/` | RLS and database policy |
| `tests/services/` | Service-level tests (COS sync and similar) |
| `tests/routers/` | Router tests that are not under `auth/` |
| `tests/utils/` | Small helper tests |
| `tests/scripts/` | Script tests |
| `tests/smoke/` | Smoke checks |
| `tests/fixtures/` | Shared JSON fixtures |
| `frontend/tests/*.spec.ts` | Vue and TypeScript specs |

`tests/conftest.py` sets a local `DATABASE_URL` default and installs the Redis 8 feature stub before models import. Markers include `integration` for tests that need a live LLM or Redis.

## Run

From the repo root, with conda env `python313` or `mindgraph`:

```bash
python -m pytest tests -q
cd frontend && npm test
```

Full CI (backend and frontend) is `./scripts/ci-local.sh`. Scoped runs: `--backend-only` and `--frontend-only`.
