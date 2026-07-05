# MindGraph — Agent Instructions

## Project overview

MindGraph is an AI-powered diagram generation platform: Python 3.13 + FastAPI backend, Vue 3 + TypeScript frontend, PostgreSQL, Redis, and Qdrant.

Repository: https://github.com/lycosa9527/MindGraph

## Cursor rules (canonical pointers)

| Topic | Source |
|-------|--------|
| WSL, conda, paths, no `npm run build` | [`.cursor/rules/wsl-conda-dev.mdc`](.cursor/rules/wsl-conda-dev.mdc) |
| CI before commit/push | [`.cursor/rules/ci-before-commit-push.mdc`](.cursor/rules/ci-before-commit-push.mdc) → [`scripts/ci-local.sh`](scripts/ci-local.sh) |
| File-reader Windows exe rebuild | [`.cursor/rules/file-reader-rebuild.mdc`](.cursor/rules/file-reader-rebuild.mdc) (glob: `clients/file-reader/**`) |

**DingTalk bind:** MindBot pair-code ingress (`services/mindbot/tools/`); bind/unbind via rotating codes — see [`docs/architecture/dingtalk_account_binding.md`](docs/architecture/dingtalk_account_binding.md) and [`docs/architecture/mindbot_tool_ingress.md`](docs/architecture/mindbot_tool_ingress.md).

**Production security deploy:** env/proxy checklist, paired rollout, ESP32 headers — see [`docs/architecture/production_security_deploy.md`](docs/architecture/production_security_deploy.md).

## Quality gates

### Before commit or push (required)

Run full GitHub CI locally; do not commit or push until it passes:

```bash
cd /mnt/d/MindGraph
./scripts/ci-local.sh
```

Details: [`.cursor/rules/ci-before-commit-push.mdc`](.cursor/rules/ci-before-commit-push.mdc). After push: `gh run watch`.

During development, scoped runs are OK when the diff is clearly one side: `--backend-only` / `--frontend-only`. Do not substitute ad-hoc partial checks when preparing commit/push.

### Lint and type-check policy

Follow PEP 8. Fix **all** pylint and basedpyright findings — no inline suppressions.

- **Pylint:** full Python tree with minimal `[tool.pylint.messages_control].disable` (`duplicate-code`, `too-few-public-methods`, `arguments-renamed`, `too-many-positional-arguments`).
- **Four hardening rules** (always on): `global-statement`, `protected-access`, `broad-except`, `import-outside-toplevel`.
- **Never** use `# pylint: disable`, `# noqa`, or `# type: ignore` — use structural fixes (holder singletons, cycle splits, narrow exception tuples from `services/utils/error_types.py`).
- Do not add project-wide `report* = "none"` suppressions in `pyproject.toml`.

Exact commands mirror [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and are executed by [`scripts/ci-local.sh`](scripts/ci-local.sh).

## Cursor Cloud

Cloud agents run on **Ubuntu Linux** (not WSL). Python 3.13 and Node.js 26 are preinstalled via [`.cursor/environment.json`](.cursor/environment.json).

- Python: conda env `mindgraph` on `PATH`.
- Frontend: `frontend/` (`npm ci` on startup).
- Copy `env.example` to `.env` only when running the full app; prefer Cursor **Secrets** for credentials.

### Full stack (optional)

| Variable | Purpose |
|----------|---------|
| `QWEN_API_KEY` | DashScope LLM |
| `REDIS_URL` | Sessions, collab, cache |
| `DATABASE_URL` | PostgreSQL |
| `QDRANT_HOST` | Knowledge Space RAG |
| `USER_DAILY_TOKEN_CAP` | Per-user daily LLM token limit (default `5000000`; `0` disables) |

Default port: **9527**. Alembic migrations run on startup. For Redis/PostgreSQL/Qdrant, use dashboard secrets or scope work to unit tests that need no live infrastructure.

## Domain notes

### Sidebar quotes

Ship as committed assets (no network at build/dev):

- `frontend/src/assets/sidebar-quotes-zh.json`, `sidebar-quotes-en.json`
- `frontend/scripts/vendor/sidebar-quotes/` (wisdom-quotes snapshots + `extracted/echoes-*.json`)
- `npm run check:sidebar-quotes` verifies they exist (`prebuild` + CI `check:scripts`)
- Refresh wisdom-quotes: `npm run import:sidebar-quotes -- --refresh`
- Re-extract echoes (rare): `--refresh-echoes` then `--extract-echoes` (normal import uses frozen `extracted/` JSON only)
- Quote rotation (UI): new quote on login, full page refresh, UI locale change, and every 5 minutes while authenticated; same quote during SPA navigation within that window; timer uses `shownAt` in `sessionStorage` and pauses when the tab is hidden
- Lazy load (runtime): authenticated sidebar only; locale bucket (`zh` vs `en`) resolved via dynamic `import('…json?url')` + `fetch()` in `sidebarQuotePicker.ts` — JSON ships as static assets, not megabyte JS chunks; PWA workbox `globIgnores` excludes `sidebar-quotes-*` from precache

Extra frontend vitest (not in default CI job): `tests/import-sidebar-quotes.spec.ts`, `tests/useSidebarPhilosophyQuote.spec.ts`, `tests/loadSidebarQuotePool.spec.ts`.

## Code conventions

- Minimize diff scope; match existing patterns in surrounding files.
- Complete a root-cause review before applying fixes.
- Keep individual source files under ~600–800 lines when adding substantial code.
- Do not commit or push unless explicitly asked.
- Changelog: update `CHANGELOG.md` for user-visible changes when requested.
