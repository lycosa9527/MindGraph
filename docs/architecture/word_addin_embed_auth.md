# Word add-in embed auth

MindGraph for Word (`word-addin/`) opens the live SPA in an Office.js task pane. Session cookies must be set on the **SPA origin**, not on `https://localhost` where the add-in shell runs.

## Flow

1. Settings stores phone + `mgat_` (OfficeRuntime.storage / localStorage).
2. MindGraph host page `POST /api/auth/embed/handoff` with `Authorization: Bearer mgat_…`, `X-MG-Account`, `X-MG-Client: word-addin`.
3. API stores a one-time Redis code (~60s) and returns `{ "handoff": "…" }`.
4. Host navigates to `GET /api/auth/embed/complete?handoff=…&next=/mindgraph`.
5. API consumes the code, issues JWT access + refresh via the same path as login (`set_auth_cookies`), redirects to `/mindgraph?embed=word-addin`.
6. SPA treats `embed=word-addin` (and Office host) as **desktop** — never `/m/*`.

Handoff codes are opaque and short-lived; do not put `mgat_` in the SPA query string. `next` must be a same-site path under an allowlist (`/mindgraph`, `/mindmate`, `/canvas`, `/showcase`).
