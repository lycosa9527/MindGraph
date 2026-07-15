<p align="center">
  <img src="docs/assets/readme-hero.jpg" alt="MindGraph — cute black cat learning with diagrams" width="100%">
</p>

<h1 align="center">MindGraph</h1>

<p align="center">
  <strong>Diagrams for cat lovers who love to learn</strong><br>
  Turn a thought into Thinking Maps, Mind Maps, and Concept Maps — with a little help from AI.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.13+-blue.svg" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI"></a>
  <a href="https://vuejs.org/"><img src="https://img.shields.io/badge/Vue-3.5+-42b883.svg" alt="Vue"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-5.147.0-brightgreen.svg" alt="Version"></a>
</p>

---

Welcome in. **MindGraph** is an AI-powered diagram studio for classrooms and curious minds: describe an idea in plain language, watch it become a structured map, then play with it on an interactive canvas — alone or with classmates.

Built for teachers, learners, and anyone who thinks better with pictures (especially if a black cat on the desk helps).

<p align="center">
  <img src="docs/assets/readme-diagrams.jpg" alt="Cute black cat guides Circle, Bubble, Tree, and Concept Maps" width="72%">
</p>

<p align="center"><em>Meet the maps: Circle, Bubble, Tree, and Concept — same learning tools teachers know, wrapped in a friendlier face.</em></p>

<p align="center">
  <img src="docs/assets/readme-canvas.jpg" alt="Black cat teacher introducing MindGraph mind map in class" width="88%">
</p>

<p align="center"><em>From “Ideas” to Stories, Questions, and Feelings — MindGraph turns brainstorming into a shareable, editable canvas.</em></p>

> README art generated with DashScope **qwen-image-2.0** (cute black-cat education theme). Regenerate via `scripts/generate_readme_images.py`.

---

## Features

**Diagram Types**

- **Thinking Maps** (8 types): Circle, Bubble, Double Bubble, Tree, Brace, Flow, Multi-Flow, Bridge
- **Tree Map**: Center-aligned vertical group layout with DOM-measured adaptive column widths
- **Mind Map**: Radial brainstorming with DOM-measured branch layout, drag-to-reparent, five diagram styles (classic, formal, bubble, underline, soft), curated color themes, and post-add inline edit
- **Concept Map**: Relationship mapping with AI-generated labels, focus questions, and root concept suggestions

**AI Capabilities**

- Natural language to diagram generation
- Node Palette: AI-suggested nodes with streaming
- Inline AI Recommendations: double-click any node for context-aware auto-completion (all diagram types)
- Concept Map focus question validation and SSE suggestion streams
- Multi-LLM support: Qwen, DeepSeek, Kimi, Doubao (Volcengine)
- Output in 149+ languages (ISO/BCP-47, filterable prompt-language picker)
- **Thinking coins** (思维币): optional trial-school wallet for LLM usage metering — see [docs/architecture/thinking_coins.md](docs/architecture/thinking_coins.md)

**MindMate & MindBot**

- **MindMate**: Dify-backed AI chat with SSE streaming, diagram preview cache, and canvas navigation handoff
- **MindBot**: DingTalk HTTP robot → Dify per-organization config; pair-code account binding; unified conversation history with web MindMate
- **Document Summary** (文档总结): canvas panel that ingests documents, images, web URLs, and chat transcripts into a session package and generates RAG-backed mind maps
- **Chat handoff**: pairing codes on the 聊天记录 tab; Windows desktop helper at [clients/file-reader/](clients/file-reader/) for WeChat/DingTalk export ingest

**Canvas Editor**

