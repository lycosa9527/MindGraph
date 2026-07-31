# Mate Learning

Inquiry-based high-school math learning: reverse decomposition, four-stage diagnosis,
targeted remedy, variant practice, and session reports.

Feature flag: `FEATURE_MATE_LEARNING` (default **off**).

## API path map

| Path | Purpose |
|------|---------|
| `GET /api/maite/health` | Authenticated health probe |
| `POST /api/maite/problems` | Create problem |
| `POST /api/maite/problems/ocr` | OCR extract (rate-limited, ≤8MB) |
| `GET /api/maite/problem-bank` | Seeded problem bank |
| `GET /api/maite/downloads/images/{file}` | Auth-scoped private upload download |
| `POST /api/maite/mentor/decompose` (+ `/stream`) | Demo mentor decompose |
| `POST /api/maite/mentor/follow-up` (+ `/stream`) | Demo mentor follow-up |
| `POST /api/maite/inquiry/sessions` | Create inquiry session |
| `GET /api/maite/inquiry/sessions` | List sessions (Redis-cached) |
| `GET /api/maite/practice/recent` | Alias for recent practice list |
| `GET /api/maite/inquiry/sessions/{id}` | Get session |
| `GET /api/maite/inquiry/sessions/{id}/snapshot` | Aggregated snapshot (no answer keys) |
| `POST /api/maite/inquiry/sessions/{id}/decompose` | Submit three tables |
| `POST /api/maite/inquiry/sessions/{id}/redo` | New version same problem |
| `POST /api/maite/inquiry/sessions/{id}/complete` | Complete (≥3 submitted variants) |
| `POST /api/maite/inquiry/{id}/diagnose/*` | Diagnosis stages (LLM rate-limited) |
| `POST /api/maite/inquiry/{id}/remedy/*` | Remedy prepare/submit |
| `POST /api/maite/inquiry/{id}/variants` | Generate / submit variants |
| `GET /api/maite/reports/{id}` | Build or fetch report |
| `GET /api/maite/graph` | Knowledge/thinking graph progress |

## Production notes

- All business routes require auth; `user_id` always from JWT/session.
- Completed sessions return **409** on mutating stage endpoints.
- `expected_strategy` / `reference_*` are stripped from client payloads.
- Child tables + `maite_task_references` use RLS (Alembic `0090`/`0091`).
- Session event bus auto-starts on emit and stops on session complete.
