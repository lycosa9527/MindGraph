# MindGraph — Agent Instructions

## Project overview

MindGraph is an AI-powered diagram generation platform: Python 3.13 + FastAPI backend, Vue 3 + TypeScript frontend, PostgreSQL, Redis, and Qdrant.

Repository: https://github.com/lycosa9527/MindGraph

## Local development (WSL)

Developers on Windows use **WSL** with conda env `python313` or `mindgraph`. Do not use Windows-native Python shims.

```bash
conda activate python313   # or: conda activate mindgraph
cd /mnt/d/MindGraph
python -m pytest tests/some_test.py -q
python -m pylint path/to/module.py
python -m basedpyright .
```

**DingTalk QR bind:** `pyzbar` requires system `libzbar0` (`sudo apt-get install -y libzbar0` on Debian/Ubuntu). All bind ingress channels must use `services.auth.dingtalk_bind_service.claim_dingtalk_qr_bind`; one MindGraph user ↔ one DingTalk staff per org — see [`docs/architecture/dingtalk_account_binding.md`](docs/architecture/dingtalk_account_binding.md).

## Cursor Cloud specific instructions

Cloud agents run on **Ubuntu Linux** (not WSL). Python 3.13 and Node.js 26 are preinstalled via `.cursor/environment.json`.

### Environment

- Python: conda env `mindgraph` is on `PATH` (`python` / `pip`).
- Frontend: dependencies live in `frontend/` (`npm ci` runs on startup).
- Do **not** run `npm run build` unless the task explicitly requires a production build.
- Copy `env.example` to `.env` only when you need to run the full app; prefer Cursor **Secrets** for credentials (see below).

### Running tests

Most CI tests need only pip packages (no live Redis/PostgreSQL):

```bash
python -m pytest -q tests/test_user_daily_token_quota.py tests/test_llm_daily_token_cap.py \
 tests/test_collab_ws_json_limits.py tests/test_workshop_update_flush_gate.py \
  tests/test_workshop_ws_integration.py tests/test_online_collab_phase8.py \
  tests/test_workshop_collab_backend.py tests/test_collab_palette_sync.py \
  tests/test_workshop_editor_redis_merge.py tests/test_ws_fanout.py \
  tests/test_collab_synthetic_probe.py tests/test_workshop_join_resume_tokens.py \
  tests/test_organization_mindmate_avatar.py tests/test_org_subscription.py \
  tests/test_school_tier.py
```

Frontend checks (from `frontend/`):

```bash
npm run check:vueuse-pure
npm run check:dep0205
npm run check:scripts
npx vitest run tests/import-sidebar-quotes.spec.ts tests/useSidebarPhilosophyQuote.spec.ts tests/loadSidebarQuotePool.spec.ts
```

**Sidebar quotes** ship as committed assets (no network at build/dev):

- `frontend/src/assets/sidebar-quotes-zh.json`, `sidebar-quotes-en.json`
- `frontend/scripts/vendor/sidebar-quotes/` (wisdom-quotes snapshots + `extracted/echoes-*.json`)
- `npm run check:sidebar-quotes` verifies they exist (`prebuild` + CI `check:scripts`)
- Refresh wisdom-quotes: `npm run import:sidebar-quotes -- --refresh`
- Re-extract echoes (rare): `--refresh-echoes` then `--extract-echoes` (normal import uses frozen `extracted/` JSON only)
- Quote rotation (UI): new quote on login, full page refresh, UI locale change, and every 5 minutes while authenticated; same quote during SPA navigation within that window; timer uses `shownAt` in `sessionStorage` and pauses when the tab is hidden
- Lazy load (runtime): authenticated sidebar only; locale bucket (`zh` vs `en`) resolved via dynamic `import('…json?url')` + `fetch()` in `sidebarQuotePicker.ts` — JSON ships as static assets, not megabyte JS chunks; PWA workbox `globIgnores` excludes `sidebar-quotes-*` from precache

Import smoke:

```bash
python -c "from main import app; assert app.title"
```

### Linting

Match CI pylint scope when touching collab/auth paths, or run pylint on files you change:

```bash
python -m pylint path/to/changed_module.py
python scripts/lint/audit_pylint_four_rules.py
python -m basedpyright .
```

Follow PEP 8; fix all pylint findings without inline suppressions. Fix all basedpyright diagnostics; do not add project-wide `report* = "none"` suppressions in `pyproject.toml`.

Pylint policy: **full pylint** on the Python tree with minimal `[tool.pylint.messages_control].disable` entries (`duplicate-code`, `too-few-public-methods`, `arguments-renamed`, `too-many-positional-arguments`). Four hardening rules (`global-statement`, `protected-access`, `broad-except`, `import-outside-toplevel`) are enabled. No inline `# pylint: disable` / `# noqa` / `# type: ignore` — use structural fixes (holder singletons, cycle splits, narrow exception tuples from `services/utils/error_types.py`).

```bash
python scripts/lint/lint_no_inline_disables.py
python scripts/lint/audit_pylint_four_rules.py --fail
python -m pylint services routers agents clients config utils scripts tests loadtests tasks alembic/env.py --fail-under=10.0
python -m basedpyright .
```

### Full stack (optional)

Starting `python main.py` requires secrets and services configured in the Cursor Cloud dashboard:

| Variable | Purpose |
|----------|---------|
| `QWEN_API_KEY` | DashScope LLM |
| `REDIS_URL` | Sessions, collab, cache |
| `DATABASE_URL` | PostgreSQL |
| `QDRANT_HOST` | Knowledge Space RAG |
| `USER_DAILY_TOKEN_CAP` | Per-user daily LLM token limit (default `5000000`; `0` disables) |

Default port: **9527**. Alembic migrations run on startup.

For system services (Redis, PostgreSQL, Qdrant), use dashboard secrets pointing at reachable hosts, or scope tasks to unit tests that do not need live infrastructure.

### Code conventions

- Minimize diff scope; match existing patterns in surrounding files.
- Keep individual source files under ~600–800 lines when adding substantial code.
- Do not commit unless explicitly asked.
- Changelog: update `CHANGELOG.md` for user-visible changes when requested.
