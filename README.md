# MindGraph

AI-powered diagram generation platform. Transform natural language into professional visual diagrams with support for Thinking Maps, Mind Maps, and Concept Maps.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5+-42b883.svg)](https://vuejs.org/)
[![Version](https://img.shields.io/badge/Version-5.33.0-brightgreen.svg)](CHANGELOG.md)

---

## Features

**Diagram Types**

- **Thinking Maps** (8 types): Circle, Bubble, Double Bubble, Tree, Brace, Flow, Multi-Flow, Bridge
- **Mind Map**: Radial brainstorming and concept organization
- **Concept Map**: Relationship mapping with AI-generated labels

**AI Capabilities**

- Natural language to diagram generation
- Node Palette: AI-suggested nodes with streaming
- Auto-complete for context-aware diagram completion
- Multi-LLM support: Qwen, DeepSeek, Kimi, Doubao
- Bilingual: Chinese and English

**Platform**

- Interactive canvas editor with export (PNG, SVG, PDF, JSON)
- Knowledge Space (RAG) for document management and retrieval
- Library with image-based document viewing
- JWT and API key authentication

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Vue 3.5, TypeScript, Vite 7, Tailwind CSS 4, Pinia, Vue Flow |
| **Backend** | Python 3.13, FastAPI, Uvicorn |
| **Data** | PostgreSQL / SQLite, Redis, Qdrant |
| **AI** | LangGraph, Dashscope (Qwen), Volcengine (Doubao, DeepSeek, Kimi) |

---

## Quick Start

### Prerequisites

- Python 3.8+ (recommended: 3.13)
- Node.js 18+
- Redis 7.0+
- Qdrant (for Knowledge Space)

### Installation

```bash
git clone https://github.com/lycosa9527/MindGraph.git
cd MindGraph

# Backend: install dependencies and Playwright browsers
python scripts/setup/setup.py

# Frontend
cd frontend && npm install && npm run build && cd ..

# Configuration
cp env.example .env
# Edit .env: set QWEN_API_KEY, REDIS_URL, QDRANT_HOST
```

### Run

```bash
python main.py
```

Default: `http://localhost:9527`

### Key Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to MindMate |
| `/mindmate` | AI chat and landing |
| `/mindgraph` | Diagram gallery |
| `/canvas` | Interactive diagram editor |
| `/knowledge-space` | RAG document management |
| `/library` | Document library |
| `/admin` | Admin panel (API keys, users) |
| `/docs` | API docs (when `DEBUG=True`) |

---

## Configuration

Required environment variables:

```bash
QWEN_API_KEY=your-api-key
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost:6333   # For Knowledge Space
PORT=9527
DEBUG=False
```

See `env.example` for full options.

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

---

## License

Proprietary (All Rights Reserved). See [LICENSE](LICENSE).

**北京思源智教科技有限公司** · Beijing Siyuan Zhijiao Technology Co., Ltd.

---

## Support

- [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
