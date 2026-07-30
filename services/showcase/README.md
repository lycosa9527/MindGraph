# Showcase — case gallery media + moderation

One backend package (Kitty-style domain + infra). Routers stay thin under
`routers/features/showcase_*.py` and `routers/auth/admin/showcase.py`.

## Layout

| Path | Role |
|------|------|
| `services/showcase/storage/` | COS/local I/O, keys, presign, asset delete |
| `services/showcase/uploads/` | Roles, Redis grants, init/complete helpers |
| `services/showcase/covers/` | Server teaching-design covers (LO + PyMuPDF + Celery) |
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
5. Teaching-design attachment → Celery cover job (soft-fail; HTTP always 200)
6. `GET /api/showcase/assets/…` — AuthZ then 302 short GET (or local FileResponse)

Withdraw (pending) **hard-deletes** rows + `delete_post_assets`. Delist (approved)
keeps storage; status becomes `withdrawn`.

## Teaching-design AI copy (step 2)

Multipart document (`.pdf`/`.doc`/`.docx`/`.pptx`) plus title/subject/grade.
Server extracts text (`DocumentProcessor`), then drafts `description` /
`design_highlights` / `teaching_reflection` with DashScope `qwen3.7-flash`
(K-12 teacher voice; ~200 字 × 3 ≈ 600 字; one paragraph each; names diagrams +
thinking types without heavy academic jargon).

| Route | Response |
|-------|----------|
| `POST /api/showcase/ai/teaching-copy` | Sync JSON (smoke / fallback) |
| `POST /api/showcase/ai/teaching-copy/stream` | SSE used by the publish modal |

Shared rate limit: `showcase_ai_teaching_copy` — 12 req / 60s per user.

**SSE events** (`text/event-stream`, `data:` JSON lines):

| `event` | Payload |
|---------|---------|
| `phase` | `phase`: `extracting` \| `generating` |
| `fields` | Partial `description` / `design_highlights` / `teaching_reflection` (keys appear as the model streams JSON) |
| `done` | Final normalized fields + `model` |
| `error` | `message`, optional `error_type` |

Publish modal auto-starts the **stream** on step-1→2 so textareas fill live
(with toasts). Button while in-flight **stops** generation (keeps partial text);
idle click clears the three fields and regenerates. Validation/extract run
before the stream opens; client disconnect cancels the LLM stream.

## Server-side teaching-design covers

Package: `services/showcase/covers/` (LibreOffice → PDF on temp disk + PyMuPDF page-1 PNG).
No Gotenberg; intermediate PDF never lands on COS.

| Step | Detail |
|------|--------|
| Trigger | `uploads/complete` with `role=attachment`, `case_type=teaching_design`, `.pdf/.doc/.docx` |
| Download | `download_to_path` / `download_file` (stream to temp; never full `get_bytes`) |
| Render | PDF → PyMuPDF; Office → soffice with per-job `-env:UserInstallation` then PNG |
| Upload | `put_bytes` → logical `showcase/posts/{id}/thumbnail.png` (`ContentType=image/png`) |
| Events | Redis pub/sub → `GET …/posts/{id}/cover-stream` SSE (`cover_ready` / `cover_fail`); FE no poll |
| Hard stop | LO 120s; Celery soft 180 / hard 210; SSE max 210s then `cover_fail` reason=timeout |
| Guard | Redis lock `showcase:cover:{post_id}`; abort if post gone or `attachment_key` stale; overwrite thumb when key matches; RLS write as `author_id` |
| Flag | `SHOWCASE_SERVER_COVERS` (default on when `COS_SHOWCASE_ENABLED`); Celery soft-starts for covers |
| Host | Startup hard-gate: LibreOffice Writer+Impress + `fonts-noto-cjk` when covers enabled (`host_deps.py`); failure messages include `apt-get install` + verify (`soffice --version`, Writer/Impress binaries, `fc-list`); `LIBREOFFICE_PATH` / `resolve_soffice_path` |

Logical keys in PG stay under `showcase/posts/{uuid}/…`; COS uses `full_cos_key` + `COS_SHOWCASE_PREFIX`.

## Workflow logging

- Logger `showcase.workflow`: `SHOWCASE_WF stage=… | post=… | uid=… | detail=…`
- Disable: `SHOWCASE_WORKFLOW_TRACE=0`
- Structured extras: `showcase_extra(event, post_id=, user_id=, role=, key=, backend=)`

Stages: `create`, `create_rollback`, `upload_init`, `upload_complete`, `download`,
`download_deny`, `withdraw`, `delete`, `assets_deleted`, `cache_invalidate`,
`sync_scan`, `sync_purge`, `cover_enqueue`, `cover_enqueue_fail`, `cover_start`,
`cover_ok`, `cover_skip`, `cover_fail`.

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
  tests/test_showcase_e2e_smoke.py tests/test_showcase_server_covers.py -q

# Real Desktop DOCX fixtures (skip if missing / no soffice):
# SHOWCASE_REAL_DOCX / SHOWCASE_REAL_DOCX_2 or default Desktop paths
python -m pytest tests/test_showcase_server_covers.py -q

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
