# Maite Learning

Inquiry-based high-school math learning: reverse decomposition, four-stage diagnosis,
targeted remedy, variant practice, and session reports.

## API path map

| Path | Purpose |
|------|---------|
| `/api/maite/problems` | Create/list problems, OCR extract |
| `/api/maite/problems/bank` | Seeded problem bank |
| `/api/maite/sessions` | Create/list inquiry sessions |
| `/api/maite/sessions/{id}` | Get session, snapshot, redo, complete |
| `/api/maite/sessions/{id}/decompose` | Submit decompose tables |
| `/api/maite/sessions/{id}/mentor/decompose` | Mentor decompose (sync/stream) |
| `/api/maite/sessions/{id}/mentor/follow-up` | Mentor follow-up (sync/stream) |
| `/api/maite/sessions/{id}/diagnosis/auto` | Auto four-stage diagnosis |
| `/api/maite/sessions/{id}/diagnosis/finalize` | Finalize block report |
| `/api/maite/sessions/{id}/diagnosis/stage-4/variant` | Stage-4 variant |
| `/api/maite/sessions/{id}/diagnosis/stage-4/evaluate` | Stage-4 evaluate |
| `/api/maite/sessions/{id}/remedy` | Remedy overview, prepare, submit |
| `/api/maite/sessions/{id}/variants` | Generate/submit variant tasks |
| `/api/maite/sessions/{id}/report` | Session report |
| `/api/maite/graph` | Knowledge/thinking graph progress |
| `/api/maite/practice/recent` | Cached recent practice list |
