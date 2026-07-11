# AdminScope and PostgreSQL RLS

This document describes how the management panel **AdminScope** maps to Postgres row-level security (RLS) session variables, which routes use which filters, and how to verify behavior.

See also [`alembic/README.md`](../alembic/README.md) for migration roles and operator commands.

## 1. Role × route matrix

| Role | Global tabs (users, orgs, stats, billing) | Invite tab | School dashboard |
|------|---------------------------------------------|------------|------------------|
| **superadmin** | Full read/write; RLS `panel_global_read=1` | Full | Full |
| **platform_bd** | Read-only global; RLS `panel_global_read=1` | Invited orgs + legacy NULL `invited_by_user_id` | Read (data center) |
| **expert** | Organizations tab: invited orgs only (no legacy); other global tabs Denied (403) | Invited orgs only (no legacy) | Denied |
| **school_admin** | Denied (403) | Denied | Own org only; RLS `readable_org_ids=<org>` |

**Filter helpers (application layer):**

| Helper | Used on | Effect |
|--------|---------|--------|
| `true()` / no filter | Superadmin global lists | All rows (RLS still applies) |
| `panel_org_table_filter` | `GET /admin/organizations` | Global cap → all orgs; expert → invited-only |
| `invite_org_filter` | `GET /admin/invites/organizations` | BD: invited + legacy; expert: invited only |
| `org_filter` | Token stats with org scope | Org ID subquery for invited-org roles |
| IDOR guards | Detail/mutation routes | `assert_panel_org_readable`, `assert_resource_org_in_scope` |

## 2. GUC mapping (AdminScope → `app.*`)

Built by [`admin_scope_to_session_vars()`](../utils/db/rls_admin_scope.py) and applied via [`RlsContext`](../utils/db/rls_context.py).

| AdminScope condition | `app.rls_mode` | Key GUCs | SQL consumers |
|---------------------|----------------|----------|---------------|
| Superadmin | `panel` | `panel_global_read=1`, `user_id`, `role` | `rls_panel_global_read()`, `rls_org_visible()` |
| `scope.global` (platform_bd) | `panel` | `panel_global_read=1` | Global admin reads short-circuit to true |
| `scope.org` (school_admin) | `panel` | `readable_org_ids`, `organization_id` | `rls_org_id_in_readable_list()`, `rls_user_visible()` |
| Expert / invited-only | `panel` | `readable_org_ids`, `role=expert` | Legacy orgs blocked in `rls_panel_legacy_org_visible()` |
| `require_admin` routes | `panel_superadmin` | `panel_global_read=1` | Same effective access as global panel |
| Normal API user | `authenticated` | `user_id`, `organization_id` | Same-org and owner checks |
| Anonymous | `deny` | `rls_mode=deny` | Deny all |

**Order note:** `CAP_SCOPE_GLOBAL` is evaluated before invited-org mapping so platform_bd gets `panel_global_read`, not only `readable_org_ids`.

## 3. Platform BD dual scope

- **Global tabs:** `scope.global` → RLS `panel_global_read=1`; application lists do not restrict by invited orgs.
- **Invite tab:** `invite_org_filter` uses `panel_readable_org_condition` (invited orgs + legacy NULL for BD, invited-only for expert).

## 4. Session lifecycle

1. **Auth middleware** sets context var to authenticated user or deny-default.
2. **Route dependencies** override `request.state.rls_context`:
   - `get_admin_scope` → panel context from AdminScope + `set_rls_context(ctx)`
   - `require_superadmin` → `bind_panel_superadmin_rls` + `set_rls_context(ctx)`
3. **`get_async_db`** reads `request.state.rls_context`, sets context var, and pins the same `RlsContext` on `session.info["rls_context"]`.
4. **`after_begin`** on each transaction runs `set_config` for all GUCs (transaction-local), preferring `session.info` over the ContextVar (survives BaseHTTPMiddleware / nested `rls_*_session` ContextVar resets).
5. **After `commit`:** new transaction re-applies GUCs from `session.info` (and ContextVar when still set) — must stay in panel mode for admin mutations.
6. **Expert org create** also needs Alembic **`0072`** (`rls_panel_org_invited_by_actor`) so `INSERT` WITH CHECK passes when `invited_by_user_id = app.user_id`.

## 5. User-owned table policies (rev 0051+)

`rls_diagram_visible(owner_user_id)`:

- Owner always visible; `panel_global_read` → all rows.
- Panel mode without global read → org-scoped via `rls_lookup_user_organization_id` (rev 0052, `SECURITY DEFINER`).
- Authenticated → same-org via `rls_same_org_users`.

Legacy org checks use `rls_lookup_org_invited_by_user_id` (rev 0053) to avoid `organizations` policy recursion.

Applies to diagrams, knowledge spaces, and child policies referencing `rls_diagram_visible`.

## 6. Verification checklist

**Unit tests (no DB):**

```bash
pytest tests/auth/test_admin_scope.py tests/auth/test_expert_invite_scope.py -q
```

**Integration tests (Postgres + `mindgraph_app`, migrations through 0053):**

```bash
set RUN_RLS_DB_TESTS=1
pytest tests/db/test_rls_panel_orgs.py tests/db/test_rls_panel_diagram_scope.py tests/auth/test_rls_context_post_commit.py -q
pytest tests/db/test_rls_explain_hot_paths.py -q
```

**Manual smoke:**

- Log in as **platform_bd** → data center user/org counts match superadmin (read-only).
- Log in as **expert** → **组织管理** lists only created orgs; create school works; global stats 403.
- **Expert creates org** → refresh succeeds after commit (panel GUC persists).

## 7. Performance

| Cost | When | Notes |
|------|------|-------|
| AdminScope build | Panel requests | Negligible (in-memory) |
| `load_expert_invited_org_ids` | Expert/BD panel deps | +1 indexed query (`ix_organizations_invited_by_user_id`) |
| `set_config` per GUC | Each transaction | ~4–8 round-trips; largest avoidable overhead |
| RLS predicates | All protected queries | Mitigated by rev 0048 indexes |
| 0051 diagram scope | Scoped panel on user-owned tables | Org lookup via SECURITY DEFINER; global panel unchanged |

## 8. Optimization backlog (deferred)

| ID | Item | Status |
|----|------|--------|
| Q1 | Panel RLS before `get_async_db` (remove double apply) | Deferred |
| Q2 | Batch GUC setup (`rls_apply_context`) | Deferred |
| Q3 | Lazy invited-org load on global admin deps | Deferred |
| M1 | Unify `panel` / `panel_superadmin` modes | Deferred |
| M2 | Explicit `invite_tab_filter` vs `global_panel_filter` | Partially addressed in `invite_org_filter` |
| M3 | Trim redundant app filters post-0051 | Deferred |
| M4 | `readable_org_ids` as `int[]` GUC | Deferred |
| L1 | Redis cache for invited org IDs | Deferred |

Implement Phase D items only when measured latency warrants it.
