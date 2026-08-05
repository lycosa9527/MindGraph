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

## Gallery limits (diagram case / template)

| Case type | Multi-item gallery | Max items |
|-----------|--------------------|-----------|
| `teaching_design` | No (single document + optional videos) | 1 attachment |
| `diagram_case` | Yes — images + saved diagrams | **15** (`gallery_0`…`gallery_14`) |
| `diagram_template` | Yes — same gallery publish/view path as case | **15** |

Frontend: `DIAGRAM_GALLERY_MAX_ITEMS`. Backend: `GALLERY_MAX_ITEMS` + upload role
`gallery_{slot}`. Spec JSON body allows up to `SHOWCASE_SPEC_MAX_BYTES` (2MB) so
multiple embedded diagram specs fit. Detail viewer carousels any `spec.gallery`
length > 1.

**Client gallery image prep (new picks only):** before COS PUT, the publish modal
runs an abortable async pick pipeline (`processShowcaseGalleryImagePick` →
`resizeImageFileForShowcaseGallery`) — long edge capped at **1600px**,
PNG/JPEG/WebP preserved (JPEG/WebP q=0.85), always canvas re-encoded to strip
EXIF/GPS (orientation applied via `imageOrientation: 'from-image'`). GIF is
left unchanged so animation is preserved. Soft-fail keeps the original file if
decode/encode fails. Processing is sequential with event-loop yields; closing
the modal or starting a new pick aborts in-flight work. Cover/thumbnail
pipeline is separate (960px PNG).

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
`design_highlights` with DashScope `qwen3.7-flash`
(K-12 teacher voice; ~200 字 × 2 ≈ 400 字; one paragraph each; names diagrams +
thinking types without heavy academic jargon). Teaching reflection stays teacher-authored.

| Route | Response |
|-------|----------|
| `POST /api/showcase/ai/teaching-copy` | Sync JSON (smoke / fallback) |
| `POST /api/showcase/ai/teaching-copy/stream` | SSE used by the publish modal |

Shared rate limit: `showcase_ai_teaching_copy` — 12 req / 60s per user.

## Diagram AI copy (step 2)

JSON body with `title` / `subject` / `grade` / `diagram_type` / `specs[]`
(personal library, `.mg`, canvas, or gallery diagram drafts). Server extracts
node labels (`native_spec_to_pseudo_nodes` + nodes walk), then drafts
`description` (图示简介) + `classroom_application` (课堂应用) with the same
model and teacher voice (~200 字 × 2).

| Route | Response |
|-------|----------|
| `POST /api/showcase/ai/diagram-copy` | Sync JSON (smoke / fallback) |
| `POST /api/showcase/ai/diagram-copy/stream` | SSE used by the publish modal |

Shared rate limit: `showcase_ai_diagram_copy` — 12 req / 60s per user.
Image-only gallery items (no diagram specs) cannot AI-fill.

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
No Gotenberg. Teachers upload the original `.pdf` / `.doc` / `.docx` / `.pptx`. Native PDF is
shown as-is; Office files are converted with high-quality LO export (`UseLosslessCompression`,
no image DPI downscale) to `preview.pdf`. The detail reader is **pdf.js only** (no browser
`docx-preview`) — pending until `preview_url` is ready, then full pages (images, shapes, layout).

| Step | Detail |
|------|--------|
| Trigger | `uploads/complete` with `role=attachment`, `case_type=teaching_design`, `.pdf/.doc/.docx/.pptx` |
| Download | `download_to_path` / `download_file` (stream to temp; never full `get_bytes`) |
| Render | PDF → PyMuPDF; Office → soffice (`writer_pdf_Export` / `impress_pdf_Export` + lossless filter) then PNG |
| Upload | `put_bytes` → `thumbnail.png`; Office also → `preview.pdf` + `spec.preview_path` |
| Reader | Detail pdf.js loads `/api/showcase/assets/…?proxy=1` (AuthZ + server bytes); HiDPI canvas, natural page width. Default asset GET stays 302→COS for ``<img>`` thumbs — credentialed `fetch` following that redirect fails browser CORS |
| Backfill | `GET /posts/{id}` + cover-stream re-enqueue when Office attachment lacks `preview_path` **and** cover job is not cold-`succeeded` |
| Manifesto | Postgres `case_square_cover_jobs` (one row/post): `queued`/`running`/`succeeded`/`failed` + attempts JSON. Admin lists read this cold — **no per-row COS HEAD**. Mark `succeeded` only after storage put + path commit. |
| Admin refresh | `POST /api/auth/admin/showcase/posts/{id}/refresh-cover` force-requeues even when `succeeded` (Published + moderation Refresh status button) |
| Celery retry | `showcase.generate_cover` total tries = `max_attempts` (3); exponential backoff; re-queues manifesto during backoff (not terminal `failed`); permanent reasons do not retry; stale in-flight (>270s) is reclaimable by admin Refresh |
| Events | Redis pub/sub → `GET …/posts/{id}/cover-stream` SSE (`cover_ready` / `cover_fail`); FE no poll. Redis fail TTL is live-only; admin uses manifesto. |
| Hard stop | LO 120s; Celery soft 180 / hard 210; SSE max 210s then `cover_fail` reason=timeout |
| Guard | Redis lock `showcase:cover:{post_id}`; abort if post gone or `attachment_key` stale; overwrite thumb when key matches; RLS write as `author_id` |
| Flag | `SHOWCASE_SERVER_COVERS` (default on when `COS_SHOWCASE_ENABLED`); Celery soft-starts for covers |
| Host | Startup hard-gate: LibreOffice Writer+Impress + `fonts-noto-cjk` when covers enabled (`host_deps.py`); failure messages include `apt-get install` + verify (`soffice --version`, Writer/Impress binaries, `fc-list`); `LIBREOFFICE_PATH` / `resolve_soffice_path` |
| CJK fonts | Optional private COS pack (`sync/fonts/office-preview/`: 宋体/楷体/仿宋/黑体/微软雅黑). Publish once from Windows Fonts: `python scripts/db/publish_office_preview_fonts_to_cos.py`. Cover jobs auto-pull into `data/office_preview_fonts/` (or `--pull` to warm). Noto remains fallback. Do not commit font binaries. |

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
