# MindGraph Architecture Snapshot (Pre-FastAPI Migration)

**Date:** 2025-10-08  
**Git Tag:** v3.4.4-pre-fastapi  
**Branch:** feature/fastapi-migration

---

## Route Inventory (33 Total Routes)

### API Routes (`api_routes.py`) - ~17 routes
- `/api/generate` - POST - Generate diagram
- `/api/enhance` - POST - Enhance diagram
- `/api/export_png` - POST - PNG export
- `/api/ai_assistant/stream` - POST - **SSE streaming (CRITICAL)**
- `/api/health` - GET - Health check
- `/api/status` - GET - System status
- `/api/session/create` - POST - Session management
- `/api/frontend_log` - POST - Frontend logging
- [+ ~9 other endpoints]

### Web Routes (`web_pages.py`) - 11 routes
- `/` - GET - index.html
- `/editor` - GET - editor.html
- `/debug` - GET - debug.html
- `/style-demo` - GET - style-demo.html
- `/test_style_manager` - GET - test_style_manager.html
- `/test_png_generation` - GET - test_png_generation.html
- `/simple_test` - GET - simple_test.html
- `/test_browser` - GET - test_browser_rendering.html
- `/test_bubble_map` - GET - test_bubble_map_styling.html
- `/debug_theme_conversion` - GET - debug_theme_conversion.html
- `/timing_stats` - GET - timing_stats.html

### Learning Routes (`api/routes/learning_routes.py`) - 4 routes
- `/api/learning/start_session` - POST - Initialize learning session
- `/api/learning/validate_answer` - POST - Validate student answer (uses V2 + V3 agents)
- `/api/learning/get_hint` - POST - Get AI hint
- `/api/learning/verify_understanding` - POST - Verify understanding

### Cache Routes (app.py) - 3 routes
- `/cache/status` - GET - JavaScript cache status
- `/cache/performance` - GET - Cache performance metrics
- `/cache/modular` - GET - Modular cache stats

---

## HTTP Client Usage (8 Files)

| File | Usage | Status |
|------|-------|--------|
| `dify_client.py` | `requests.post(stream=True)` | ❌ Blocking SSE |
| `llm_clients.py` (sync) | `requests.post()` | ❌ Sync methods |
| `llm_clients.py` (async) | `aiohttp.ClientSession()` | ✅ Keep |
| `agents/main_agent.py` | `requests.post()` | ❌ LLM calls |
| `app.py` | `requests.get()` (startup only) | ⚠️ Low priority |

---

## Agent System (~20+ files)

### Core
- `agents/main_agent.py` - Main orchestrator (sync)
- `agents/core/base_agent.py` - Base class

### Diagram Types
- `agents/concept_maps/concept_map_agent.py`
- `agents/mind_maps/mind_map_agent.py`
- `agents/thinking_maps/*.py` (8 files)
- `agents/thinking_tools/*.py` (9 files)

### Learning System
- `agents/learning/learning_agent.py` (V2 - LangChain)
- `agents/learning/learning_agent_v3.py` (V3 - LangChain)

---

## Already Async Components ✅

- `browser_manager.py` - Uses `async_playwright`
- `llm_clients.py` (async methods) - Uses `aiohttp`
- Templates (Jinja2) - Compatible with FastAPI
- Static files - No changes needed

---

## Critical Bottlenecks Identified

1. **SSE Streaming** (`dify_client.py` line 69-101)
   - Blocks thread with `requests.post(stream=True)`
   - Limits concurrent SSE to ~6-100 connections

2. **LLM Clients** (`llm_clients.py` line 91, 259, 358)
   - Hybrid sync/async causes confusion
   - Sync methods use blocking `requests`

3. **Agent System** (`agents/main_agent.py` line 324)
   - All generation methods are synchronous
   - Uses `ThreadPoolExecutor` (line 982) instead of `asyncio.gather()`

4. **Learning Routes** (`api/routes/learning_routes.py`)
   - All routes are synchronous
   - LangChain agents are sync (acceptable temporary)

---

## Migration Targets

- **Routes:** 0% async → 100% async (33/33 routes)
- **HTTP Clients:** 8 files with `requests` → 0 files (100% aiohttp)
- **Concurrency:** 6-100 SSE → 4,000+ SSE
- **Memory/Connection:** 8-10 MB → 2 MB
- **Server:** Waitress (WSGI) → Uvicorn (ASGI)
- **Framework:** Flask → FastAPI

---

**This snapshot documents the application state before FastAPI migration begins.**