- Interactive canvas with export (PNG, SVG, PDF, JSON)
- KaTeX math rendering in diagram labels (mhchem for chemistry notation)
- Branch drag-and-drop (long-press to reparent or swap nodes)
- Presentation mode with pointer, hand, laser, spotlight, highlighter, pen, and countdown timer
- Learning sheet float bar: custom pick and random blank sessions
- Auto-save with dirty/saving indicators and relative timestamps
- Diagram snapshots: up to 10 point-in-time versions per diagram with click-to-recall
- Canvas history baseline: first edit is undoable; session reset clears ephemeral state
- Text alignment and rich text-style toolbar
- Mind map v2 canvas (optional, `FEATURE_MINDMAP_V2_CANVAS=True`): side-toolbar chrome, orthogonal edges, Document Summary panel
- Mobile web shell (`/m/*`) with touch pinch-zoom and pane pan

**Collaboration & Platform**

- Online canvas collaboration (WebSocket, Redis live-spec merge)
- Workshop Chat (教研坊): school-scoped real-time channels, topics, DMs, reactions, and file attachments
- International landing page with Chinese / International UI version toggle
- Knowledge Space (RAG) for document management and retrieval
- Library with image-based document viewing
- DebateVerse, AskOnce, and Showcase AI features
- Teacher usage tracking

**Internationalization**

- Full UI in 77 bundled locales (tier-1: zh, en; tier-2: 75+ locales including RTL Dhivehi)
- Interface language picker with parity-checked bundles
- Prompt output language independent of UI language

**Security & Auth**

- Optional **AbuseIPDB** and **Fail2ban** integration — see [docs/FAIL2BAN_SETUP.md](docs/FAIL2BAN_SETUP.md)
- JWT and API key authentication with Redis cache-aside (5-minute TTL, SHA-256 fingerprinting)
- **OAuth QR login** (WeChat + DingTalk, `FEATURE_OAUTH_LOGIN=False` by default) — see [docs/architecture/oauth_qr_login.md](docs/architecture/oauth_qr_login.md)
- **DingTalk pair-code binding** — rotating 6-digit codes via MindBot; see [docs/architecture/dingtalk_account_binding.md](docs/architecture/dingtalk_account_binding.md)
- CSRF double-submit protection; CSP script nonce on SPA shell (no `'unsafe-inline'` for scripts)
- Captcha on password change; sessions revoked on password update
- Per-feature organization/user access rules (DB-backed, Redis-cached)
- Production startup guards: `DATABASE_URL` required; optional `REQUIRE_REDIS_AUTH`, `ALLOWED_HOSTS`, `COLLAB_FANOUT_ORIGIN_SECRET`
- OpenAPI schema served only when `DEBUG=True`
- Health endpoints require JWT; SSE errors do not expose stack traces

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Vue 3.5, TypeScript, Vite 7, Tailwind CSS 4, Pinia, Vue Flow, KaTeX |
| **Backend** | Python 3.13, FastAPI, Uvicorn, Alembic |
| **Data** | PostgreSQL (JSONB), Redis 8+, Qdrant |
| **AI** | LangGraph, Dashscope (Qwen), Volcengine (Doubao, DeepSeek, Kimi), Dify |

---

## Quick Start

### Prerequisites

- Miniconda (Python 3.13+ env named `mindgraph`)
- Node.js and npm (latest; see [docs/NODE_NVM_SETUP.md](docs/NODE_NVM_SETUP.md))
- Redis 7.0+ (8.6+ recommended for key-memory histograms and VSET)
- Qdrant (for Knowledge Space)
- PostgreSQL

### Installation

```bash
git clone https://github.com/lycosa9527/MindGraph.git
cd MindGraph

conda create -n mindgraph python=3.13 -y
conda activate mindgraph
pip install -r requirements.txt
python -m playwright install chromium

# Linux system packages: Redis, PostgreSQL, Qdrant, Playwright deps, Tesseract OCR
sudo -E env PATH="$PATH" "$(which python)" scripts/setup/setup.py

# Optional: install dashboard assets (ECharts, China GeoJSON, ip2region)
python scripts/setup/dashboard_install.py

# Frontend
cd frontend && npm install && npm run build && cd ..

# Configuration
cp env.example .env
# Edit .env: set QWEN_API_KEY, REDIS_URL, QDRANT_HOST, DATABASE_URL
```

