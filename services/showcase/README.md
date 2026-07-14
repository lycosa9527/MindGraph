# Showcase — case gallery media + moderation

One backend package (Kitty-style domain + infra). Routers stay thin under
`routers/features/showcase_*.py` and `routers/auth/admin/showcase.py`.

## Layout

| Path | Role |
|------|------|
| `services/showcase/storage/` | COS/local I/O, keys, presign, asset delete |
| `services/showcase/uploads/` | Roles, Redis grants, init/complete helpers |
| `services/showcase/posts/` | Create rollback + lifecycle workflow logs |
| `services/showcase/sync/` | COS ↔ DB inventory, reconcile, orphan purge |
| `services/showcase/infra/` | `showcase_extra` + `showcase_wf_log` |
| `services/showcase/audit.py` | Audit log writes |
| `services/showcase/staff_permissions.py` | Permission matrix |
| `services/showcase/field_options.py` | Subject/grade/tag meta |
| `routers/features/showcase_*.py` | Public `/api/showcase/*` |
| `routers/auth/admin/showcase.py` | Admin stats, grants, fields, **storage** |

Compatibility shims: `services.showcase.upload_roles` re-exports `uploads.roles`.

## Publish contract (COS on)

1. `POST /api/showcase/posts` — metadata only (multipart files rejected when COS on)
2. `POST …/uploads/init` — Redis grant + short-TTL presigned PUT
3. Browser `PUT` to COS
4. `POST …/uploads/complete` — head + magic bytes + bind key in PG
5. `GET /api/showcase/assets/…` — AuthZ then 302 short GET (or local FileResponse)

Withdraw (pending) **hard-deletes** rows + `delete_post_assets`. Delist (approved)
keeps storage; status becomes `withdrawn`.

## Workflow logging

- Logger `showcase.workflow`: `SHOWCASE_WF stage=… | post=… | uid=… | detail=…`
- Disable: `SHOWCASE_WORKFLOW_TRACE=0`
- Structured extras: `showcase_extra(event, post_id=, user_id=, role=, key=, backend=)`

Stages: `create`, `create_rollback`, `upload_init`, `upload_complete`, `download`,
`download_deny`, `withdraw`, `delete`, `assets_deleted`, `cache_invalidate`,
`sync_scan`, `sync_purge`.

## COS management (sync)

Postgres keys are source of truth. Reconcile diffs bucket objects under
`{COS_SHOWCASE_PREFIX}/showcase/posts/`.

| Class | Meaning |
|-------|---------|
| `matched` | In DB and COS |
| `orphan_cos` | In COS, not referenced (abandoned PUT) |
| `missing_in_cos` | DB key with no object |
| `unscoped` | Under prefix but not `showcase/posts/{id}/role.ext` |
| `legacy_local` | `case_square/…` keys (report only) |

Admin API:

- `GET /api/auth/admin/showcase/storage/status`
- `GET /api/auth/admin/showcase/storage/reconcile`
- `POST /api/auth/admin/showcase/storage/purge-orphans` `{ "dry_run": true }`  
  (apply purge requires `showcase.delete`; default dry_run)

CLI:

```bash
PYTHONPATH=. python scripts/showcase_cos_reconcile.py
PYTHONPATH=. python scripts/showcase_cos_reconcile.py --purge --i-know-what-im-doing
```

## Tests / smoke

```bash
python -m pytest tests/test_showcase_storage_cos.py tests/test_showcase_helpers.py \
  tests/test_showcase_e2e_smoke.py -q

# Live COS (TENCENT_SMS_SECRET_* + COS_BUCKET + COS_SHOWCASE_ENABLED):
COS_SHOWCASE_SMOKE=1 python -m pytest tests/test_showcase_e2e_smoke.py \
  tests/test_showcase_cos_live_matrix.py -q
```

Smoke / matrix use isolated prefixes (`showcase/mindgraph-e2e-smoke`,
`showcase/mindgraph-e2e-matrix`) and a phone-keyed teacher (`19900000661`) so
live objects stay out of shared prod/test prefixes. Prefer distinct
`COS_SHOWCASE_PREFIX` per environment (`showcase/mindgraph` vs
`showcase/mindgraph-Test`).

## Test ↔ prod MG id mismatch

Same phone can have different `users.id` on test vs production (teachers who
registered on test only). PG merge remaps Showcase FKs via phone:

- `case_square_posts`: `author_id`, `submitted_by_id`, `reviewed_by`, `expert_recommended_by`
- likes / favorites / staff grants / audit: `user_id` / `actor_id`

COS object keys are `…/showcase/posts/{post_uuid}/…` (not MG id), so media
survives id remap; keep env prefixes separate so reconcile/purge stay scoped.
