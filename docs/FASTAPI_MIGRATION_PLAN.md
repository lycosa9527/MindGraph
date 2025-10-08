# MindGraph Flask → FastAPI Migration Plan
## Full Async Rewrite with Uvicorn

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Target:** 100+ concurrent users with SSE support  
**Timeline:** 6-7 days focused development  
**Priority:** High - Required for production scale

---

## 📊 Migration Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BEFORE (Flask + Waitress)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Flask App (app.py)                                                         │
│    ├─ Blueprints: api_routes.py, web_pages.py, learning_routes.py         │
│    ├─ HTTP Client: requests (SYNC, BLOCKING) ❌                            │
│    ├─ Server: Waitress (WSGI, thread-based)                                │
│    └─ Concurrency: 6-100 SSE connections (thread-limited)                  │
│                                                                             │
│  Critical Bottlenecks:                                                      │
│    • dify_client.py: requests.post(stream=True) blocks threads             │
│    • llm_clients.py: Hybrid sync/async (inconsistent)                      │
│    • agents/main_agent.py: Synchronous LLM calls                           │
│    • ThreadPoolExecutor: CPU overhead, context switching                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                    ⬇️  MIGRATION ⬇️

┌─────────────────────────────────────────────────────────────────────────────┐
│                       AFTER (FastAPI + Uvicorn)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FastAPI App (main.py)                                                      │
│    ├─ Routers: routers/api.py, routers/pages.py, routers/learning.py      │
│    ├─ HTTP Client: aiohttp (ASYNC, NON-BLOCKING) ✅                        │
│    ├─ Server: Uvicorn (ASGI, event-loop based)                             │
│    └─ Concurrency: 4,000+ SSE connections (event-loop efficient)           │
│                                                                             │
│  Performance Improvements:                                                  │
│    • async_dify_client.py: async for chunk in response.content             │
│    • llm_clients.py: 100% async, no sync methods                           │
│    • agents/main_agent.py: await llm_client.chat_completion()              │
│    • asyncio.gather(): Parallel async operations, no threads               │
│                                                                             │
│  Key Benefits:                                                              │
│    • Memory: 8MB → 2MB per connection (75% reduction)                      │
│    • Scalability: 100x improvement in concurrent SSE                       │
│    • Cross-platform: Windows 11 + Ubuntu (same server)                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Migration Strategy: 100% Async, No Compromises

| Component | Current | Target | Action |
|-----------|---------|--------|--------|
| **HTTP Library** | `requests` (8 files) | `aiohttp` (100%) | DELETE all `requests`, replace with `aiohttp` |
| **Routes** | Flask routes (0% async) | FastAPI routes (100% async) | Convert all 33 routes to `async def` |
| **LLM Clients** | Hybrid sync/async | Pure async | DELETE sync methods, keep only async |
| **SSE Streaming** | Blocking generator | Async generator | `async for` instead of `for` |
| **Concurrency** | ThreadPoolExecutor | asyncio.gather() | Replace threads with async tasks |

---

## 📑 Table of Contents

