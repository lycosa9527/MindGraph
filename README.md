# MindGraph

AI-powered diagram generation platform. Transform natural language into professional visual diagrams with support for Thinking Maps, Mind Maps, and Concept Maps.

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5+-42b883.svg)](https://vuejs.org/)
[![Version](https://img.shields.io/badge/Version-5.71.0-brightgreen.svg)](CHANGELOG.md)

---

## Features

**Diagram Types**

- **Thinking Maps** (8 types): Circle, Bubble, Double Bubble, Tree, Brace, Flow, Multi-Flow, Bridge
- **Tree Map**: Center-aligned vertical group layout with DOM-measured adaptive column widths
- **Mind Map**: Radial brainstorming with DOM-measured branch layout and drag-to-reparent
- **Concept Map**: Relationship mapping with AI-generated labels, focus questions, and root concept suggestions

**AI Capabilities**

- Natural language to diagram generation
- Node Palette: AI-suggested nodes with streaming
- Inline AI Recommendations: double-click any node for context-aware auto-completion (all diagram types)
- Concept Map focus question validation and SSE suggestion streams
- Multi-LLM support: Qwen, DeepSeek, Kimi, Doubao (Volcengine)
- Output in 149+ languages (ISO/BCP-47, filterable prompt-language picker)

**Canvas Editor**

- Interactive canvas with export (PNG, SVG, PDF, JSON)
- KaTeX math rendering in diagram labels (mhchem for chemistry notation)
- Branch drag-and-drop (long-press to reparent or swap nodes)
- Presentation mode with laser pointer, spotlight, highlighter, and pen tools
- Auto-save with dirty/saving indicators and relative timestamps
- Diagram snapshots: up to 10 point-in-time versions per diagram with click-to-recall
- Text alignment and rich text-style toolbar
- Mobile web shell (`/m/*`) with touch pinch-zoom and pane pan

**Collaboration & Platform**

- Online canvas collaboration (WebSocket, Redis live-spec merge)
- Workshop Chat (教研坊): school-scoped real-time channels, topics, DMs, reactions, and file attachments
- International landing page with Chinese / International UI version toggle
- Knowledge Space (RAG) for document management and retrieval
- Library with image-based document viewing
- DebateVerse and AskOnce AI features
- School Zone and teacher usage tracking

**Internationalization**

- Full UI in 60+ languages (tier-1: zh, en; tier-2: 50+ bundled locales including RTL Dhivehi)
- Interface language picker with parity-checked bundles
- Prompt output language independent of UI language

**Security & Auth**

- Optional **AbuseIPDB** and **Fail2ban** integration — see [docs/FAIL2BAN_SETUP.md](docs/FAIL2BAN_SETUP.md)
- JWT and API key authentication with Redis cache-aside (5-minute TTL, SHA-256 fingerprinting)
- Captcha on password change; sessions revoked on password update
- Per-feature organization/user access rules (DB-backed, Redis-cached)
- OpenAPI schema served only when `DEBUG=True`
- Health endpoints require JWT; SSE errors do not expose stack traces

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Vue 3.5, TypeScript, Vite 7, Tailwind CSS 4, Pinia, Vue Flow, KaTeX |
| **Backend** | Python 3.13, FastAPI, Uvicorn, Alembic |
| **Data** | PostgreSQL (JSONB), SQLite, Redis 8+, Qdrant |
| **AI** | LangGraph, Dashscope (Qwen), Volcengine (Doubao, DeepSeek, Kimi) |

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- Redis 7.0+ (8.6+ recommended for key-memory histograms and VSET)
- Qdrant (for Knowledge Space)
- PostgreSQL (recommended) or SQLite

### Installation

```bash
git clone https://github.com/lycosa9527/MindGraph.git
cd MindGraph

# Backend: install dependencies, Redis, PostgreSQL, Qdrant, Playwright, and Tesseract OCR
sudo python scripts/setup/setup.py

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
python main.py
```

Database schema migrations (Alembic) run automatically on startup.

Default: `http://localhost:9527`

### Key Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects based on UI version |
| `/mindmate` | AI chat and landing (Chinese version) |
| `/mindgraph` | Diagram gallery |
| `/canvas` | Interactive diagram editor |
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

See `env.example` for full options including feature flags (`FEATURE_WORKSHOP_CHAT`, `FEATURE_LIBRARY`, etc.) and multi-worker settings.

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
- [Redis Setup](docs/REDIS_SETUP.md)
- [Qdrant Setup](docs/QDRANT_SETUP.md)
- [PostgreSQL Setup](docs/POSTGRES_SETUP.md)
- [Fail2ban + AbuseIPDB](docs/FAIL2BAN_SETUP.md)

---

## License

Proprietary (All Rights Reserved). See [LICENSE](LICENSE).

**北京思源智教科技有限公司** · Beijing Siyuan Zhijiao Technology Co., Ltd.

---

## Support

- [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