### Run

```bash
conda activate mindgraph
python main.py
```

Database schema migrations (Alembic) and PostgreSQL RLS role bootstrap run automatically on startup.

Default: `http://localhost:9527`

### Key Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects based on UI version |
| `/mindmate` | AI chat and landing (Chinese version) |
| `/mindgraph` | Diagram gallery |
| `/canvas` | Interactive diagram editor |
| `/canvas?openDocSummary=1` | Canvas with Document Summary panel open |
| `/knowledge-space` | RAG document management |
| `/library` | Document library |
| `/workshop-chat` | Workshop Chat — real-time teacher collaboration |
| `/admin` | Admin panel (API keys, users, features, database) |
| `/docs` | API docs (when `DEBUG=True`) |
| `/m/*` | Mobile web shell |

---

## Configuration

Required environment variables:

```bash
QWEN_API_KEY=your-api-key
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost:6333   # For Knowledge Space
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/mindgraph
PORT=9527
DEBUG=False
AUTH_MODE=jwt   # or: enterprise (disables JWT validation, isolated networks only)
```

Notable feature flags (see `env.example` for full list):

| Flag | Default | Description |
|------|---------|-------------|
| `FEATURE_MINDBOT` | `True` | DingTalk MindBot → Dify |
| `FEATURE_MINDMATE` | `False` | MindMate AI chat |
| `FEATURE_KNOWLEDGE_SPACE` | `False` | RAG / Document Summary (requires Qdrant + Celery) |
| `FEATURE_OAUTH_LOGIN` | `False` | WeChat + DingTalk QR login |
| `FEATURE_THINKING_COINS` | `False` | Trial-tier org thinking coin wallet |
| `FEATURE_MINDMAP_V2_CANVAS` | `False` | Mind map v2 side-toolbar canvas |

Production hardening: set `COLLAB_FANOUT_ORIGIN_SECRET` (shared across workers), `ALLOWED_HOSTS`, and see [docs/architecture/production_security_deploy.md](docs/architecture/production_security_deploy.md).

---

## API

**Generate PNG diagram (API Key):**

```bash
curl -X POST http://localhost:9527/api/generate_png \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mg_your_key" \
  -d '{"prompt": "Compare cats and dogs", "language": "en"}'
```

API keys are created in the admin panel (`/admin`). See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for full documentation.

---

## Documentation

- [API Reference](docs/API_REFERENCE.md)
- [Changelog](CHANGELOG.md)
- [Architecture](docs/ARCHITECTURE.md)
- [OAuth QR Login](docs/architecture/oauth_qr_login.md)
- [Thinking Coins](docs/architecture/thinking_coins.md)
- [DingTalk Account Binding](docs/architecture/dingtalk_account_binding.md)
- [MindBot Tool Ingress](docs/architecture/mindbot_tool_ingress.md)
- [Production Security Deploy](docs/architecture/production_security_deploy.md)
- [Mind Map v2 Separation](docs/architecture/mindmap_v2_separation.md)
- [File Reader Client](clients/file-reader/README.md)
- [Redis Setup](docs/REDIS_SETUP.md)
- [Qdrant Setup](docs/QDRANT_SETUP.md)
- [PostgreSQL Setup](docs/POSTGRES_SETUP.md)
- [Celery Setup](docs/CELERY_SETUP.md)
- [Fail2ban + AbuseIPDB](docs/FAIL2BAN_SETUP.md)
- [Uvicorn `resource_tracker` / SIGHUP (operations)](docs/operations/UVICORN_RESOURCE_TRACKER.md)

---

## License

Proprietary (All Rights Reserved). See [LICENSE](LICENSE).

**北京思源智教科技有限公司** · Beijing Siyuan Zhijiao Technology Co., Ltd.

---

## Support

- [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
