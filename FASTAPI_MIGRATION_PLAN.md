# MindGraph Flask → FastAPI Migration Plan
## Full Async Rewrite with Uvicorn

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Target:** 100+ concurrent users with SSE support  
**Timeline:** 4-5 days focused development  
**Priority:** High - Required for production scale

---

## Executive Summary

This document outlines the complete migration path from Flask + Waitress to FastAPI + Uvicorn with full async/await support. The migration will enable handling 4,000+ concurrent Server-Sent Events (SSE) connections for the MindMate AI assistant and other real-time features.

### Current State
- **Framework:** Flask 3.1.1 with Blueprint architecture
- **Server:** Waitress 3.0.0 (WSGI, synchronous, thread-based)
- **HTTP Client:** requests library (synchronous, blocking)
- **Routes:** ~20 endpoints (13 in `api_routes.py`, 7 in `app.py`)
- **Templates:** 3 Jinja2 templates
- **Concurrency:** Limited to ~6-100 concurrent SSE connections (thread-limited)
- **Platforms:** Windows 11 (development), Ubuntu (production)

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
# FastAPI Core
fastapi>=0.104.0
uvicorn[standard]>=0.24.0  # Note: [standard] installs without uvloop on Windows

# Async HTTP Client (replaces requests for async calls)
aiohttp>=3.9.0

# ASGI Middleware and Utilities
python-multipart>=0.0.6  # For form data and file uploads
sse-starlette>=1.8.0     # Optional: Better SSE support

# Keep existing dependencies
# (Flask will coexist during migration)
```

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

**All Routes to Convert (~20 total):**
1. `/api/generate` - Generate diagram
2. `/api/enhance` - Enhance diagram
3. `/api/export_png` - PNG export
4. `/api/ai_assistant/stream` - SSE streaming
5. `/api/health` - Health check
6. `/api/status` - System status
7. `/api/session/create` - Session management
8. All other endpoints in `api_routes.py`

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
   - Current: Custom `UnifiedFormatter` in app.py
   - Target: Custom FastAPI middleware that logs requests/responses
   - Preserve same log format: `[HH:MM:SS] LEVEL | Source | Message`
   - Keep color coding for terminal output

3. **Error Handling Middleware**
   - Current: `@app.errorhandler(...)` decorators
   - Target: FastAPI exception handlers
   - Preserve same error response format
   - Keep client-friendly error messages

**New Middleware to Add:**

4. **Request ID Middleware** (Optional but Recommended)
   - Add unique request ID to each request
   - Include in logs for request tracing
   - Useful for debugging SSE issues

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

### 3.2 LLM Clients Async Rewrite
**Objective:** Convert `llm_clients.py` to async

**Current Implementation:**
- File: `llm_clients.py`
- Multiple LLM integrations: Qwen, DeepSeek, Kimi
- Uses: `requests` library for API calls

**Target Implementation:**

**Create `async_llm_clients.py`:**

**Key Changes for Each LLM Client:**

1. **QwenLLMClient:**
   - Make all methods `async def`
   - Replace `requests` with `aiohttp`
   - Use `async with session.post()` for API calls
   - Handle streaming responses with `async for`
   - Preserve retry logic
   - Preserve error handling

2. **DeepSeekLLMClient:**
   - Same async pattern as Qwen
   - Preserve API-specific logic
   - Handle streaming if supported

3. **KimiLLMClient:**
   - Same async pattern
   - Preserve API-specific logic

**Shared Async Utilities:**
- Create async retry decorator
- Create async timeout wrapper
- Create async rate limiting if needed

**Integration Points:**
- All routes calling LLM clients must be `async def`
- Use `await client.generate()` instead of `client.generate()`
- Handle async context managers properly

---

### 3.3 Agent System Async Integration
**Objective:** Make agent system work with async LLM clients

**Files to Update:**
- `agents/main_agent.py` - Main orchestrator
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

### 3.4 Browser Manager Async Integration
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

## Phase 4: Server Configuration (Day 3)

### 4.1 Uvicorn Server Setup
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

### 4.2 Server Launcher Update
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

### 4.3 Environment Configuration
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

## Phase 5: Testing Strategy (Day 4)

### 5.1 Unit Testing
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

### 5.2 Integration Testing
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

### 5.3 Load Testing
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

### 5.4 Cross-Platform Testing
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

## Phase 6: Deployment and Rollout (Day 5)

### 6.1 Documentation Updates
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
   - Add FastAPI dependencies
   - Add aiohttp
   - Add uvicorn
   - Remove Flask dependencies (after full migration)
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

### 6.2 Gradual Rollout Strategy
**Objective:** Minimize risk during deployment

**Option A: Feature Flag Approach (Recommended)**

**Phase 6.2.1: Parallel Deployment**
- Keep Flask app as `app_flask.py`
- Deploy FastAPI as `main.py`
- Use environment variable to choose: `USE_FASTAPI=true/false`
- Run both in parallel on different ports temporarily
- Gradually route traffic from Flask to FastAPI

**Phase 6.2.2: Canary Testing**
- Route 10% of users to FastAPI
- Monitor error rates
- Compare performance metrics
- If stable, increase to 50%
- If issues, roll back to Flask

**Phase 6.2.3: Full Cutover**
- Route 100% to FastAPI
- Keep Flask as backup for 1 week
- After stability confirmed, remove Flask code

**Option B: Hard Cutover (Faster but Riskier)**
- Full deployment in one step
- Thorough testing beforehand
- Have rollback plan ready
- Schedule during low-traffic window

---

### 6.3 Rollback Plan
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

### 6.4 Performance Monitoring
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

## Phase 7: Optimization and Cleanup (Post-Migration)

### 7.1 Code Cleanup
**Objective:** Remove Flask remnants

**After Stable for 1 Week:**
- Remove `app_flask.py` (if kept as backup)
- Remove `waitress.conf.py`
- Remove Flask from `requirements.txt`
- Remove unused imports
- Remove feature flags
- Update all documentation references

---

### 7.2 Performance Optimization
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

### 7.3 API Versioning Strategy
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
| **Phase 2: Core Migration** | 1.5 days | FastAPI app, routes, models |
| **Phase 3: Async Rewrite** | 1.5 days | Async clients, agents |
| **Phase 4: Server Setup** | 0.5 days | Uvicorn config, testing |
| **Phase 5: Testing** | 1 day | Unit, integration, load tests |
| **Phase 6: Deployment** | 0.5 days | Deploy, monitor |
| **Phase 7: Cleanup** | Ongoing | Optimize, clean up |
| **Total** | **5 days** | Production-ready FastAPI app |

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

### Files to Eventually Remove (After Stable)
- `app.py` - Replaced by `main.py`
- `api_routes.py` - Replaced by `routers/api.py`
- `web_pages.py` - Replaced by `routers/pages.py`
- `waitress.conf.py` - Replaced by `uvicorn.conf.py`
- `dify_client.py` - Replaced by `async_dify_client.py`

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

**End of Migration Plan**

**Version:** 1.0  
**Last Updated:** 2025-10-08  
**Status:** Ready for Execution