### Quick Reference
- [Executive Summary](#executive-summary) - Overview and goals
- [Code Review Checklist](#code-review-and-pre-migration-analysis) - Current state analysis
- [Migration Phases](#phase-1-pre-migration-preparation-day-0) - 8 phases with detailed steps
- [Final Verification](#final-code-review-checklist) - Complete file inventory and verification
- [Success Metrics](#-success-metrics---quantified) - Measurable targets

### Core Sections
1. **[Pre-Migration Analysis](#code-review-and-pre-migration-analysis)**
   - Already async components ✅
   - Critical items requiring migration ❌
   - Migration complexity assessment

2. **[Phase 1: Preparation](#phase-1-pre-migration-preparation-day-0)** (4 hours)
   - Code freeze and branching
   - Dependency installation
   - Architecture documentation

3. **[Phase 2: Core Framework Migration](#phase-2-core-framework-migration-days-1-2)** (1.5 days)
   - FastAPI app structure
   - Route migration (33 routes)
   - Pydantic models creation
   - Middleware migration

4. **[Phase 3: Async HTTP Client Migration](#phase-3-async-http-client-migration-day-2-3)** (1.5 days) ⚠️ **CRITICAL**
   - Dify client async rewrite
   - LLM clients 100% async conversion
   - Agent system async integration
   - Browser manager integration

5. **[Phase 4: Configuration Migration](#phase-4-configuration-and-settings-migration-day-3)** (0.5 days)
   - Settings module verification
   - Environment configuration

6. **[Phase 5: Server Configuration](#phase-5-server-configuration-day-3)** (0.5 days)
   - Uvicorn setup
   - Server launcher update
   - Cross-platform testing

7. **[Phase 6: Testing Strategy](#phase-6-testing-strategy-day-4)** (1 day)
   - Unit testing
   - Integration testing
   - Load testing (100+ SSE)
   - Cross-platform validation

8. **[Phase 7: Deployment and Rollout](#phase-7-deployment-and-rollout-day-5)** (0.5 days)
   - Documentation updates
   - Gradual rollout strategy
   - Rollback plan

9. **[Phase 8: Optimization and Cleanup](#phase-8-optimization-and-cleanup-post-migration)** (1-2 days)
   - Code cleanup (remove Flask)
   - Performance optimization
   - **LangChain full async migration** (100% async achieved)
   - API versioning

### Reference Materials
- [Final Code Review Checklist](#final-code-review-checklist) - Complete file inventory
- [Migration Verification Matrix](#-migration-verification-matrix) - Phase-by-phase verification commands
- [Success Metrics](#-success-metrics---quantified) - Quantified performance targets
- [Timeline Summary](#timeline-summary) - Phase durations and deliverables
- [Key Files Reference](#key-files-reference) - Files to create, modify, remove
- [Risk Mitigation](#risk-mitigation) - Identified risks and strategies
- [Migration Checklist](#migration-checklist) - Step-by-step checklist

---

## 🚀 Quick Start Guide for Cursor

### How to Use This Document

**If you're starting the migration:**
1. Read [Executive Summary](#executive-summary) for context
2. Review [Code Review Checklist](#code-review-and-pre-migration-analysis) to understand current state
3. Follow phases sequentially starting from [Phase 1](#phase-1-pre-migration-preparation-day-0)
4. Run verification commands after each phase

**If you're debugging a specific component:**
- **SSE Streaming Issues**: See [Phase 3.1 Dify Client](#31-dify-client-async-rewrite) + [Pattern 5](#pattern-5-sse-streaming-critical---most-complex)
- **Route Migration**: See [Phase 2.1 FastAPI Structure](#21-create-fastapi-application-structure) + [Pattern 4](#pattern-4-flask-route--fastapi-route)
- **LLM Client Issues**: See [Phase 3.2 LLM Clients](#32-llm-clients-full-async-migration-100-async) + [Pattern 2](#pattern-2-synchronous-llm-calls-must-convert)
- **Agent System**: See [Phase 3.4 Agent System](#34-agent-system-async-integration) + [Pattern 3](#pattern-3-threadpoolexecutor-replace-with-asynciogather)
- **Testing**: See [Phase 6 Testing Strategy](#phase-6-testing-strategy-day-4)

**If you're verifying the migration:**
- Jump to [Final Code Review Checklist](#final-code-review-checklist)
- Run commands from [Migration Verification Matrix](#-migration-verification-matrix)
- Check [Success Metrics](#-success-metrics---quantified)

### Key Numbers to Remember
- **33 routes** total across 3 blueprints (all need async conversion)
- **8 files** use `requests` library (must be 0 after migration)
- **4,000+** target concurrent SSE connections
- **100% async** - no hybrid solutions, no compromises
- **6-7 days** expected timeline with thorough verification

### Critical Success Factors
✅ **MUST DELETE** all `requests` library usage  
✅ **MUST CONVERT** all routes to `async def`  
✅ **MUST VERIFY** SSE streaming works with 100+ concurrent connections  
✅ **MUST TEST** on both Windows 11 and Ubuntu  
✅ **MUST ACHIEVE** 100% async (no thread pools except temporary LangChain)

---

## Executive Summary

This document outlines the complete migration path from Flask + Waitress to FastAPI + Uvicorn with full async/await support. The migration will enable handling 4,000+ concurrent Server-Sent Events (SSE) connections for the MindMate AI assistant and other real-time features.

### Current State
- **Framework:** Flask 3.1.1 with Blueprint architecture
- **Server:** Waitress 3.0.0 (WSGI, synchronous, thread-based)
- **HTTP Client:** requests library (synchronous, blocking)
- **Routes:** ~20 endpoints across 3 Blueprints (api, web, learning)
- **Templates:** 3 Jinja2 templates (index.html, editor.html, debug.html)
- **Concurrency:** Limited to ~6-100 concurrent SSE connections (thread-limited)
- **Platforms:** Windows 11 (development), Ubuntu (production)
- **Special Features:** JavaScript lazy cache system, LangChain integration, request/response logging middleware
- **Dependencies:** LangChain, Playwright (async capable), custom logging with ANSI colors

### Target State
- **Framework:** FastAPI 0.100+ with APIRouter architecture
- **Server:** Uvicorn with multiple workers (ASGI, async)
- **HTTP Client:** aiohttp (asynchronous, non-blocking)
- **Routes:** Same ~20 endpoints, all async
- **Templates:** Jinja2Templates (compatible, minimal changes)
- **Concurrency:** ~4,000 concurrent SSE connections per deployment
- **Platforms:** Windows 11 + Ubuntu (same codebase, same command)

### Key Benefits
1. **Scalability:** 6-100 → 4,000+ concurrent SSE connections
2. **Performance:** Non-blocking I/O for all external API calls
3. **Memory:** ~2MB per connection (vs ~8-10MB with threads)
4. **Cross-Platform:** Same server (Uvicorn) works on Windows + Ubuntu
5. **Modern:** Auto-generated OpenAPI/Swagger documentation
6. **Type Safety:** Pydantic models for request/response validation
7. **Future-Proof:** Native async/await throughout the stack

---

## Code Review and Pre-Migration Analysis

### ✅ Good News: Some Components Already Async-Ready!

#### 1. **Browser Manager - Already Async! ✅**
**File:** `browser_manager.py`
- ✅ Already uses `async_playwright` (not sync Playwright)
- ✅ `BrowserContextManager` is async context manager (`async __aenter__`, `async __aexit__`)
- ✅ All methods are async: `await browser.launch()`, `await context.close()`
- **Migration Impact:** Minimal! Just integrate into FastAPI async routes
- **Action:** Keep as-is, verify it works in async FastAPI context

#### 2. **LLM Clients - Partially Async! ⚠️**
**File:** `llm_clients.py`
- ✅ Has async methods: `async def chat_completion()` using aiohttp
- ❌ ALSO has sync methods: `def chat_completion()` using requests (backward compatibility)
- ✅ `QwenClient` already uses `aiohttp.ClientSession` for async calls
- **Current State:** Hybrid - supports both sync and async
- **Migration Impact:** Medium - **REMOVE all sync methods, go 100% async**
- **Action:** Delete sync methods immediately, use ONLY async throughout
- **Goal:** Full async stack for maximum SSE concurrency

### ⚠️ Critical Items Requiring Migration

#### 3. **Dify Client - Sync Only! ❌**
**File:** `dify_client.py` (Lines 69-78)
```python
response = requests.post(
    url,
    json=payload,
    headers={...},
    stream=True,  # ← BLOCKING!
    timeout=(10, self.timeout)
)
for line in response.iter_lines(decode_unicode=True):  # ← BLOCKING!
```
- ❌ Uses synchronous `requests.post()` with `stream=True`
- ❌ `iter_lines()` blocks the thread
- **Impact:** HIGH - This is your MindMate AI SSE endpoint bottleneck!
- **Priority:** CRITICAL - Must convert to aiohttp
- **Action:** Create `async_dify_client.py` with aiohttp as planned

#### 4. **Main Agent - Sync Methods! ❌**
**File:** `agents/main_agent.py`
- ❌ All generation functions are synchronous:
  - `generate_graph_spec()` - sync
  - `generate_concept_map_two_stage()` - sync
  - `generate_concept_map_unified()` - sync
- Uses `llm_clients.py` but calls sync methods
- **Impact:** HIGH - All diagram generation is blocking
- **Action:** Convert to async, call async llm_clients methods

#### 5. **Flask Dependencies - Everywhere! ❌**
**Files with Flask imports:** 6 files
- `app.py` - Main Flask app
- `api_routes.py` - API Blueprint
- `web_pages.py` - Web Blueprint
- `api/routes/learning_routes.py` - Learning Blueprint
- `setup.py` - Installation script
- `docker/docker-entrypoint.sh` - Docker startup

**Flask-specific patterns found:**
```python
from flask import Blueprint, request, jsonify, render_template, send_file
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
```

### 📊 Migration Complexity Assessment

| Component | Current State | Async Ready? | Migration Effort | Priority |
|-----------|---------------|--------------|------------------|----------|
| **browser_manager.py** | ✅ Async | 100% | None | Low |
| **llm_clients.py** | ⚠️ Hybrid | 50% | Low | Medium |
| **dify_client.py** | ❌ Sync | 0% | High | **CRITICAL** |
| **agents/main_agent.py** | ❌ Sync | 0% | High | High |
| **app.py** | ❌ Flask | 0% | Very High | High |
| **api_routes.py** | ❌ Flask | 0% | Very High | **CRITICAL** |
| **web_pages.py** | ❌ Flask | 0% | Medium | Medium |
| **learning_routes.py** | ❌ Flask | 0% | High | High |

### 🎯 Migration Strategy: 100% Async, No Compromises

**Philosophy:** Full async/await throughout the stack for maximum SSE performance and scalability.

**No Hybrid Solutions:**
- ❌ No sync fallbacks
- ❌ No thread pool workarounds (except temporary LangChain)
- ❌ No "backward compatibility" with blocking code
- ✅ Pure async from HTTP to database/API calls
- ✅ All I/O operations non-blocking
- ✅ Maximum concurrent SSE connections (4,000+)

#### Phase 1 Priority Order (Critical Path):
1. **Dify Client** → 100% async with aiohttp for SSE (MindMate AI)
2. **API Routes** → All endpoints async, no blocking calls
3. **LLM Clients** → **DELETE all sync methods**, async only
4. **Main Agent** → 100% async diagram generation
5. **Learning Routes** → Async educational features
6. **Web Routes** → Async template rendering (minimal I/O)

#### Reusable Components (Keep As-Is):
- ✅ `browser_manager.py` - Already async, no changes needed
- ✅ `settings.py` - Config is sync (fast), can be called from async
- ✅ `static/js/lazy_cache_manager.py` - File I/O, not Flask-specific
- ✅ All templates (HTML files) - Jinja2 compatible with FastAPI
- ✅ All static files (CSS, JS) - No changes needed

### 🔍 Detailed Code Patterns to Migrate

#### Pattern 1: Flask Route → FastAPI Route
**Current (Flask):**
```python
# api_routes.py
from flask import Blueprint, request, jsonify
api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/generate', methods=['POST'])
def generate():
    data = request.json
    result = agent.generate(data['prompt'])
    return jsonify({'success': True, 'data': result})
```

**Target (FastAPI):**
```python
# routers/api.py
from fastapi import APIRouter, HTTPException
from models.requests import GenerateRequest
from models.responses import GenerateResponse

router = APIRouter(prefix='/api')

@router.post('/generate', response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    result = await agent.generate(req.prompt)  # async call
    return {'success': True, 'data': result}
```

#### Pattern 2: SSE Streaming
**Current (Flask) - BLOCKING:**
```python
# api_routes.py Line 2840
from flask import Response, stream_with_context

def generate():
    for chunk in client.stream_chat(message, user_id):  # BLOCKS!
        yield f"data: {json.dumps(chunk)}\n\n"

return Response(stream_with_context(generate()), 
                mimetype='text/event-stream')
```

**Target (FastAPI) - NON-BLOCKING:**
```python
# routers/api.py
from fastapi.responses import StreamingResponse

async def generate():
    async for chunk in client.stream_chat(message, user_id):  # ASYNC!
        yield f"data: {json.dumps(chunk)}\n\n"

return StreamingResponse(generate(), media_type='text/event-stream')
```

#### Pattern 3: Template Rendering
**Current (Flask):**
```python
# web_pages.py
from flask import render_template

@web.route('/')
def index():
    return render_template('index.html', title='MindGraph')
```

**Target (FastAPI):**
```python
# routers/pages.py
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@router.get('/')
async def index(request: Request):
    return templates.TemplateResponse('index.html', 
                                     {'request': request, 'title': 'MindGraph'})
```

#### Pattern 4: Error Handling
**Current (Flask):**
```python
# app.py Line 589
from werkzeug.exceptions import HTTPException

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    return jsonify({'error': 'Unexpected error'}), 500
```

**Target (FastAPI):**
```python
# main.py
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse({'error': exc.detail}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse({'error': 'Unexpected error'}, status_code=500)
```

### ⚠️ Critical Migration Gotchas Identified

#### Gotcha 1: Sync/Async Method Name Collision ⚠️
**Problem:** `llm_clients.py` has BOTH async and sync `chat_completion()` methods
```python
# Line 38: Async version
async def chat_completion(self, messages: List[Dict], ...):
    async with aiohttp.ClientSession() as session:
        ...

# Line 91: Sync version (SAME NAME!)
def chat_completion(self, messages: List[Dict], ...):
    response = requests.post(...)
```

**Solution (100% Async Approach):**
- ❌ **DELETE sync method entirely** (not rename, DELETE)
- ✅ Keep ONLY async version
- ✅ Update all callers to use `await client.chat_completion()`
- ✅ Remove `requests` library from this file
- **Rationale:** No hybrid code → cleaner, faster, more maintainable
- **Timeline:** Phase 3.2 (not deferred to Phase 8)

#### Gotcha 2: LLM Result Caching
**Location:** `api_routes.py` Lines 88-91
```python
_LLM_RESULT_CACHE = {}
_LLM_CACHE_TTL_SECONDS = 300  # 5 minutes
```

**Problem:** Global dict cache is not thread-safe with multiple Uvicorn workers!

**Solution:**
- Use async-safe cache (Redis or FastAPI `@lru_cache`)
- Or accept cache per-worker (simple, acceptable)
- Document cache behavior with multiple workers

#### Gotcha 3: Request Timing in Middleware
**Location:** `app.py` Lines 291-325
```python
@app.before_request
def log_request():
    request.start_time = time.time()  # Attach to Flask request object

@app.after_request
def log_response(response):
    response_time = time.time() - request.start_time  # Read from Flask request
```

**Problem:** FastAPI doesn't have `request.start_time` attribute attachment

**Solution:**
- Use FastAPI middleware with `state` or `contextvars`
- Store timing in request.state.start_time
- Access in middleware response callback

#### Gotcha 4: Dependency Validation at Startup
**Location:** `app.py` Lines 173-252 - `validate_dependencies()`
```python
required_packages = ['flask', 'requests', 'langchain', ...]
```

**Problem:** Validates Flask presence (will fail after migration)

**Solution:**
- Update validation to check for FastAPI, uvicorn, aiohttp
- Remove Flask from validation after cutover
- Add FastAPI-specific checks

### 📝 Updated Migration Checklist Based on Code Review

#### Pre-Flight Checks ✓
- [x] Confirmed browser_manager.py is already async ✅
- [x] Confirmed llm_clients.py has async methods ✅
- [x] Identified dify_client.py as critical blocker ❌
- [x] Identified main_agent.py needs async conversion ❌
- [x] Found 6 files with Flask dependencies
- [x] Found 12 files with requests library usage
- [x] Confirmed templates are Jinja2 (FastAPI compatible)

#### Risk Mitigation Strategies (100% Async Focus):
1. **Keep browser_manager.py unchanged** - Already async, battle-tested ✅
2. **Delete sync methods from llm_clients.py immediately** - No hybrid code ✅
3. **Prioritize dify_client.py async rewrite** - Critical for SSE performance ✅
4. **LangChain: Thread pool ONLY temporarily** - Migrate to async in Phase 8 ⚠️
5. **All new code must be async** - No exceptions, no blocking I/O ✅
6. **Parallel deployment** - Flask + FastAPI coexist during migration only ⚠️

**Non-Negotiables for 100% Async:**
- All HTTP calls → aiohttp (no requests library)
- All database calls → async drivers (if added)
- All LLM calls → async methods only
- All file I/O → aiof files or minimal blocking
- All SSE → StreamingResponse with async generators

---

## Phase 1: Pre-Migration Preparation (Day 0)

### 1.1 Code Freeze and Branch Management
**Objective:** Establish clean migration environment

**Actions:**
- Create git branch: `feature/fastapi-migration`
- Tag current stable version: `git tag v3.4.4-pre-fastapi`
- Ensure all current features are committed and working
- Run full test suite to establish baseline
- Document current API behavior (manual testing checklist)

**Success Criteria:**
- Clean git branch created
- All tests passing on main branch
- Current version tagged for rollback

---

### 1.2 Dependency Analysis and Installation
**Objective:** Install FastAPI ecosystem without breaking Flask

**New Dependencies to Add to `requirements.txt`:**
```
# ============================================================================
# FASTAPI DEPENDENCIES (New - for migration)
# ============================================================================
fastapi>=0.104.0
uvicorn[standard]>=0.24.0  # Replaces waitress (works on Windows + Ubuntu)

# Async HTTP Client (replaces requests for async calls)
aiohttp>=3.9.0

# ASGI Middleware and Utilities
python-multipart>=0.0.6  # For form data and file uploads
sse-starlette>=1.8.0     # Optional: Better SSE support

# ============================================================================
# KEEP DURING MIGRATION (Remove in Phase 8)
# ============================================================================
# Flask (coexists during migration, remove after)
# waitress (coexists during migration, remove after)
```

**Dependencies to Remove (Phase 8 - 100% Async Cleanup):**
```
# These stay ONLY during migration, DELETE when FastAPI is stable:
Flask>=3.1.1           # Replaced by FastAPI
Werkzeug>=3.1.0        # Flask dependency
flask-cors>=6.0.0      # Replaced by FastAPI CORSMiddleware
waitress>=3.0.0        # Replaced by Uvicorn
requests>=2.31.0       # ← DELETE COMPLETELY - Replaced by aiohttp 100%
```

**⚠️ Critical: requests Library Must Be FULLY Removed**
- NOT "if all calls migrated" - MUST migrate ALL calls
- No exceptions, no fallbacks, no "legacy" code
- 100% aiohttp for all HTTP operations
- Verify: `grep -r "import requests" .` returns ZERO results (except tests)

**Actions:**
- Update `requirements.txt` with new dependencies
- Install in development environment: `pip install -r requirements.txt`
- Verify no conflicts with existing Flask dependencies
- Test that both Flask and FastAPI can import successfully

**Success Criteria:**
- All dependencies installed without conflicts
- `import fastapi` works
- `import uvicorn` works
- Flask app still runs: `python run_server.py`

---

### 1.3 Current Architecture Documentation
**Objective:** Map all components for migration reference

**Files to Document:**

#### Core Application Files
- `app.py` (852 lines) - Main Flask application, logging setup, banner display
- `api_routes.py` (~2,920 lines) - All API endpoints, Blueprint architecture
- `web_pages.py` - Template rendering routes
- `run_server.py` - Server launcher (Waitress)
- `waitress.conf.py` - Server configuration

#### Supporting Modules
- `dify_client.py` - Dify API integration (synchronous HTTP, needs async rewrite)
- `llm_clients.py` - LLM integrations (Qwen, DeepSeek, Kimi - needs async)
- `settings.py` - Configuration management
- `browser_manager.py` - Playwright for PNG export
- All agent modules in `agents/` directory

#### Frontend Assets
- `templates/` - 3 Jinja2 templates (minimal changes needed)
- `static/` - CSS, JS, fonts (no changes needed)

**Create Documentation:**
- List all `@app.route()` and `@api.route()` endpoints with methods
- Map Blueprint structure to future APIRouter structure
- Identify all synchronous external API calls (requests library usage)
- Document custom middleware and error handlers
- List all template rendering endpoints

**Success Criteria:**
- Complete route inventory created
- All external HTTP calls identified
- Middleware and error handlers documented

---

## Phase 2: Core Framework Migration (Days 1-2)

### 2.1 Create FastAPI Application Structure
**Objective:** Set up parallel FastAPI app alongside Flask

**New Files to Create:**

#### `main.py` - FastAPI Application Entry Point
**Purpose:** Replace `app.py` as the main application file

**Key Components:**
- FastAPI app initialization with metadata (title, version, description)
- CORS middleware configuration (match current Flask-CORS settings)
- Custom logging middleware to match UnifiedFormatter
- Static files mounting for `/static` directory
- Template configuration for Jinja2Templates
- Include all routers (APIRouter instances)
- Lifespan events for startup/shutdown (replace Flask @app.before_first_request)
- Exception handlers for 404, 500, custom errors

**Configuration to Preserve:**
- Use same logging format from current `UnifiedFormatter`
- Same CORS settings from Flask-CORS
- Same environment variable loading from .env
- Same banner display on startup

---

#### `routers/__init__.py` - Router Package
**Purpose:** Organize routes into modules (replace Flask Blueprints)

**Structure:**
```
routers/
├── __init__.py
├── api.py          # Main API routes (from api_routes.py)
├── pages.py        # Template rendering routes (from web_pages.py)
├── learning.py     # Learning mode routes (from api/routes/learning_routes.py)
└── health.py       # Health check endpoints
```

---

#### `routers/api.py` - API Routes Migration
**Purpose:** Convert all API routes from `api_routes.py`

**Migration Pattern for Each Route:**

**Key Changes:**
1. Replace `@api.route('/endpoint', methods=['POST'])` with `@router.post('/endpoint')`
2. Replace function `def` with `async def`
3. Replace `request.json` with Pydantic model parameters
4. Replace `jsonify(...)` with direct dict return
5. Replace `request.args` with FastAPI Query parameters
6. Replace `request.files` with FastAPI File/UploadFile
7. Replace Flask `abort(404)` with `raise HTTPException(status_code=404)`
8. Replace `@handle_api_errors` decorator with FastAPI exception handling

**Critical SSE Endpoints to Migrate:**
- `/api/ai_assistant/stream` - MindMate AI SSE endpoint
  - Replace `Response(stream_with_context(generate()), mimetype='text/event-stream')`
  - With `StreamingResponse(generate(), media_type='text/event-stream')`
  - Make generator function `async def generate()`
  - Use async HTTP client in generator

**All Routes to Convert (~20+ total):**

**API Routes (api_routes.py):**
1. `/api/generate` - Generate diagram
2. `/api/enhance` - Enhance diagram
3. `/api/export_png` - PNG export
4. `/api/ai_assistant/stream` - SSE streaming (CRITICAL)
5. `/api/health` - Health check
6. `/api/status` - System status
7. `/api/session/create` - Session management
8. `/api/frontend_log` - Frontend logging endpoint
9. All other endpoints in `api_routes.py`

**Web Routes (web_pages.py):**
1. `/` - Landing page (index.html)
2. `/editor` - Interactive editor (editor.html)
3. `/debug` - Debug panel (debug.html)

**Learning Routes (api/routes/learning_routes.py):**
1. `/api/learning/start_session` - Initialize learning session
2. `/api/learning/submit_answer` - Submit student answer
3. `/api/learning/get_hint` - Get AI hint
4. `/api/learning/end_session` - End learning session

**Cache Routes (app.py):**
1. `/cache/status` - JavaScript cache status
2. `/cache/performance` - Cache performance metrics
3. `/cache/modular` - Modular cache stats

**Preserve:**
- All validation logic
- All error handling logic
- All logging statements
- All business logic

---

#### `routers/pages.py` - Template Routes Migration
**Purpose:** Convert template rendering routes from `web_pages.py`

**Migration Pattern:**

**Key Changes:**
1. Replace `render_template('index.html', **context)`
2. With `templates.TemplateResponse('index.html', {'request': request, **context})`
3. Add `request: Request` parameter to all template functions
4. Make functions `async def` (optional but recommended)

**Templates to Support:**
- `/` - index.html (landing page)
- `/editor` - editor.html (interactive editor)
- `/debug` - debug.html (debug panel)

---

### 2.2 Pydantic Models Creation
**Objective:** Define request/response models for type safety

**Create `models/` Package:**
```
models/
├── __init__.py
├── requests.py     # All request body models
├── responses.py    # All response models
└── common.py       # Shared models
```

**Models to Create (Based on Current API):**

#### Request Models
- `GenerateRequest` - For `/api/generate` endpoint
  - diagram_type: str
  - prompt: str
  - llm: str = "qwen"
  - user_context: Optional[dict]

- `EnhanceRequest` - For `/api/enhance` endpoint
  - diagram_data: dict
  - enhancement_type: str
  - llm: str

- `ExportPNGRequest` - For `/api/export_png`
  - diagram_data: dict
  - diagram_type: str
  - export_options: Optional[dict]

- `AIAssistantRequest` - For `/api/ai_assistant/stream`
  - message: str
  - user_id: str
  - conversation_id: Optional[str]

- Create models for all other endpoints

#### Response Models
- `GenerateResponse` - Success response with diagram data
- `ErrorResponse` - Standard error format
- `HealthResponse` - Health check status
- `StatusResponse` - System status information

**Validation to Add:**
- String length limits
- Required vs optional fields
- Field constraints (e.g., llm must be in ["qwen", "deepseek", "kimi"])
- Default values

---

### 2.3 Middleware Migration
**Objective:** Preserve current middleware functionality

**Current Middleware to Migrate:**

1. **CORS Middleware**
   - Current: `flask_cors.CORS(app)`
   - Target: `app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)`
   - Preserve all current CORS settings

2. **Logging Middleware**
   - Current: Custom `UnifiedFormatter` in app.py with ANSI color codes
   - Target: Custom FastAPI middleware that logs requests/responses
   - Preserve same log format: `[HH:MM:SS] LEVEL | Source | Message`
   - Keep color coding for terminal output (DEBUG=cyan, INFO=green, WARN=yellow, ERROR=red, CRIT=magenta)
   - Preserve source abbreviation logic (APP, API, FRNT, CONF, SRVR, etc.)
   - Preserve file logging to `logs/app.log`

3. **Request/Response Timing Middleware**
   - Current: `@app.before_request` and `@app.after_request` hooks
   - Functionality:
     - Attach start_time to each request
     - Log request method, path, remote_addr
     - Calculate and log response time
     - Detect slow requests (>5s general, >20s for PNG generation)
     - Block access to deprecated `/static/js/d3-renderers.js` file (return 403)
   - Target: FastAPI middleware with same functionality
   - Keep all threshold values and blocking logic

4. **Error Handling Middleware**
   - Current: Single `@app.errorhandler(Exception)` for all exceptions
   - Functionality:
     - Pass through HTTPException with original code
     - Log unhandled exceptions with full traceback
     - Return user-friendly error in production
     - Include debug info in development mode (config.DEBUG)
   - Target: FastAPI exception handlers
   - Preserve same error response format: `{'error': '...'}`
   - Keep debug mode detection from config

**New Middleware to Add:**

5. **Request ID Middleware** (Optional but Recommended)
   - Add unique request ID to each request
   - Include in logs for request tracing
   - Useful for debugging SSE issues

6. **Static File Access Control Middleware**
   - Block access to deprecated files (d3-renderers.js)
   - Return 403 Forbidden with custom message
   - Log attempted access for security monitoring

---

### 2.4 Static Files and Templates Setup
**Objective:** Preserve frontend functionality

**Static Files:**
- Mount `/static` directory: `app.mount("/static", StaticFiles(directory="static"), name="static")`
- No changes to actual static files needed
- Verify all CSS, JS, fonts, images accessible

**Templates:**
- Configure Jinja2Templates: `templates = Jinja2Templates(directory="templates")`
- No changes to HTML files needed (Jinja2 syntax identical)
- Update template rendering calls to include `request` parameter
- Verify all template variables passed correctly

**Verification:**
- All static files load at `/static/*` paths
- All templates render correctly
- No broken links or missing assets

---

## Phase 3: Async HTTP Client Migration (Day 2-3)

### 3.1 Dify Client Async Rewrite
**Objective:** Convert `dify_client.py` to use async HTTP

**Current Implementation:**
- File: `dify_client.py` (149 lines)
- Uses: `requests.post(..., stream=True)` - synchronous, blocking
- SSE parsing: `for line in response.iter_lines(decode_unicode=True)`

**Target Implementation:**

**Create `async_dify_client.py`:**

**Key Changes:**
1. Replace `requests` with `aiohttp`
2. Change class methods to `async def`
3. Use `async with aiohttp.ClientSession()` for HTTP calls
4. Use `async for line in response.content` for streaming
5. Keep same SSE parsing logic (data: prefix handling)
6. Keep same error handling
7. Keep same logging

**Method to Rewrite:**
- `stream_chat()` → `async def stream_chat()`
  - Replace `requests.post()` with `session.post()`
  - Replace `response.iter_lines()` with `async for line in response.content`
  - Keep yielding JSON chunks in SSE format
  - Keep [DONE] signal handling
  - Keep timeout configuration

**Testing Requirements:**
- Verify SSE events arrive in correct order
- Verify conversation_id preservation
- Verify error handling works
- Verify timeout behavior

---

### 3.2 LLM Clients Full Async Migration (100% Async)
**Objective:** Convert llm_clients.py to 100% async, DELETE all sync code

**Current Implementation:**
- File: `llm_clients.py`
- ✅ Has async methods (using aiohttp)
- ❌ Also has sync methods (using requests)
- Multiple LLM integrations: Qwen, DeepSeek, Kimi

**Target Implementation (100% Async):**

**Modify `llm_clients.py` in-place (NOT create new file):**

**Critical Changes - DELETE Sync Code:**

1. **Remove ALL Sync Methods:**
   ```python
   # DELETE these methods entirely:
   def chat_completion(self, messages, ...):  # ← DELETE
       response = requests.post(...)          # ← DELETE
       ...
   ```

2. **Keep ONLY Async Methods:**
   ```python
   # KEEP and enhance:
   async def chat_completion(self, messages, ...):  # ← KEEP
       async with aiohttp.ClientSession() as session:
           async with session.post(...) as response:
               ...
   ```

3. **Remove requests Library:**
   - Delete `import requests` from file
   - Remove requests from this file's dependencies
   - 100% aiohttp for all HTTP calls

**For Each LLM Client (Qwen, DeepSeek, Kimi):**

1. **Delete sync methods completely**
   - No backward compatibility
   - No "just in case" fallbacks
   - Pure async only

2. **Enhance async methods:**
   - Connection pooling with aiohttp
   - Proper timeout handling
   - Retry logic (async)
   - Error handling (async)

3. **Streaming support:**
   - Use `async for chunk in response.content`
   - Yield chunks in async generator
   - Proper cleanup of connections

**Shared Async Utilities:**
- Async retry decorator
- Async timeout wrapper  
- Async connection pool manager
- Async rate limiting

**Integration Points:**
- All routes MUST be `async def`
- All calls MUST use `await client.method()`
- No sync fallbacks allowed
- Test async performance under load

**Success Criteria:**
- ✅ Zero sync methods remain
- ✅ Zero `import requests` in file
- ✅ All tests pass with async calls
- ✅ 100% async code coverage

---

### 3.3 LangChain Integration Async Migration
**Objective:** Migrate LangChain-based learning agents to async

**Critical File:**
- `agents/learning/qwen_langchain.py` - Custom LangChain LLM wrapper
  - Wraps `QwenLLM` from main_agent
  - Used by learning mode agents
  - Needs async support

**LangChain Async Strategy (Temporary Compromise Only):**

**⚠️ EXCEPTION TO 100% ASYNC RULE:**
LangChain is complex and educational features are critical. We'll use a **temporary** hybrid approach:

1. **Phase 3.3 (Migration Week): Option B - Thread Pool (Temporary)**
   - Keep LangChain synchronous initially
   - Use `asyncio.to_thread()` to run in background (non-blocking)
   - Accepts slightly lower concurrency for learning mode
   - **Reason:** Reduces migration risk for educational features

2. **Phase 8.3 (Post-Migration): Option A - Full Async (Target)**
   - Implement native async LangChain support
   - Extend custom `QwenLLM(LLM)` class with `_acall()` method
   - Remove thread pool, go 100% async
   - **Goal:** Achieve full async stack across entire application

**Timeline:**
- Week 1 (Migration): Thread pool (acceptable compromise)
- Week 2-4 (Post-migration): Native async LangChain
- **Final State:** 100% async, no thread pools, maximum concurrency

**Why This Is OK:**
- Learning mode is lower traffic than main API
- Thread pool is non-blocking (uses asyncio.to_thread)
- Allows focus on critical SSE endpoints first
- Will be removed in Phase 8.3 for true 100% async

**Learning Routes Dependencies:**
- `LearningAgent` and `LearningAgentV3` in `agents/learning/`
- Use LangChain for intelligent question generation
- Must preserve educational features during migration

---

### 3.4 Agent System Async Integration
**Objective:** Make agent system work with async LLM clients

**Files to Update:**
- `agents/main_agent.py` - Main orchestrator (QwenLLM class)
- `agents/core/base_agent.py` - Base class
- All specific agent files (concept_maps, mind_maps, thinking_maps, thinking_tools)

**Key Changes:**

1. **Base Agent Class:**
   - Add async support to base methods
   - Allow both sync and async LLM calls (transition period)
   - Update error handling for async exceptions

2. **Agent Methods:**
   - Make `generate()` methods `async def`
   - Make `enhance()` methods `async def`
   - Use `await` for all LLM client calls
   - Keep all validation and processing logic

3. **Diagram Validation:**
   - Keep synchronous (no I/O, pure logic)
   - Can be called from async context without changes

**Testing Requirements:**
- Verify all diagram types still generate correctly
- Verify enhancement features work
- Verify error messages preserved

---

### 3.5 JavaScript Cache System Integration
**Objective:** Preserve JavaScript lazy loading cache system in FastAPI

**Current Implementation:**
- `static/js/lazy_cache_manager.py` - Lazy loading cache with intelligent caching
- `static/js/modular_cache_python.py` - Modular cache for code splitting
- Cache endpoints: `/cache/status`, `/cache/performance`, `/cache/modular`
- Caches JavaScript files to reduce file I/O overhead (2-5s → instant)

**Key Features to Preserve:**
- Lazy loading strategy (load on demand, not at startup)
- TTL-based caching (3600 seconds = 1 hour)
- Memory limits and cleanup
- Cache hit rate tracking
- Performance metrics (average load time, total requests, etc.)

**Migration Strategy:**
1. Cache system is file-based Python, not Flask-specific
2. Should work with FastAPI without changes
3. Test cache initialization at startup
4. Verify cache endpoints return same data
5. Keep all performance metrics

**Testing Required:**
- Verify cache initialization doesn't block server startup
- Test cache endpoints under load
- Verify JavaScript files load correctly
- Monitor memory usage with cache

---

### 3.6 Browser Manager Async Integration
**Objective:** Make Playwright PNG export work with async

**Current Implementation:**
- File: `browser_manager.py`
- Uses: Playwright for browser automation
- Called from: `/api/export_png` endpoint

**Target Implementation:**

**Key Changes:**
1. Playwright already supports async: `async with async_playwright()`
2. Make `export_png()` function `async def`
3. Use async Playwright context manager
4. Use `await page.goto()`, `await page.screenshot()`, etc.
5. Keep all image processing logic
6. Keep cleanup logic

**Performance Benefit:**
- Non-blocking during browser operations
- Multiple exports can run concurrently
- Better resource utilization

---

## Phase 4: Configuration and Settings Migration (Day 3)

### 4.0 Settings Module Async Compatibility
**Objective:** Ensure settings.py works with async context

**Current Implementation:**
- `settings.py` - Configuration with caching mechanism
- Caches environment variables for 30 seconds to prevent race conditions
- Property-based access for real-time updates

**Key Features:**
- `Config._get_cached_value()` - Internal caching
- 30-second cache duration
- Properties for all config values (QWEN_API_KEY, DEEPSEEK_MODEL, etc.)

**Migration Considerations:**
1. Current caching is synchronous (no locks needed - single threaded)
2. FastAPI with multiple workers needs thread-safe caching
3. Consider using `@lru_cache` for immutable config values
4. Or use `asyncio.Lock` for mutable cache

**Recommended Approach:**
- Keep current implementation (works with FastAPI)
- Config reads are fast and don't need async
- Can be called from async context without issues
- Monitor for race conditions under load

---

## Phase 5: Server Configuration (Day 3)

### 5.1 Uvicorn Server Setup
**Objective:** Replace Waitress with Uvicorn

**Create `uvicorn.conf.py`:**

**Configuration Parameters:**
- `host` - Same as Waitress: `0.0.0.0`
- `port` - Same as Waitress: `9527`
- `workers` - CPU cores × 2-4 (e.g., 4 workers)
- `worker_class` - Not needed (Uvicorn uses async by default)
- `timeout_keep_alive` - 300 seconds for SSE
- `log_level` - `info`
- `access_log` - Enable
- `reload` - False (production), True (development)

**Platform Detection:**
- Windows: Use standard Uvicorn (no uvloop)
- Ubuntu: Use Uvicorn with uvloop (better performance)
- Auto-detect in `run_server.py`

---

### 5.2 Server Launcher Update
**Objective:** Update `run_server.py` to use Uvicorn

**New Structure:**

**Key Changes:**
1. Add `run_uvicorn()` function
2. Replace Waitress import with Uvicorn import
3. Change from `serve(app, ...)` to `uvicorn.run("main:app", ...)`
4. Load config from `uvicorn.conf.py` instead of `waitress.conf.py`
5. Keep banner display
6. Keep logs directory creation
7. Keep error handling

**Uvicorn Command Pattern:**
```python
uvicorn.run(
    "main:app",  # Points to FastAPI app in main.py
    host=host,
    port=port,
    workers=workers,
    timeout_keep_alive=timeout,
    log_level="info"
)
```

**Development vs Production:**
- Development: `workers=1, reload=True` (auto-reload on file changes)
- Production: `workers=4, reload=False`
- Control via environment variable: `UVICORN_ENV`

**Platform Compatibility:**
- Same command works on Windows and Ubuntu
- Auto-detects OS capabilities (uvloop on Linux only)
- No platform-specific code needed

---

### 5.3 Environment Configuration
**Objective:** Update environment variables for FastAPI

**Update `.env` and `env.example`:**

**New Variables:**
- `FASTAPI_ENV` - development/production
- `UVICORN_WORKERS` - Number of workers (default: 4)
- `UVICORN_RELOAD` - Auto-reload for dev (default: false)

**Preserve Existing:**
- All LLM API keys (QWEN_API_KEY, DEEPSEEK_API_KEY, etc.)
- DIFY_API_KEY, DIFY_API_URL
- LOG_LEVEL
- PORT

**Remove (No Longer Needed):**
- Waitress-specific variables (if any)

---

## Phase 6: Testing Strategy (Day 4)

### 6.1 Unit Testing
**Objective:** Verify individual components work

**Test Async Functions:**
- Create `tests/test_async_clients.py`
- Test async Dify client methods
- Test async LLM client methods
- Use `pytest-asyncio` for async test support

**Test Pydantic Models:**
- Create `tests/test_models.py`
- Test validation rules
- Test default values
- Test error cases

**Test Endpoints:**
- Create `tests/test_routes.py`
- Use FastAPI TestClient (supports async)
- Test each endpoint individually
- Verify request/response formats

---

### 6.2 Integration Testing
**Objective:** Verify end-to-end workflows

**Critical Workflows to Test:**

1. **Diagram Generation Flow:**
   - User submits prompt → LLM generates → Diagram renders
   - Test all diagram types
   - Test all LLM options (Qwen, DeepSeek, Kimi)
   - Verify JSON structure

2. **MindMate AI SSE Flow:**
   - User sends message → Dify streams response → Frontend receives chunks
   - Test conversation continuity
   - Test error handling mid-stream
   - Test connection timeout
   - Test concurrent connections

3. **PNG Export Flow:**
   - Diagram data → Playwright renders → PNG generated
   - Test various diagram sizes
   - Test error cases (invalid data)

4. **Session Management:**
   - Create session → Use session → Cleanup
   - Test session isolation
   - Test session timeout

---

### 6.3 Load Testing
**Objective:** Verify concurrency targets met

**SSE Concurrency Test:**
- Simulate 100+ concurrent MindMate AI connections
- Use tool like `locust` or `hey`
- Verify all connections receive data
- Verify no connection drops
- Measure response times
- Monitor memory usage

**Target Metrics:**
- Support 100 concurrent SSE connections minimum
- Support 500+ concurrent SSE connections ideal
- Response time < 2 seconds for first chunk
- Memory usage < 2GB with 100 connections

**Comparison Test:**
- Run same test on old Flask/Waitress version
- Compare performance metrics
- Document improvement

---

### 6.4 LangChain Learning Mode Testing
**Objective:** Verify learning mode still works with async migration

**Learning Mode Features to Test:**
1. **Session Management:**
   - Start learning session with knocked-out nodes
   - Maintain session state across requests
   - Session timeout and cleanup

2. **AI Question Generation:**
   - Generate questions using LangChain
   - Verify question quality and relevance
   - Test both v1 and v3 learning agents

3. **Answer Validation:**
   - Submit student answers
   - Get AI feedback
   - Hint generation

4. **Performance:**
   - Question generation time
   - Concurrent learning sessions
   - Memory usage per session

**Test Cases:**
- 10+ students in simultaneous learning sessions
- Different diagram types (bubble_map, concept_map, etc.)
- Both English and Chinese language modes
- Error handling for invalid answers

---

### 6.5 Cross-Platform Testing
**Objective:** Verify Windows + Ubuntu compatibility

**Windows 11 Testing:**
- Run full test suite
- Start server: `python run_server.py`
- Verify all features work
- Check logs for any OS-specific errors
- Test SSE with browser DevTools

**Ubuntu Testing:**
- Deploy to Ubuntu server or VM
- Run full test suite
- Start server: `python run_server.py`
- Verify uvloop is being used (check logs)
- Verify performance better than Windows
- Test under load

**Both Platforms:**
- Same command works: `python run_server.py`
- Same .env configuration
- Same port (9527)
- Same API behavior

---

## Phase 7: Deployment and Rollout (Day 5)

### 7.1 Documentation Updates
**Objective:** Update all docs for FastAPI

**Files to Update:**

1. **README.md:**
   - Update technology stack section
   - Update installation instructions
   - Update API documentation
   - Add FastAPI-specific notes
   - Keep Windows/Ubuntu instructions

2. **API_REFERENCE.md:**
   - Update endpoint documentation
   - Add Pydantic model schemas
   - Add auto-generated OpenAPI link
   - Document request/response formats

3. **requirements.txt:**
   - **Add FastAPI dependencies:**
     - `fastapi>=0.104.0`
     - `uvicorn[standard]>=0.24.0`
     - `aiohttp>=3.9.0`
     - `python-multipart>=0.0.6`
   - **Remove after migration complete:**
     - `Flask>=3.1.1`
     - `Werkzeug>=3.1.0`
     - `flask-cors>=6.0.0`
     - `waitress>=3.0.0` ← **Replace with Uvicorn**
   - Add version pins for stability

4. **env.example:**
   - Add new environment variables
   - Update comments
   - Document FastAPI-specific settings

5. **Create MIGRATION_NOTES.md:**
   - Document breaking changes
   - List new features
   - API compatibility notes
   - Upgrade instructions for users

---

### 7.2 Gradual Rollout Strategy
**Objective:** Minimize risk during deployment

**Option A: Feature Flag Approach (Recommended)**

**Phase 7.2.1: Parallel Deployment**
- Keep Flask app as `app_flask.py`
- Deploy FastAPI as `main.py`
- Use environment variable to choose: `USE_FASTAPI=true/false`
- Run both in parallel on different ports temporarily
- Gradually route traffic from Flask to FastAPI

**Phase 7.2.2: Canary Testing**
- Route 10% of users to FastAPI
- Monitor error rates
- Compare performance metrics
- If stable, increase to 50%
- If issues, roll back to Flask

**Phase 7.2.3: Full Cutover**
- Route 100% to FastAPI
- Keep Flask as backup for 1 week
- After stability confirmed, remove Flask code

**Option B: Hard Cutover (Faster but Riskier)**
- Full deployment in one step
- Thorough testing beforehand
- Have rollback plan ready
- Schedule during low-traffic window

---

### 7.3 Rollback Plan
**Objective:** Quick recovery if issues arise

**Rollback Procedure:**

1. **Immediate Rollback (< 5 minutes):**
   - Git checkout previous commit: `git checkout v3.4.4-pre-fastapi`
   - Restart server: `python run_server.py`
   - Server runs Flask/Waitress version

2. **Keep Flask Version Available:**
   - Tag FastAPI version: `git tag v4.0.0-fastapi`
   - Keep `v3.4.4-pre-fastapi` tag accessible
   - Document rollback command in operations guide

3. **Database/State Rollback:**
   - If any database schema changes, have migration down scripts
   - Document state restoration procedure

**Monitoring After Deployment:**
- Watch error logs for 24 hours
- Monitor SSE connection counts
- Check response times
- Monitor memory usage
- Have on-call person ready

---

### 7.4 Performance Monitoring
**Objective:** Validate migration success

**Metrics to Track:**

1. **Concurrency Metrics:**
   - Current concurrent SSE connections
   - Peak concurrent connections reached
   - Connection duration average
   - Connection failures/errors

2. **Performance Metrics:**
   - API endpoint response times (p50, p95, p99)
   - SSE first chunk time
   - PNG export completion time
   - Memory usage per connection
   - CPU usage under load

3. **Error Metrics:**
   - 4xx error rate
   - 5xx error rate
   - SSE disconnection rate
   - Timeout rate

**Monitoring Tools:**
- Built-in logging (file-based)
- Optional: Prometheus + Grafana
- Optional: Sentry for error tracking
- Server metrics: htop, iostat

**Success Criteria:**
- 100+ concurrent SSE connections supported
- < 1% error rate
- Response times similar or better than Flask
- No memory leaks over 24 hours
- Clean logs (no unexpected errors)

---

## Phase 8: Optimization and Cleanup (Post-Migration)

### 8.1 Code Cleanup
**Objective:** Remove Flask remnants

**After Stable for 1 Week:**
- Remove `app_flask.py` (if kept as backup)
- Remove `waitress.conf.py` (replaced by `uvicorn.conf.py`)
- **Remove from `requirements.txt`:**
  - `Flask>=3.1.1`
  - `Werkzeug>=3.1.0`
  - `flask-cors>=6.0.0`
  - `waitress>=3.0.0` ← **Replaced by Uvicorn**
  - `requests>=2.31.0` ← **MUST DELETE - 100% replaced by aiohttp**
- **Verify 100% Async:**
  - Run: `grep -r "import requests" . --exclude-dir=venv --exclude-dir=.git`
  - Expected result: ZERO matches (except maybe test mocks)
  - If ANY found → migration incomplete, fix before cleanup
- Remove unused imports
- Remove feature flags
- Update all documentation references

**100% Async Validation Checklist:**
- [ ] No `import requests` anywhere in source code
- [ ] All HTTP calls use aiohttp
- [ ] All LLM calls are async
- [ ] All SSE endpoints use async generators
- [ ] No blocking I/O in any route handler
- [ ] All database calls async (if DB added)
- [ ] Thread pool only for LangChain (temporary, removed in Phase 8.3)

---

### 8.2 Performance Optimization
**Objective:** Maximize FastAPI benefits

**Optimizations to Consider:**

1. **Connection Pooling:**
   - Configure aiohttp ClientSession with connection pools
   - Reuse sessions across requests
   - Tune pool size based on load

2. **Caching:**
   - Add caching for LLM responses (if appropriate)
   - Cache static diagram templates
   - Use FastAPI dependency caching

3. **Worker Tuning:**
   - Adjust Uvicorn worker count based on CPU cores
   - Monitor worker memory usage
   - Restart workers periodically if needed

4. **Async Optimization:**
   - Profile async functions for bottlenecks
   - Use `asyncio.gather()` for parallel operations
   - Optimize database queries (if added)

---

### 8.3 LangChain Full Async Migration (Final 100% Async Step)
**Objective:** Remove last hybrid code, achieve true 100% async stack

**This is the FINAL step to complete async migration:**

**Current State (After Phase 3):**
- LangChain uses thread pool (`asyncio.to_thread()`)
- Learning mode is non-blocking but not truly async
- Only remaining non-async code in the system

**Target State (100% Async):**
1. **Implement Native Async LangChain:**
   - Add `_acall()` method to custom `QwenLLM` class
   - Use LangChain's async agents (`agenerate()`, `acall()`)
   - Make all learning routes pure async

2. **Remove Thread Pool Completely:**
   - Delete `asyncio.to_thread()` wrappers
   - Direct async LangChain calls
   - No background threads anywhere

3. **Update Learning Routes:**
   - Change from `await asyncio.to_thread(langchain.call, ...)`
   - To: `await langchain.acall(...)`
   - Pure async generators for streaming

**Expected Benefits:**
- ✅ Better concurrency for learning mode
- ✅ Lower memory usage (no threads)
- ✅ Faster question generation
- ✅ **100% async stack achieved** - no exceptions!

**Validation:**
- [ ] No `asyncio.to_thread()` calls in codebase
- [ ] All LangChain calls are native async
- [ ] Learning mode tests pass
- [ ] Concurrent learning sessions scale linearly
- [ ] **TRUE 100% ASYNC ACHIEVED** 🎉

**Success Metric:**
- **0 blocking calls** in entire application
- **0 thread pools** (except Uvicorn workers)
- **4,000+ concurrent SSE connections** across all features

---

### 8.4 API Versioning Strategy
**Objective:** Plan for future changes

**Implement API Versioning:**
- Add `/v1/` prefix to all routes
- Keep `/api/` as alias for backwards compatibility
- Document versioning strategy
- Plan for v2 API if needed

**Auto-Generated Documentation:**
- Enable OpenAPI docs at `/docs` (Swagger UI)
- Enable ReDoc at `/redoc`
- Document all endpoints with descriptions
- Include request/response examples

---

## Migration Checklist

### Pre-Migration ✓
- [ ] Create feature branch: `feature/fastapi-migration`
- [ ] Tag stable version: `v3.4.4-pre-fastapi`
- [ ] Install dependencies: FastAPI, Uvicorn, aiohttp
- [ ] Document current API behavior
- [ ] Create route inventory
- [ ] Run baseline tests

### Core Migration ✓
- [ ] Create `main.py` with FastAPI app
- [ ] Create `routers/` package structure
- [ ] Migrate all routes to `routers/api.py`
- [ ] Migrate template routes to `routers/pages.py`
- [ ] Create Pydantic models in `models/`
- [ ] Configure CORS middleware
- [ ] Configure logging middleware
- [ ] Set up static files mounting
- [ ] Set up Jinja2 templates

### Async Migration ✓
- [ ] Create `async_dify_client.py`
- [ ] Create `async_llm_clients.py`
- [ ] Update agent system for async
- [ ] Update browser manager for async
- [ ] Make all route handlers `async def`
- [ ] Replace all `requests` calls with `aiohttp`
- [ ] Test SSE streaming works

### Server Setup ✓
- [ ] Create `uvicorn.conf.py`
- [ ] Update `run_server.py` for Uvicorn
- [ ] Test on Windows 11
- [ ] Test on Ubuntu
- [ ] Verify same command works on both

### Testing ✓
- [ ] Write unit tests for async functions
- [ ] Write integration tests
- [ ] Run load tests (100+ concurrent SSE)
- [ ] Cross-platform testing
- [ ] Performance comparison with Flask

### Deployment ✓
- [ ] Update README.md
- [ ] Update API_REFERENCE.md
- [ ] Update requirements.txt
- [ ] Create MIGRATION_NOTES.md
- [ ] Tag FastAPI version: `v4.0.0-fastapi`
- [ ] Deploy to production
- [ ] Monitor for 24 hours
- [ ] Measure success metrics

### Cleanup ✓
- [ ] Remove Flask dependencies
- [ ] Remove old code
- [ ] Update changelog
- [ ] Archive migration documents

---

## Risk Mitigation

### High-Risk Areas

1. **SSE Streaming Breaking:**
   - **Risk:** MindMate AI stops working
   - **Mitigation:** Extensive SSE testing, keep Flask version ready
   - **Rollback:** Immediate revert to Flask

2. **Performance Regression:**
   - **Risk:** Slower than Flask despite async
   - **Mitigation:** Load testing before deployment, profiling
   - **Rollback:** Revert and investigate

3. **Platform Incompatibility:**
   - **Risk:** Works on Windows but breaks on Ubuntu
   - **Mitigation:** Test on both platforms before deployment
   - **Rollback:** Platform-specific deployment

4. **Memory Leaks:**
   - **Risk:** Async code causes memory growth
   - **Mitigation:** Memory profiling, long-running tests
   - **Rollback:** Worker restart script

### Medium-Risk Areas

5. **Third-Party API Compatibility:**
   - **Risk:** Async HTTP breaks Dify/LLM integrations
   - **Mitigation:** Test with real APIs early
   - **Rollback:** Keep sync client as fallback

6. **Browser Automation Issues:**
   - **Risk:** Async Playwright breaks PNG export
   - **Mitigation:** Test PNG export thoroughly
   - **Rollback:** Use sync Playwright in background thread

---

## Success Metrics

### Must-Have (Required for Migration Success)
- ✅ Support 100+ concurrent SSE connections
- ✅ All existing features work (diagram generation, export, etc.)
- ✅ Same command works on Windows 11 and Ubuntu
- ✅ Error rate < 1%
- ✅ No critical bugs in 48 hours post-deployment

### Nice-to-Have (Optimization Targets)
- ⭐ Support 500+ concurrent SSE connections
- ⭐ Faster response times than Flask
- ⭐ Lower memory usage than Flask
- ⭐ Auto-generated API docs
- ⭐ Better developer experience

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|-----------------|
| **Phase 1: Preparation** | 4 hours | Branch, deps, docs |
| **Phase 2: Core Migration** | 1.5 days | FastAPI app, routes, models, 3 blueprints |
| **Phase 3: Async Rewrite** | 1.5 days | Async clients, agents, LangChain |
| **Phase 4: Config Migration** | 0.5 days | Settings, cache system |
| **Phase 5: Server Setup** | 0.5 days | Uvicorn config, testing |
| **Phase 6: Testing** | 1 day | Unit, integration, load, learning mode |
| **Phase 7: Deployment** | 0.5 days | Deploy, monitor |
| **Phase 8: Cleanup** | Ongoing | Optimize, LangChain async, clean up |
| **Total** | **5-6 days** | Production-ready FastAPI app |

---

## Key Files Reference

### Files to Create
- `main.py` - FastAPI app entry point
- `routers/__init__.py` - Router package
- `routers/api.py` - API routes
- `routers/pages.py` - Template routes
- `models/__init__.py` - Pydantic models package
- `models/requests.py` - Request models
- `models/responses.py` - Response models
- `async_dify_client.py` - Async Dify client
- `async_llm_clients.py` - Async LLM clients
- `uvicorn.conf.py` - Uvicorn configuration
- `MIGRATION_NOTES.md` - Migration documentation

### Files to Modify
- `run_server.py` - Server launcher (add Uvicorn support)
- `requirements.txt` - Add FastAPI dependencies
- `env.example` - Add FastAPI environment variables
- `.env` - Configure for FastAPI
- `README.md` - Update for FastAPI
- `API_REFERENCE.md` - Update API docs
- All agent files - Add async support
- `browser_manager.py` - Make async
- `agents/learning/qwen_langchain.py` - Add async LangChain support
- `settings.py` - Verify thread safety for multi-worker
- `static/js/lazy_cache_manager.py` - Test with FastAPI
- `static/js/modular_cache_python.py` - Test with FastAPI

### Files to Eventually Remove (After Stable)
- `app.py` - Replaced by `main.py`
- `api_routes.py` - Replaced by `routers/api.py`
- `web_pages.py` - Replaced by `routers/pages.py`
- `api/routes/learning_routes.py` - Replaced by `routers/learning.py`
- `waitress.conf.py` - Replaced by `uvicorn.conf.py`
- `dify_client.py` - Replaced by `async_dify_client.py`
- `llm_clients.py` - Replaced by `async_llm_clients.py`

---

## Additional Resources

### FastAPI Documentation
- Official docs: https://fastapi.tiangolo.com
- Async programming: https://fastapi.tiangolo.com/async/
- SSE example: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse

### Testing Resources
- pytest-asyncio: https://github.com/pytest-dev/pytest-asyncio
- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/
- Load testing with locust: https://locust.io

### Deployment Guides
- Uvicorn deployment: https://www.uvicorn.org/deployment/
- FastAPI in production: https://fastapi.tiangolo.com/deployment/

---

## Notes for Future Cursor Sessions

When executing this migration plan:

1. **Start with Phase 1** - Don't skip preparation
2. **Test frequently** - After each file migration, test it works
3. **Keep Flask running** - Don't delete until FastAPI is stable
4. **Use git liberally** - Commit after each working phase
5. **Reference this doc** - Follow the checklist, don't improvise
6. **Test on both platforms** - Windows and Ubuntu, every phase
7. **Monitor logs** - Watch for errors, fix immediately
8. **Ask for help** - If stuck, consult FastAPI docs or this plan

**Critical Success Factor:** The async rewrite is essential. Don't migrate to FastAPI without also migrating HTTP clients to async. Otherwise, you won't get the concurrency benefits.

**Expected Outcome:** A FastAPI application that handles 100-4,000 concurrent SSE connections, works identically on Windows 11 and Ubuntu, and launches with the same simple command: `python run_server.py`

---

## Final Code Review Checklist

### ✅ All Files Verified - Complete Inventory

#### Route Files (Total: 33 routes across 3 blueprints)
| File | Routes | Status | Priority | Notes |
|------|--------|--------|----------|-------|
| `api_routes.py` | ~17 routes | ❌ Sync | **CRITICAL** | Includes SSE `/ai_assistant/stream` |
| `web_pages.py` | 11 routes | ❌ Sync | Low | Simple templates, no I/O |
| `api/routes/learning_routes.py` | 4 routes | ❌ Sync | High | LangChain integration |
| `app.py` (direct) | 3 routes | ❌ Sync | Low | Cache endpoints, lightweight |

**All 33 routes accounted for ✅**

---

#### HTTP Client Files (MUST migrate to aiohttp)
| File | Method | Library Used | Status | Action |
|------|--------|--------------|--------|--------|
| `dify_client.py` | `stream_chat()` | `requests.post(stream=True)` | ❌ Blocking | **CREATE** `async_dify_client.py` |
| `llm_clients.py` | `chat_completion()` (sync) | `requests.post()` | ❌ Blocking | **DELETE** sync methods |
| `llm_clients.py` | `async def chat_completion()` | `aiohttp` | ✅ Async | **KEEP** async methods |
| `agents/main_agent.py` | `QwenLLM._call()` | `requests.post()` | ❌ Blocking | **REWRITE** to use async llm_clients |
| `app.py` | `get_wan_ip()` | `requests.get()` | ⚠️ Low Priority | Optional, startup only |

**Critical finding:** 4 files using `requests` for core functionality  
**Migration path:** DELETE all `requests` imports, replace with `aiohttp` 100%

---

#### Agent Files (ALL need async conversion)
| File | Key Methods | Current State | Action |
|------|-------------|---------------|--------|
| `agents/main_agent.py` | `generate_graph_spec()`, `generate_concept_map_*()` | ❌ Sync | **CONVERT** to `async def` |
| `agents/main_agent.py` | `QwenLLM._call()` | ❌ Uses `requests` | **REPLACE** with async LLM clients |
| `agents/main_agent.py` | `ThreadPoolExecutor` (line 982) | ⚠️ Threads | **REPLACE** with `asyncio.gather()` |
| `agents/learning/learning_agent.py` | All methods | ❌ Sync (LangChain) | **WRAP** in `asyncio.to_thread()` initially |
| `agents/learning/learning_agent_v3.py` | All methods | ❌ Sync (LangChain) | **WRAP** in `asyncio.to_thread()` initially |
| All other agent files | `generate_graph()` | ❌ Sync | **CONVERT** to `async def` |

**Total agent files:** ~20+ (all in `agents/` directory)

---

#### Already Async Files (No changes needed) ✅
| File | Status | Notes |
|------|--------|-------|
| `browser_manager.py` | ✅ 100% Async | Uses `async_playwright`, `async __aenter__`, `async __aexit__` |
| `llm_clients.py` (async methods) | ✅ Partial Async | Keep async methods, delete sync methods |

---

#### Configuration & Utilities (Async-safe, no changes needed) ✅
| File | Status | Notes |
|------|--------|-------|
| `settings.py` | ✅ Sync (OK) | Config reads are fast, no I/O blocking |
| `static/js/lazy_cache_manager.py` | ✅ File-based | Not Flask-specific, should work as-is |
| `static/js/modular_cache_python.py` | ✅ File-based | Not Flask-specific, should work as-is |

---

### 🔍 Line-by-Line Critical Code Patterns

#### Pattern 1: `requests` Library (MUST DELETE ALL)
**Locations found (8 files total):**
```bash
# Run this command to verify NO requests imports remain after migration:
grep -r "import requests" . --exclude-dir=venv --exclude-dir=.git
```

**Expected result after Phase 8.1:** ZERO matches (except maybe test files)

**Critical files:**
1. `dify_client.py` line 9: `import requests`
2. `llm_clients.py` line 259: `import requests` (inside sync method)
3. `llm_clients.py` line 358: `import requests` (inside sync method)
4. `agents/main_agent.py` line 31: `import requests`
5. `app.py` line 645: `import requests` (inside `get_wan_ip()`)

**Migration action:** Replace ALL with `aiohttp` or delete (for `get_wan_ip()`, acceptable to leave as startup-only utility)

---

#### Pattern 2: Synchronous LLM Calls (MUST CONVERT)
**Example from `agents/main_agent.py` lines 324-329:**
```python
resp = requests.post(
    config.QWEN_API_URL,
    headers=headers,
    json=data
)
```

**After migration (use async llm_clients):**
```python
# Instead of direct requests, use async llm_clients
from llm_clients import qwen_client_generation
result = await qwen_client_generation.chat_completion(messages, temperature, max_tokens)
```

---

#### Pattern 3: ThreadPoolExecutor (REPLACE with asyncio.gather)
**Example from `agents/main_agent.py` lines 982-1027:**
```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(fetch_parts, k) for k in keys]
    for fut in as_completed(futures):
        k, plist = fut.result()
        parts_results[k] = plist
```

**After migration:**
```python
# Use asyncio.gather for parallel async operations
parts_results = {}
async_tasks = [fetch_parts_async(k) for k in keys]
results = await asyncio.gather(*async_tasks)
for k, plist in results:
    parts_results[k] = plist
```

**Performance benefit:** No thread overhead, true async concurrency

---

#### Pattern 4: Flask Route → FastAPI Route
**Example from `api_routes.py`:**
```python
@api.route('/generate', methods=['POST'])
def generate_graph():
    data = request.json
    # ... processing ...
    return jsonify(result)
```

**After migration:**
```python
@router.post('/generate', response_model=GenerateResponse)
async def generate_graph(req: GenerateRequest):
    # ... async processing ...
    return result  # Pydantic model, auto-serialized
```

---

#### Pattern 5: SSE Streaming (CRITICAL - Most Complex)
**Example from `api_routes.py` lines 2837-2920:**
```python
def generate():
    for chunk in dify_client.stream_chat(message, user_id):  # BLOCKS!
        yield f"data: {json.dumps(chunk)}\n\n"

return Response(stream_with_context(generate()), 
                mimetype='text/event-stream')
```

**After migration:**
```python
async def generate():
    async for chunk in async_dify_client.stream_chat(message, user_id):  # ASYNC!
        yield f"data: {json.dumps(chunk)}\n\n"

return StreamingResponse(generate(), media_type='text/event-stream')
```

**Why this matters:** This is THE bottleneck preventing 100+ concurrent SSE connections

---

### 📊 Migration Verification Matrix

#### Phase-by-Phase Verification Commands

**Phase 2 Verification (Core Migration):**
```bash
# Verify FastAPI app exists and imports correctly
python -c "from main import app; print('FastAPI app loaded successfully')"

# Verify all routers registered
python -c "from main import app; print([r.path for r in app.routes])"
```

**Phase 3 Verification (Async Migration):**
```bash
# CRITICAL: Verify NO requests library in production code
grep -r "import requests" --exclude-dir=venv --exclude-dir=.git --exclude-dir=test .

# Expected: ZERO results (or only in test files)

# Verify aiohttp is used instead
grep -r "import aiohttp" --exclude-dir=venv --exclude-dir=.git .

# Expected: At least 3 files (dify_client, llm_clients, and any new async helpers)
```

**Phase 5 Verification (Server Configuration):**
```bash
# Verify Uvicorn can start the app
uvicorn main:app --host 0.0.0.0 --port 9527 --workers 1 --log-level info

# Expected: Server starts without errors, logs show "Application startup complete"
```

**Phase 6 Verification (Load Testing):**
```bash
# Test 100 concurrent SSE connections (should succeed after migration)
python test_sse_load.py --connections 100 --duration 60

# Expected: All connections maintained, no timeouts, memory < 2GB
```

**Phase 8.1 Verification (100% Async Cleanup):**
```bash
# FINAL VERIFICATION - NO requests library anywhere
grep -r "import requests" . --exclude-dir=venv --exclude-dir=.git --exclude-dir=test

# Expected: ZERO results

# NO sync HTTP calls anywhere
grep -r "requests\.post\|requests\.get" . --exclude-dir=venv --exclude-dir=.git --exclude-dir=test

# Expected: ZERO results

# Verify all routes are async
grep -r "@router\." routers/ | grep "def " | grep -v "async def"

# Expected: ZERO results (all route handlers should be "async def")
```

---

### 🎯 Success Metrics - Quantified

| Metric | Current (Flask+Waitress) | Target (FastAPI+Uvicorn) | How to Measure |
|--------|--------------------------|--------------------------|----------------|
| **Concurrent SSE** | 6-100 connections | 100+ (4,000 ideal) | Load test with `locust` or custom script |
| **Memory per connection** | ~8-10 MB (thread-based) | ~2 MB (async) | Monitor with `psutil` during load test |
| **Response time (first SSE chunk)** | ~500-1000ms | < 500ms | Measure with browser DevTools Network tab |
| **requests library usage** | 8 files | **0 files** | `grep -r "import requests" .` |
| **Async route coverage** | 0% (0/33 routes) | **100% (33/33 routes)** | Count async routes in routers/ |
| **API response time (p95)** | Baseline TBD | < 2x baseline | Apache Bench or Locust |
| **Error rate** | Baseline TBD | < 1% | Monitor logs and `/status` endpoint |

---

### ⚠️ Final Pre-Migration Warnings

1. **DO NOT skip the cleanup phase (Phase 8.1)**
   - Leaving `requests` library in code defeats the purpose
   - Hybrid sync/async code is worse than pure sync
   - Must achieve 100% async to hit target metrics

2. **DO NOT mix sync and async HTTP clients**
   - If ANY code still uses `requests`, the migration is incomplete
   - Run verification commands BEFORE marking phases complete

3. **DO NOT deploy without load testing**
   - Must verify 100+ concurrent SSE connections work
   - Must verify memory usage is acceptable
   - Must verify no connection drops under load

4. **DO NOT ignore LangChain async migration (Phase 8.3)**
   - Thread pool is a temporary compromise
   - Must complete native async LangChain for true 100% async
   - Learning mode performance depends on this

5. **DO NOT forget to update requirements.txt**
   - Must remove: `Flask`, `Werkzeug`, `flask-cors`, `waitress`, **`requests`**
   - Must add: `fastapi`, `uvicorn[standard]`, `aiohttp`, `python-multipart`
   - Verify: `pip list | grep -E "flask|waitress|requests"` returns ZERO after Phase 8

---

### 📝 Final Execution Notes

**For Cursor AI Assistant:**

When executing this migration plan:

1. **Read this checklist FIRST** before starting each phase
2. **Verify each file** in the inventory matches the described state
3. **Run verification commands** after each phase
4. **Do NOT skip phases** - they build on each other
5. **Reference line numbers** from this review when making changes
6. **Test incrementally** - don't change 10 files then test, change 1 file and test
7. **Keep Flask running** until FastAPI is fully validated
8. **Git commit after each working phase** - enables easy rollback
9. **Monitor metrics** throughout migration to catch regressions early
10. **Ask for clarification** if any step is ambiguous

**Expected timeline with verification:**
- Phase 1: 4-6 hours (thorough analysis)
- Phase 2: 2 days (careful route migration + testing)
- Phase 3: 2 days (critical async rewrite + testing)
- Phase 4: 4 hours (config verification)
- Phase 5: 4 hours (server testing both platforms)
- Phase 6: 1 day (comprehensive testing)
- Phase 7: 4 hours (deployment + monitoring)
- Phase 8: 1-2 days (cleanup + final async migration)

**Total: 6-7 days** with thorough verification at each step

---

---

## 📋 Quick Reference Commands

### Essential Verification Commands (Copy-Paste Ready)

**Check for requests library (MUST be ZERO after Phase 8.1):**
```bash
grep -r "import requests" . --exclude-dir=venv --exclude-dir=.git --exclude-dir=test
```

**Verify all routes are async:**
```bash
grep -r "@router\." routers/ | grep "def " | grep -v "async def"
# Expected: ZERO results
```

**Test FastAPI app startup:**
```bash
python -c "from main import app; print('FastAPI app loaded successfully')"
```

**Run Uvicorn server:**
```bash
uvicorn main:app --host 0.0.0.0 --port 9527 --workers 1 --log-level info
```

**Check installed dependencies:**
```bash
pip list | grep -E "fastapi|uvicorn|aiohttp"  # Should exist
pip list | grep -E "flask|waitress|requests"  # Should NOT exist after Phase 8
```

### Git Commands for Safe Migration

**Create migration branch:**
```bash
git checkout -b feature/fastapi-migration
git tag v3.4.4-pre-fastapi
```

**Commit after each phase:**
```bash
git add .
git commit -m "Phase X: [description] - [status]"
```

**Rollback if needed:**
```bash
git checkout v3.4.4-pre-fastapi
# Or: git reset --hard HEAD~1
```

### Load Testing Commands

**Simple SSE load test:**
```bash
# Create test script first, then run:
python test_sse_load.py --connections 100 --duration 60
```

**Monitor memory usage:**
```bash
# During load test:
watch -n 1 'ps aux | grep uvicorn | grep -v grep'
```

### File Structure Verification

**Count routes in new structure:**
```bash
grep -r "@router\." routers/ | wc -l
# Expected: 33 total routes
```

**Verify no Flask imports in routers:**
```bash
grep -r "from flask import" routers/
# Expected: ZERO results
```

---

## 📌 Critical Reminders for Cursor

### Before Starting Any Phase:
1. ✅ Read the phase description completely
2. ✅ Check current file states match the plan
3. ✅ Have a clean git working directory
4. ✅ Know the rollback command

### During Each Phase:
1. ✅ Make incremental changes (1-2 files at a time)
2. ✅ Test after each file change
3. ✅ Run verification commands immediately
4. ✅ Commit working code frequently

### After Completing Each Phase:
1. ✅ Run ALL verification commands for that phase
2. ✅ Check logs for errors or warnings
3. ✅ Test the application manually
4. ✅ Git commit with descriptive message
5. ✅ Update this document with actual results

### Red Flags (Stop and Debug):
- ❌ ANY `import requests` found after Phase 8.1
- ❌ ANY route handler is `def` instead of `async def`
- ❌ Server won't start or crashes immediately
- ❌ Memory usage grows unbounded during testing
- ❌ SSE connections drop or timeout
- ❌ Cross-platform tests fail

### Success Indicators (Keep Going):
- ✅ All verification commands return expected results
- ✅ Server starts without errors
- ✅ All routes respond correctly
- ✅ SSE streaming works smoothly
- ✅ Memory usage is stable
- ✅ Tests pass on both Windows and Ubuntu

---

**End of Migration Plan**

**Version:** 1.2 (Organized for Cursor Reference)  
**Last Updated:** 2025-10-08  
**Status:** Ready for Execution - All Files Verified  
**Code Review:** Complete ✅  
**Verification Commands:** Included ✅  
**Success Metrics:** Quantified ✅  
**Quick Reference:** Added ✅  
**Organization:** Optimized for AI Assistant ✅

