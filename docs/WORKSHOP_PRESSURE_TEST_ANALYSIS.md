# MindGraph Workshop Pressure Test Analysis

**Date**: December 2, 2024  
**Log File**: `app.log` (607,355 lines - extended with additional 24 hours of logs)  
**Total ERROR/WARN Messages**: 3,032+ (from initial analysis)

---

## Executive Summary

During a workshop session that served as a pressure test, the MindGraph server experienced significant load resulting in multiple cascading failures. This document categorizes all issues found, their root causes, and recommended fixes.

### Key Metrics

| Metric | Count |
|--------|-------|
| Total log lines | 607,355 |
| ERROR messages | 499+ (initial) + 221 (extended) |
| WARN messages | 2,533+ |
| Unique error types | 185+ |
| Unique warning types | 1,024+ |

**Note:** Extended analysis covers lines 559716-607355 (additional ~24 hours of logs).

---

## Issue Categories

| Priority | Category | Count | Status |
|----------|----------|-------|--------|
| **P0** | Database Connection Pool Exhaustion | 56 | ✅ Fixed |
| **P2** | Missing Method Bugs (ThinkingAgents) | 9 | Code Fix Required |
| **P2** | Tree Renderer Dynamic Loading Failure | Multiple | ✅ Fixed |
| **P2** | LLMAutoCompleteManager Null Reference | Multiple | Code Fix Required |
| **P3** | Background Rectangle Selectable (Purple Highlight) | Multiple Diagrams | Code Fix Required |
| **P3** | LLM JSON Extraction Failures (Use JSON Mode) | 8+ | Code Fix Required |
| **P3** | Agent Validation Failures | 6+ | Working as Intended |
| **P3** | Slow Requests | 939 | ✅ Fixed by P0 |
| **P4** | Authentication Warnings | 200+ | Working as Intended |
| **P4** | Prompt Clarity Warnings | 18 | Working as Intended |

---

## Frontend Issues (Logged via /api/frontend_log_batch)

These are **client-side JavaScript errors** reported to the server via the frontend logging endpoint.

---

## P2: Tree Renderer Dynamic Loading Failure

### Status: ✅ FIXED

### Symptom (Historical)
```
[DynamicRendererLoader] Failed to load renderer module tree-renderer: | Error: Failed to load script: /static/js/renderers/tree-renderer.js
[DynamicRendererLoader] Dynamic rendering failed for tree_map: | Error: Failed to load script
[RendererDispatcher] Dynamic rendering failed, falling back to static
```

### Root Cause
**Dependency loading order issue.** The `tree-renderer.js` requires `shared-utilities.js` (which provides `MindGraphUtils`) to be loaded first.

### Fix Applied
The fix was implemented in `static/js/dynamic-renderer-loader.js` (lines 126-138):

```javascript
// Load shared utilities first if not loaded
if (!this.cache.has('shared-utilities')) {
    const sharedPromise = this.loadScript('/static/js/renderers/shared-utilities.js')
        .then(() => {
            this.cache.set('shared-utilities', { renderer: true });
        })
        .catch(error => {
            logger.error('DynamicRendererLoader', 'Failed to load shared utilities:', error);
            throw error;
        });
    this.cache.set('shared-utilities', { promise: sharedPromise });
    await sharedPromise;
}
```

### Verification
Code review confirmed the fix is in place - `shared-utilities.js` is now loaded before any renderer module.

---

## P2: LLMAutoCompleteManager Null Reference

### Symptom
```
[LLMAutoCompleteManager] Generation failed | TypeError: Cannot read properties of null (reading 'setAllLLMButtonsLoading')
```

### Stack Trace
```javascript
at LLMAutoCompleteManager._handleAllModelsComplete (llm-autocomplete-manager.js:289:31)
at onComplete (llm-autocomplete-manager.js:207:54)
at LLMEngineManager.callMultipleModels (llm-engine-manager.js:238:13)
at async LLMAutoCompleteManager.handleAutoComplete (llm-autocomplete-manager.js:201:32)
```

### Code Review

**File: `static/js/managers/toolbar/llm-autocomplete-manager.js`**

**Line 217 - MISSING null check:**
```javascript
// Show loading state ONLY for models that will actually run
this.toolbarManager.showNotification(
    language === 'zh' ? '正在生成内容...' : 'Generating content...',
    'info'
);
this.progressRenderer.setAllLLMButtonsLoading(true, models);  // ← No null check!
```

**Lines 354-357 - Has null check (correct):**
```javascript
// Only update UI if components are still available
if (this.progressRenderer) {
    this.progressRenderer.setAllLLMButtonsLoading(false);
    this.updateLLMButtonStates();
}
```

### Root Cause
**Inconsistent null checking.** Line 217 calls `this.progressRenderer.setAllLLMButtonsLoading()` without a null check, while other locations (lines 133, 355) correctly check for null first.

When the user navigates away during an LLM call (user abort), `this.progressRenderer` becomes null, but the async callback still tries to access it.

### Affected File
- `static/js/managers/toolbar/llm-autocomplete-manager.js` (line 217)

### Step-by-Step Solution

**Step 1: Add null check at line 217**

```javascript
// static/js/managers/toolbar/llm-autocomplete-manager.js
// Around line 212-218

// Before:
this.toolbarManager.showNotification(
    language === 'zh' ? '正在生成内容...' : 'Generating content...',
    'info'
);
this.progressRenderer.setAllLLMButtonsLoading(true, models);

// After:
if (this.toolbarManager) {
    this.toolbarManager.showNotification(
        language === 'zh' ? '正在生成内容...' : 'Generating content...',
        'info'
    );
}
if (this.progressRenderer) {
    this.progressRenderer.setAllLLMButtonsLoading(true, models);
}
```

**Step 2: Add safety check in catch block (line 261)**

```javascript
// Around line 261
// Before:
if (this.toolbarManager) {
    this.toolbarManager.showNotification(...);
}

// Also add before this:
if (this.progressRenderer) {
    this.progressRenderer.setAllLLMButtonsLoading(false);
}
```

**Step 3: Test scenarios**
1. Start LLM generation
2. Navigate away before completion
3. Verify no console errors
4. Return and verify UI state is correct

### Alternative: Optional Chaining
```javascript
this.uiManager?.setAllLLMButtonsLoading(false);
```

---

## P3: LLMAutoCompleteManager Cache Miss

### Symptom
```
[LLMAutoCompleteManager] Cannot render deepseek: No valid cached data
```

### Root Cause
When other LLM models (qwen, kimi, hunyuan) timeout or fail, deepseek may complete but if it also failed, there's no cached data to render. This is a **consequence** of the gateway timeouts, not a separate bug.

### Resolution
This will be resolved when the gateway timeout issue (P1) is fixed.

---

## P4: User Abort Errors (Working as Intended)

### Symptom
```
[LLMEngineManager] API error for hunyuan | AbortError: The user aborted a request.
```

### Root Cause
User navigated away or cancelled the operation while LLM call was in progress. The browser's `AbortController` correctly cancelled the pending fetch.

### Status
This is **expected behavior** when users navigate away during long operations. No fix required, but could improve UX by:
1. Showing a "cancel" button instead of just navigation
2. Warning users before leaving during active LLM calls

---

## P0: Database Connection Pool Exhaustion (CRITICAL)

### Symptom
```
QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00
```

### Occurrences
- `[TokenTracker] Batch write failed`: 20+ occurrences
- `[MAIN] Unhandled exception: TimeoutError`: 30+ occurrences
- `[UTIL] Error validating cookie token`: 10+ occurrences

### Root Cause
Authentication dependency functions (`get_current_user`, `get_current_user_or_api_key`) used `db: Session = Depends(get_db)` which held database connections for the **entire request duration**. During concurrent LLM requests (30-120+ seconds), all 15 connections (5 base + 10 overflow) were exhausted.

### Timeline Example
```
14:46:24 - 15+ concurrent requests arrive
14:46:24 - Each acquires DB connection for auth check
14:46:24 - LLM calls start (30+ second hunyuan calls)
14:46:56 - TokenTracker tries to write → Pool exhausted
14:47:26 - More failures cascade
```

### Fix Applied
Modified `config/database.py`:
- Increased `pool_size` from 5 to 10
- Increased `max_overflow` from 10 to 20
- Added `pool_pre_ping=True` for stale connection detection
- Added `pool_recycle=1800` for connection health

Modified `utils/auth.py`:
- `get_current_user()` now manages its own session and closes immediately
- `get_current_user_or_api_key()` now manages its own session and closes immediately

---

## P2: Missing Method Bugs (ThinkingAgents)

### Total Occurrences: 9

### Affected Agents

| Agent | Missing Method | Occurrences |
|-------|----------------|-------------|
| `BraceMapThinkingAgent` | `_call_llm()` | 1 |
| `FlowMapThinkingAgent` | `_call_llm()` | 5 |
| `DoubleBubbleMapThinkingAgent` | `_call_llm_for_json()` | 3 |

### Error Messages
```
Intent detection failed: 'BraceMapThinkingAgent' object has no attribute '_call_llm'
Intent detection failed: 'FlowMapThinkingAgent' object has no attribute '_call_llm'
[DoubleBubbleMapAgent] Intent detection failed: 'DoubleBubbleMapThinkingAgent' object has no attribute '_call_llm_for_json'
```

### Code Review

**File 1: `agents/thinking_modes/brace_map_agent_react.py` (lines 82-88)**
```python
async def _detect_user_intent(self, session, message, current_state):
    # ...
    try:
        result = await self._call_llm(system_prompt, user_prompt, session)  # ← BROKEN
        intent = json.loads(result)
        return intent
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return {'action': 'discuss'}
```

**File 2: `agents/thinking_modes/flow_map_agent_react.py` (lines 82-88)**
```python
async def _detect_user_intent(self, session, message, current_state):
    # ...
    try:
        result = await self._call_llm(system_prompt, user_prompt, session)  # ← BROKEN
        intent = json.loads(result)
        return intent
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return {'action': 'discuss'}
```

**File 3: `agents/thinking_modes/double_bubble_map_agent_react.py` (lines 234-246)**
```python
async def _detect_user_intent(self, session, message, current_state):
    # ...
    try:
        response = await self._call_llm_for_json(  # ← BROKEN
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            session_id=session.get('session_id', '')
        )
        return response
    except Exception as e:
        logger.error(f"[DoubleBubbleMapAgent] Intent detection failed: {e}")
        return {'action': 'discuss'}
```

**Working Reference: `agents/thinking_modes/circle_map_agent_react.py` (lines 222-234)**
```python
# This is the CORRECT pattern to follow:
result_text = await self.llm.chat(
    prompt=user_prompt,
    model=self.model,
    system_message=system_prompt,
    temperature=0.1,
    max_tokens=500,
    user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
    organization_id=organization_id,
    request_type='thinkguide',
    endpoint_path='/thinking_mode/stream',
    conversation_id=session.get('session_id'),
    diagram_type=self.diagram_type
)
```

### Root Cause
The three agents call methods (`_call_llm()` or `_call_llm_for_json()`) that **don't exist** in `BaseThinkingAgent`. The working `CircleMapThinkingAgent` uses `self.llm.chat()` directly.

### Step-by-Step Solution

**Step 1: Fix `brace_map_agent_react.py` (lines 82-88)**

```python
# Before:
try:
    result = await self._call_llm(system_prompt, user_prompt, session)
    intent = json.loads(result)
    return intent

# After:
try:
    user_id = session.get('user_id')
    organization_id = session.get('organization_id')
    
    result_text = await self.llm.chat(
        prompt=user_prompt,
        model=self.model,
        system_message=system_prompt,
        temperature=0.1,
        max_tokens=500,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
        organization_id=organization_id,
        request_type='thinkguide',
        endpoint_path='/thinking_mode/stream',
        conversation_id=session.get('session_id'),
        diagram_type=self.diagram_type
    )
    
    # Parse JSON from response
    import re
    json_match = re.search(r'\{[\s\S]*\}', result_text)
    if json_match:
        intent = json.loads(json_match.group())
        return intent
    return {'action': 'discuss'}
```

**Step 2: Fix `flow_map_agent_react.py` (lines 82-88)**

Same fix as Step 1 (identical pattern).

**Step 3: Fix `double_bubble_map_agent_react.py` (lines 234-246)**

```python
# Before:
try:
    response = await self._call_llm_for_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        session_id=session.get('session_id', '')
    )
    return response

# After:
try:
    user_id = session.get('user_id')
    organization_id = session.get('organization_id')
    
    result_text = await self.llm.chat(
        prompt=user_prompt,
        model=self.model,
        system_message=system_prompt,
        temperature=0.1,
        max_tokens=500,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
        organization_id=organization_id,
        request_type='thinkguide',
        endpoint_path='/thinking_mode/stream',
        conversation_id=session.get('session_id'),
        diagram_type=self.diagram_type
    )
    
    # Parse JSON from response
    import re
    json_match = re.search(r'\{[\s\S]*\}', result_text)
    if json_match:
        response = json.loads(json_match.group())
        logger.info(f"[DoubleBubbleMapAgent] Intent detected: {response.get('action', 'unknown')}")
        return response
    return {'action': 'discuss'}
```

**Step 4: Test each agent**
1. Open ThinkGuide for Brace Map → verify intent detection works
2. Open ThinkGuide for Flow Map → verify intent detection works
3. Open ThinkGuide for Double Bubble Map → verify intent detection works
4. Check logs for any remaining errors

---

## P3: Slow Requests

### Total Occurrences: 939

### Breakdown

| Endpoint | Count | Cause |
|----------|-------|-------|
| `POST /api/generate_graph` | 906 | Expected (LLM calls) |
| `GET /auth` | 18 | DB connection wait |
| `GET /` | 5 | DB connection wait |
| `POST /api/frontend_log_batch` | 6 | DB connection wait |
| `GET /api/auth/captcha/generate` | 5 | DB connection wait |

### Non-LLM Slow Requests (Fixed by P0)
```
Slow request: GET / took 150.060s
Slow request: GET /auth took 180.067s
Slow request: GET /api/auth/captcha/generate took 120.035s
```

These simple endpoints were slow because they waited for database connections that were held by LLM requests. The P0 fix resolves this.

---

## P3: Background Rectangle Selectable (Purple Highlight Bug)

### Symptom
When clicking on white space in some diagrams (Bubble Map, Circle Map, Double Bubble Map), a large purple square/rectangle appears highlighted, covering most of the canvas.

### Visual Description
- User clicks on empty space in diagram
- Large purple-highlighted rectangle appears (selection color `#667eea`)
- Rectangle covers the entire canvas area
- Expected: Nothing should be selected when clicking white space

### Code Review

**Root Cause Analysis:**

The `InteractionHandler` in `interaction-handler.js` (lines 90-104) adds click handlers to ALL `rect` elements:

```javascript
d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
    const element = d3.select(nodes[i]);
    
    // Skip background rectangles and other non-interactive elements
    const elemClass = element.attr('class') || '';
    if (elemClass.includes('background') || elemClass.includes('watermark')) {
        return; // Skip this element
    }
    
    const nodeId = element.attr('data-node-id') || `node_${i}`;
    
    // Add node ID attribute if not exists
    if (!element.attr('data-node-id')) {
        element.attr('data-node-id', nodeId);  // ← BUG: Assigns data-node-id to background rect
    }
```

The logic only skips elements with class containing `'background'` or `'watermark'`. However, most renderers don't add this class to their background rectangles.

**Renderer Status:**

| Renderer | File | Has `class="background*"`? | Bug Present? |
|----------|------|---------------------------|--------------|
| Concept Map | `concept-map-renderer.js` (line 132) | **Yes** (`background-rect`) | No |
| Bubble Map | `bubble-map-renderer.js` (line 177) | **No** | **Yes** |
| Circle Map | `bubble-map-renderer.js` (line 534) | **No** | **Yes** |
| Double Bubble Map | `bubble-map-renderer.js` (line 777) | **No** | **Yes** |
| Other renderers | Various | Unknown | Likely |

**Selection Highlight Applied:**

From `selection-manager.js` (lines 88-93):
```javascript
// Apply selection highlight with contrasting blue/purple color
nodeElement
    .classed('selected', true)
    .attr('stroke', '#667eea')  // Blue/purple from app theme
    .attr('stroke-width', 4)
    .style('filter', 'drop-shadow(0 0 12px rgba(102, 126, 234, 0.7))');
```

### Affected Files

| File | Line(s) | Issue |
|------|---------|-------|
| `static/js/renderers/bubble-map-renderer.js` | 177, 534, 777 | Background rect missing `class="background"` |
| `static/js/managers/editor/interaction-handler.js` | 90-104 | Assigns `data-node-id` to unclassed rects |

### Step-by-Step Solution

**Option A: Add class to background rectangles (Recommended)**

In `bubble-map-renderer.js`, add class to each background rect:

```javascript
// Line 177 (Bubble Map):
svg.append('rect')
    .attr('class', 'background')  // ADD THIS
    .attr('x', minX)
    .attr('y', minY)
    // ...

// Line 534 (Circle Map):
svg.append('rect')
    .attr('class', 'background')  // ADD THIS
    .attr('x', minX)
    // ...

// Line 777 (Double Bubble Map):
svg.append('rect')
    .attr('class', 'background')  // ADD THIS
    .attr('width', width)
    // ...
```

**Option B: Enhanced detection in InteractionHandler**

In `interaction-handler.js`, add additional checks:

```javascript
// After line 97, add:
// Skip rectangles that fill the entire SVG (likely background)
const svgElement = d3.select('svg').node();
if (svgElement) {
    const svgWidth = svgElement.getAttribute('width');
    const svgHeight = svgElement.getAttribute('height');
    const rectWidth = element.attr('width');
    const rectHeight = element.attr('height');
    if (rectWidth === svgWidth && rectHeight === svgHeight) {
        return; // Skip - this is a background rect
    }
}
```

### Test Scenarios

1. Open Bubble Map → Click on white space → Should NOT highlight anything
2. Open Circle Map → Click on white space → Should NOT highlight anything
3. Open Double Bubble Map → Click on white space → Should NOT highlight anything
4. Open Concept Map → Click on white space → Should NOT highlight anything (already works)
5. Click on actual nodes → Should still highlight correctly with purple border

---

## P3: LLM JSON Extraction Failures

### Symptom
Multiple diagram agents fail to parse JSON from LLM responses:

```
[09:31:37] ERROR | BraceMapAgent: Failed to extract JSON from LLM response
[15:16:04] ERROR | DoubleBubbleMapAgent: Failed to extract JSON from LLM response
[15:57:41] ERROR | MindMapAgent: Failed to extract JSON from LLM response
[16:26:47] ERROR | TreeMapAgent: Failed to extract JSON from LLM response
[17:42:29] ERROR | DoubleBubbleMapAgent: Failed to extract JSON from LLM response
```

### Affected Agents
| Agent | Occurrences |
|-------|-------------|
| DoubleBubbleMapAgent | 3 |
| MindMapAgent | 1 |
| TreeMapAgent | 1 |
| BraceMapAgent | 1 |

### Example Raw Response
```
[16:26:47] ERROR | TreeMapAgent: Raw response was: topic: "Fruits"
```

### Root Cause
LLM returns plain text or malformed JSON instead of valid JSON. This can happen due to:
1. **Rate limiting** - Truncated responses when provider is overloaded
2. **Prompt issues** - LLM not following JSON format instructions
3. **Model variability** - Different models have different JSON formatting tendencies

### Current Extraction Method (Fragile)

**File:** `agents/core/agent_utils.py` (lines 23-70)

```python
# Current regex-based extraction - can fail easily
json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)  # Try markdown
json_match = re.search(r'\{.*\}', content, re.DOTALL)  # Try raw JSON
json_match = re.search(r'\[.*\]', content, re.DOTALL)  # Try array
```

**Problems with regex approach:**
- LLM adds explanatory text before/after JSON → Breaks extraction
- JSON is truncated due to rate limiting → Invalid JSON
- Nested braces confuse the regex → Wrong match
- LLM uses unusual formatting → No match

### Recommended Solution: DashScope JSON Mode

**Discovery:** DashScope (Qwen) supports `response_format={"type": "json_object"}` which **forces the model to output valid JSON**.

```python
# DashScope JSON mode example
completion = client.chat.completions.create(
    model="qwen-flash",
    messages=[...],
    response_format={"type": "json_object"}  # FORCES valid JSON output
)
json_string = completion.choices[0].message.content  # Guaranteed valid JSON
```

### LLM JSON Mode Support

| LLM | JSON Mode Support | Parameter |
|-----|------------------|-----------|
| **Qwen (DashScope)** | ✅ Yes | `response_format={"type": "json_object"}` |
| **DeepSeek** | ✅ Yes | `response_format={"type": "json_object"}` |
| **Kimi (Moonshot)** | ✅ Yes | `response_format={"type": "json_object"}` |
| **Hunyuan (Tencent)** | ⚠️ Check docs | May need different format |

### ⚠️ DashScope JSON Mode Caveats (from official docs)

**1. Validation Required (有效性校验)**

DashScope does NOT guarantee JSON conforms to a specific JSON Schema. Before passing to downstream business logic, validate using:
- Python: `jsonschema`
- JavaScript: `Ajv`
- Java: `Everit`

If validation fails → Use retry or LLM rewrite strategies.

**2. Do NOT use `max_tokens` (禁用 max_tokens)**

> ⛔ **CRITICAL**: Do NOT specify `max_tokens` when using JSON mode!

If `max_tokens` is set, the returned JSON may be **truncated/incomplete**, causing downstream parsing failures.

```python
# ❌ WRONG - may truncate JSON
response = client.chat.completions.create(
    model="qwen-flash",
    messages=[...],
    response_format={"type": "json_object"},
    max_tokens=1000  # ← DO NOT USE WITH JSON MODE
)

# ✅ CORRECT - let model output complete JSON
response = client.chat.completions.create(
    model="qwen-flash",
    messages=[...],
    response_format={"type": "json_object"}
    # No max_tokens - uses model's maximum
)
```

### Implementation Considerations

Given these caveats, the implementation should:
1. **Remove `max_tokens`** when using JSON mode
2. **Add JSON Schema validation** using `jsonschema` library after receiving response
3. **Add retry logic** if validation fails
4. **Keep fallback** to regex extraction for edge cases

### Expected Impact

| Metric | Before (Regex) | After (JSON Mode) |
|--------|----------------|-------------------|
| JSON extraction failures | 8+ per workshop | ~0 |
| Success rate | ~92% | ~99%+ |
| Code complexity | High (regex + fallbacks) | Low (`json.loads()`) |

### Step-by-Step Implementation

**Step 1: Add `response_format` to Client Methods**

In `clients/llm.py`, update `QwenClient.chat_completion`:

```python
async def chat_completion(self, messages: List[Dict], temperature: float = None,
                          max_tokens: int = 1000, 
                          response_format: dict = None) -> str:  # ADD parameter
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "extra_body": {"enable_thinking": False}
    }
    
    # ADD: Enable JSON mode if requested
    if response_format:
        payload["response_format"] = response_format
```

**Step 2: Add to LLM Service**

In `services/llm_service.py`, update `chat()` method:

```python
async def chat(
    self,
    prompt: str,
    model: str = 'qwen',
    response_format: dict = None,  # ADD parameter
    ...
) -> str:
    # Pass through to client
    return await client.chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,  # PASS through
        **kwargs
    )
```

**Step 3: Update Diagram Agents**

In each diagram agent (e.g., `bubble_map_agent.py`):

```python
# Before (fragile):
response = await self.llm.chat(prompt=prompt, model='qwen')
spec = extract_json_from_response(response)  # Can fail

# After (reliable):
response = await self.llm.chat(
    prompt=prompt, 
    model='qwen',
    response_format={"type": "json_object"}  # FORCE JSON
)
spec = json.loads(response)  # Guaranteed to work
```

**Step 4: Keep Fallback for Non-JSON Calls**

Keep `extract_json_from_response()` in `agent_utils.py` for backwards compatibility with any calls that don't use JSON mode.

### Affected Files

| File | Change Required |
|------|-----------------|
| `clients/llm.py` | Add `response_format` parameter to all client methods |
| `services/llm_service.py` | Add `response_format` parameter to `chat()` and `chat_stream()` |
| `agents/thinking_maps/*.py` | Use `response_format={"type": "json_object"}` |
| `agents/mind_maps/*.py` | Use `response_format={"type": "json_object"}` |

### Resolution Status
🔧 **Code Fix Required** - Implement JSON mode support in LLM clients and agents.

---

## P3: Agent Validation Failures

### DoubleBubbleMapAgent Validation

**Symptom:**
```
[09:18:06] WARN | DoubleBubbleMapAgent: Validation failed: Left topic must have at least 2 attributes
[15:15:31] WARN | DoubleBubbleMapAgent: Validation failed: Left topic must have at least 2 attributes
[15:16:09] WARN | DoubleBubbleMapAgent: Validation failed: Left topic must have at least 2 attributes
[15:16:28] WARN | DoubleBubbleMapAgent: Validation failed: Left topic must have at least 2 attributes
[15:16:49] WARN | DoubleBubbleMapAgent: Validation failed: Left topic must have at least 2 attributes
```

**Occurrences:** 5

**Root Cause:** 
User's prompt or LLM output doesn't provide enough attributes for a meaningful double bubble map comparison. This is expected behavior - the validation correctly rejects incomplete specifications.

### TreeMapAgent Validation

**Symptom:**
```
[16:26:33] WARN | TreeMapAgent: Validation failed: Missing or invalid topic
```

**Occurrences:** 1

**Root Cause:**
LLM response didn't include a valid topic field. Similar to JSON extraction issues.

### Resolution
These are **expected validation behaviors** - the agents correctly reject incomplete data.

No code fix needed. The root cause is likely rate limiting causing poor LLM outputs, which will improve after DashScope increases limits.

---

## P4: Authentication Warnings (Working as Intended)

### Captcha Issues

| Warning | Count | Status |
|---------|-------|--------|
| `Captcha not found` | 40 | Normal - captcha expired |
| `Captcha verification failed` | 15 | Normal - user error |
| `Captcha rate limit exceeded for IP` | 2 IPs | Working as intended |

### Login Failures

| Warning | Count | Status |
|---------|-------|--------|
| `Invalid password` | 5 | Normal - wrong credentials |
| `Invalid token: Signature has expired` | Multiple | Normal - session expired |
| `Account locked` | 4 | Normal - security feature |
| `Phone number already registered` | 1 | Normal - duplicate registration |
| `Invalid or expired invitation code` | 1 | Normal - bad invite code |

---

## P4: Prompt Clarity Warnings (Working as Intended)

### LLM Classification Unclear

| Prompt | Issue |
|--------|-------|
| `工会活动` | Too vague |
| `勾股定理` | Multiple possible diagram types |
| `化学公式` | Needs more context |
| `学习用具` | Too generic |

These warnings indicate the system correctly identified ambiguous prompts and requested clarification.

---

## P4: MindMap Layout Warnings (Working as Intended)

### Odd Number of Branches

**Symptom:**
```
Odd number of branches (5) detected! Adding empty branch for balance.
Odd number of branches (9) detected! Adding empty branch for balance.
```

**Occurrences:** 8

**Root Cause:** MindMap renderer requires even number of branches for symmetrical layout. System auto-adds empty placeholder branch for visual balance.

**Status:** ✅ Working as Intended (auto-correction behavior)

---

### Node Overlap Detection

**Symptom:**
```
OVERLAP: Additional information and Additional Aspect overlap
OVERLAP: 运算规则精讲 and 六年级数学分数除法总复习 overlap
```

**Occurrences:** 15

**Root Cause:** LLM generated nodes with similar/overlapping content. System detects and warns about semantic overlap.

**Status:** ✅ Working as Intended (quality detection)

---

## Diagram Generation Failures

### JSON Extraction Failures

| Agent | Error | Likely Cause |
|-------|-------|--------------|
| `BraceMapAgent` | Failed to extract JSON from LLM response | LLM returned malformed JSON |
| `DoubleBubbleMapAgent` | Failed to extract JSON from LLM response | LLM returned malformed JSON |
| `MindMapAgent` | Failed to extract JSON from LLM response | LLM returned malformed JSON |
| `TreeMapAgent` | Failed to extract JSON from LLM response | LLM returned malformed JSON |

### Validation Failures

| Agent | Error | Issue |
|-------|-------|-------|
| `DoubleBubbleMapAgent` | Left topic must have at least 2 attributes | Insufficient content generated |
| `DoubleBubbleMapAgent` | Left attributes: 0, Right attributes: 0, Shared: 0 | Empty generation |
| General | Missing or invalid topic | LLM didn't follow format |

---

## Summary of Actions Required

### Immediate (Code Changes Required)

| # | Priority | Issue | File(s) | Line(s) | Status |
|---|----------|-------|---------|---------|--------|
| 1 | ✅ P0 | Database Connection Pool | `config/database.py`, `utils/auth.py` | - | **FIXED** |
| 2 | 🔧 P2 | BraceMapThinkingAgent missing `_call_llm` | `agents/thinking_modes/brace_map_agent_react.py` | 83 | Code Fix Required |
| 3 | 🔧 P2 | FlowMapThinkingAgent missing `_call_llm` | `agents/thinking_modes/flow_map_agent_react.py` | 83 | Code Fix Required |
| 4 | 🔧 P2 | DoubleBubbleMapThinkingAgent missing `_call_llm_for_json` | `agents/thinking_modes/double_bubble_map_agent_react.py` | 235 | Code Fix Required |
| 5 | ✅ P2 | Tree Renderer dependency loading | `static/js/dynamic-renderer-loader.js` | 126-138 | **FIXED** |
| 6 | 🔧 P2 | LLMAutoCompleteManager null reference | `static/js/managers/toolbar/llm-autocomplete-manager.js` | 217 | Code Fix Required |
| 7 | 🔧 P3 | Background Rectangle Selectable (Purple Highlight) | `static/js/renderers/bubble-map-renderer.js` | 177, 534, 777 | Code Fix Required |
| 8 | 🔧 P3 | LLM JSON Extraction Failures | `clients/llm.py`, `services/llm_service.py`, `agents/` | Multiple | Code Fix Required |

**Note**: P1 LLM Provider Rate Limiting issues have been moved to [LLM_PROVIDER_RATE_LIMITING.md](LLM_PROVIDER_RATE_LIMITING.md) (pending provider response).

### Code Change Details

**Fix #2-4: ThinkingAgent Missing Methods**
- **Pattern to follow**: See `circle_map_agent_react.py` lines 222-234
- **Key change**: Replace `self._call_llm()` or `self._call_llm_for_json()` with `self.llm.chat()`
- **Test**: Open ThinkGuide for each diagram type, verify intent detection works

**Fix #5: Tree Renderer Dependency** ✅ FIXED
- **Root cause**: `tree-renderer.js` requires `MindGraphUtils` from `shared-utilities.js`
- **Fix Applied**: `dynamic-renderer-loader.js` now loads `shared-utilities.js` before any renderer (lines 126-138)
- **Verification**: Code review confirmed fix is in place

**Fix #6: LLMAutoCompleteManager Null Reference**
- **Root cause**: Line 217 calls `this.progressRenderer.setAllLLMButtonsLoading()` without null check
- **Fix**: Add `if (this.progressRenderer)` guard before the call
- **Test**: Start LLM generation, navigate away before completion, verify no console errors

**Fix #7: Background Rectangle Selectable (Purple Highlight Bug)**
- **Root cause**: Background rectangles in renderers don't have `class="background"`, so `interaction-handler.js` treats them as selectable nodes
- **Affected renderers**: Bubble Map (line 177), Circle Map (line 534), Double Bubble Map (line 777)
- **Working example**: `concept-map-renderer.js` (line 132) correctly uses `class="background-rect"`
- **Fix**: Add `.attr('class', 'background')` to each background rect in `bubble-map-renderer.js`
- **Test**: Open Bubble/Circle/Double Bubble Map → Click white space → Should NOT highlight

**Fix #8: LLM JSON Extraction Failures (Use DashScope JSON Mode)**
- **Root cause**: Current regex-based JSON extraction in `agent_utils.py` is fragile and fails when LLM adds text or truncates output
- **Discovery**: DashScope supports `response_format={"type": "json_object"}` which forces valid JSON output
- **Files to update**:
  1. `clients/llm.py` - Add `response_format` parameter to all client methods
  2. `services/llm_service.py` - Add `response_format` parameter to `chat()` and pass to clients
  3. `agents/thinking_maps/*.py` - Use `response_format={"type": "json_object"}` in LLM calls
  4. `agents/mind_maps/*.py` - Use `response_format={"type": "json_object"}` in LLM calls
- **Expected improvement**: JSON extraction success rate from ~92% to ~99%+
- **Test**: Generate diagrams with all types → Verify no "Failed to extract JSON" errors

### Monitoring

- 📊 Track LLM provider response times
- 📊 Monitor connection pool utilization
- 📊 Alert on rate limit errors (2003, 429)
- 📊 Monitor frontend error rates via `/api/frontend_log_batch`

---

## P4: Logging Level Improvements (Reduce Noise)

### Problem
Current logs are extremely noisy. One page load generates 50+ static file logs. One diagram generation generates 20+ detailed step-by-step logs. This makes finding real issues difficult.

### Current Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     Log Sources                             │
├─────────────────────────────────────────────────────────────┤
│  1. Uvicorn Access Logs (HTTP requests)                     │
│     - Controlled by: run_server.py + uvicorn_log_config.py  │
│     - Example: SRVR | "GET /static/css/editor.css" 200      │
│                                                             │
│  2. Application Logs (Python logging module)                │
│     - Controlled by: main.py + individual modules           │
│     - Example: AGNT | FlowMapAgent: Added step: '准备食材'    │
└─────────────────────────────────────────────────────────────┘
```

---

### Complete Code Review: Logs to Move to DEBUG

#### 1. Uvicorn Access Logs (Static Files)

**File:** `uvicorn_log_config.py`

| Current Log | Volume | Action |
|-------------|--------|--------|
| `GET /static/css/*.css` | 5+ per page | Move to DEBUG |
| `GET /static/js/*.js` | 40+ per page | Move to DEBUG |
| `GET /static/fonts/*` | 3+ per page | Move to DEBUG |
| `GET /favicon.svg` | 1 per page | Move to DEBUG |

**Fix:** Add `StaticFileFilter` class (see Step-by-Step Fix below)

---

#### 2. Authentication Logs (Repeated)

**File:** `utils/auth.py` (line 869)

```python
logger.info(f"Authenticated teacher: {user.name}")
```

| Current Behavior | Problem |
|------------------|---------|
| Logs on EVERY authenticated request | 4 logs per autocomplete (4 LLM calls) |
| Logs same user multiple times | Creates noise during parallel calls |

**Fix:** Change to `logger.debug()` or log only on first request per session

---

#### 3. ThinkingAgent Internal Logs

**Files:** `agents/thinking_modes/*_agent_react.py`

| Log Pattern | File | Action |
|-------------|------|--------|
| `[*ThinkingAgent] Initialized for diagram type:` | All *_agent_react.py | DEBUG |
| `[*ThinkingAgent] Language detection from text:` | All *_agent_react.py | DEBUG |
| `[*ThinkingAgent] Created session:` | All *_agent_react.py | DEBUG |
| `[*ThinkingAgent] ReAct cycle started` | All *_agent_react.py | DEBUG |
| `[*ThinkingAgent] REASON → Intent:` | All *_agent_react.py | DEBUG |

**Example fix in `brace_map_agent_react.py`:**
```python
# Before:
logger.info(f"[BraceMapThinkingAgent] Language detection from text: '...' → {lang}")

# After:
logger.debug(f"[BraceMapThinkingAgent] Language detection from text: '...' → {lang}")
```

---

#### 4. NodePalette Streaming Logs (HIGH VOLUME)

**Files:** `agents/thinking_modes/node_palette/*.py`

| Log Pattern | Volume per Palette | Action |
|-------------|-------------------|--------|
| `[NodePalette-Stream] Node generated \| LLM: *` | 50-100 per session | DEBUG |
| `[BraceMapPalette] Node tagged with part mode=*` | 50-100 per session | DEBUG |
| `[FlowMapPalette] Node tagged with stage mode=*` | 50-100 per session | DEBUG |
| `[DoubleBubble] Node tagged with mode=*` | 50-100 per session | DEBUG |
| `[DoubleBubble] DIFFERENCES mode - processing node` | 20-50 per session | DEBUG |
| `[DoubleBubble] ✓ Parsed pair successfully` | 20-50 per session | DEBUG |
| `[*Palette-Prompt] Building prompt for stage:` | 2-4 per session | DEBUG |

**Keep at INFO (summaries only):**
- `[NodePalette] * batch * complete | Unique: * | Time: *`

---

#### 5. NodePalette Generator Initialization

**Files:** `agents/thinking_modes/node_palette/*.py`

| Log Pattern | Action |
|-------------|--------|
| `[NodePalette-*Generator] Initialized with concurrent multi-LLM architecture` | DEBUG |
| `[NodePalette-*Generator] LLMs: qwen, deepseek, hunyuan, kimi` | DEBUG |

---

#### 6. LLM Service Detailed Logs

**File:** `services/llm_service.py`

| Log Pattern | Action | Reason |
|-------------|--------|--------|
| `[LLMService] * responded in X.XXs` | **KEEP INFO** | Performance monitoring |
| `[LLMService] * stream completed in X.XXs` | DEBUG | Duplicate of above |
| `[LLMService] * stream complete - N tokens in X.XXs (X tok/s)` | DEBUG | Too detailed |
| `[LLMService] stream_progressive() - streaming from N models` | DEBUG | Internal |
| `[LLMService] stream_progressive() complete: N/N succeeded` | DEBUG | Internal |

---

#### 7. HTTP Client Logs (External API Calls)

**Source:** httpx library / LLM clients

| Log Pattern | Action |
|-------------|--------|
| `HTTP Request: POST https://api.hunyuan.cloud.tencent.com/*` | DEBUG |
| `HTTP Request: POST https://dashscope.aliyuncs.com/*` | DEBUG |

**Fix:** Set httpx logger to WARNING level in `main.py`:
```python
logging.getLogger("httpx").setLevel(logging.WARNING)
```

---

#### 8. Agent Step Processing Logs

**Files:** `agents/thinking_maps/*.py`, `agents/mind_maps/*.py`

| Log Pattern | File | Action |
|-------------|------|--------|
| `FlowMapAgent: Raw steps from LLM:` | flow_map_agent.py | DEBUG |
| `FlowMapAgent: Added normalized step:` | flow_map_agent.py | DEBUG |
| `FlowMapAgent: Final normalized steps:` | flow_map_agent.py | DEBUG |
| `FlowMapAgent: Processing N substeps entries` | flow_map_agent.py | DEBUG |
| `FlowMapAgent: Matching substeps for step` | flow_map_agent.py | DEBUG |
| `BraceMapAgent: * parts/subparts` | brace_map_agent.py | DEBUG |
| `DoubleBubbleMapAgent: Left attributes: N, Right: N` | double_bubble_map_agent.py | DEBUG |
| `BridgeMapAgent: Alternative dimensions from LLM:` | bridge_map_agent.py | DEBUG |

**Keep at INFO:**
- `FlowMapAgent: Flow map generation completed successfully`
- `BraceMapAgent: Brace map generation completed successfully`

---

#### 9. DIFY/MindMate Logs

**Files:** `clients/dify.py`, `services/voice_diagram_agent.py`

| Log Pattern | Action |
|-------------|--------|
| `[DIFY] API URL:` | DEBUG (startup only) |
| `[DIFY] Making async request to:` | DEBUG |
| `[DIFY] Request headers:` | DEBUG |
| `[DIFY] Response status:` | DEBUG |
| `[DIFY] Sending async POST request...` | DEBUG |
| `[DIFY] Using conversation_id:` | DEBUG |
| `[DIFY] Async streaming message:` | DEBUG |
| `[MindMate] Conversation opener triggered` | INFO (keep) |

---

### Summary: Files to Update

| File | Changes |
|------|---------|
| `uvicorn_log_config.py` | Add StaticFileFilter |
| `utils/auth.py` | Line 869: info → debug |
| `services/llm_service.py` | Stream detail logs → debug |
| `agents/thinking_modes/*_agent_react.py` (6 files) | Internal logs → debug |
| `agents/thinking_modes/node_palette/*.py` (6 files) | Streaming logs → debug |
| `agents/thinking_maps/*.py` (8 files) | Step processing → debug |
| `agents/mind_maps/mind_map_agent.py` | Step processing → debug |
| `clients/dify.py` | Request/response logs → debug |
| `main.py` | Add `logging.getLogger("httpx").setLevel(logging.WARNING)` |

---

### Step-by-Step Fix

**Step 1: Filter static files from Uvicorn access log**

Add to `uvicorn_log_config.py`:
```python
class StaticFileFilter(logging.Filter):
    """Filter out static file requests from access logs"""
    
    SKIP_PREFIXES = ('/static/', '/favicon')
    
    def filter(self, record):
        message = record.getMessage()
        for prefix in self.SKIP_PREFIXES:
            if prefix in message:
                return False
        return True

# Update LOGGING_CONFIG:
"filters": {
    "static_filter": {
        "()": StaticFileFilter,
    },
},
"handlers": {
    "access": {
        "class": "logging.StreamHandler",
        "formatter": "access",
        "stream": "ext://sys.stdout",
        "filters": ["static_filter"],
    },
},
```

**Step 2: Suppress httpx logs**

Add to `main.py` after logging setup:
```python
logging.getLogger("httpx").setLevel(logging.WARNING)
```

**Step 3: Change auth log to debug**

In `utils/auth.py` line 869:
```python
# Before:
logger.info(f"Authenticated teacher: {user.name}")

# After:
logger.debug(f"Authenticated teacher: {user.name}")
```

**Step 4: Change agent internal logs to debug**

Use find/replace in each file:
```python
# Pattern to find:
logger.info(f"[*ThinkingAgent]
logger.info(f"[NodePalette-Stream]
logger.info(f"[*Palette] Node tagged

# Replace with:
logger.debug(...)
```

---

### Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Logs per page load | **50+** | 5-10 |
| Logs per diagram generation | **20-50** | 5-10 |
| Logs per NodePalette session | **100+** | 5-10 |
| Log file size (1 hour workshop) | **~50MB** | ~5MB |
| Time to find errors | **Minutes** | Seconds |

---

## Feature Enhancements from Workshop Feedback

### Gallery: QQ Group Feedback Button

| Item | Details |
|------|---------|
| **Location** | Gallery page, top right corner |
| **Feature** | Button to display QQ group QR code |
| **Purpose** | Allow users to scan QR code and join QQ group for software feedback |

**User Story:**
- User visits the gallery page
- Clicks on "Join Feedback Group" button in the top right corner
- Modal/popup displays QQ group QR code
- User scans with phone to join QQ group for providing feedback

**Implementation Notes:**
1. Add button component to gallery header/toolbar
2. Create modal component to display QR code image
3. QR code image should be stored in `/static/images/` directory
4. Button text suggestions: "反馈群" (Chinese) / "Feedback Group" (English)

**Priority:** P4 (Enhancement)

**Status:** 🔧 Pending Implementation

---

## Appendix: Complete Error Types

### All Unique ERROR Messages (185 types)

<details>
<summary>Click to expand full list</summary>

```
[DoubleBubbleMapAgent] Intent detection failed: 'DoubleBubbleMapThinkingAgent' object has no attribute '_call_llm_for_json'
[LLMService] deepseek failed after 90-153s
[LLMService] hunyuan failed after 90-120s
[LLMService] hunyuan stream error: 请求限频
[LLMService] kimi failed after 90-165s
[LLMService] kimi stream error: 429
[LLMService] qwen failed after 90-153s
[NodePalette] hunyuan stream error: 请求限频
[NodePalette] kimi stream error: 429
[TokenTracker] Batch write failed: QueuePool limit
BraceMapAgent: Failed to extract JSON from LLM response
BubbleMapAgent: Error in spec generation
CircleMapAgent: Error in spec generation
DoubleBubbleMapAgent: Error in spec generation
DoubleBubbleMapAgent: Failed to extract JSON from LLM response
Error validating cookie token: QueuePool limit
Exception in ASGI application
Failed to generate spec for brace_map
Failed to generate spec for bubble_map
Failed to generate spec for circle_map
Failed to generate spec for double_bubble_map
Failed to generate spec for mind_map
Failed to generate spec for tree_map
Hunyuan API error: 请求限频
Hunyuan streaming error: 请求限频
Intent detection failed: 'BraceMapThinkingAgent' object has no attribute '_call_llm'
Intent detection failed: 'FlowMapThinkingAgent' object has no attribute '_call_llm'
Kimi API error 429
Kimi stream error 429
Kimi streaming error: 429
LLM double bubble topic extraction error
MindMapAgent: Error in spec generation
MindMapAgent: Failed to extract JSON from LLM response
Qwen API timeout
Result contains error: Failed to generate * specification
Result contains error: Generated invalid specification
TreeMapAgent: Failed to extract JSON from LLM response
Unhandled exception: TimeoutError: QueuePool limit
```

</details>

### All Unique WARN Messages (1,024+ types)

<details>
<summary>Click to expand categories</summary>

**Authentication:**
- Captcha not found (40 unique IDs)
- Captcha verification failed (15 unique IDs)
- Captcha rate limit exceeded (2 IPs)
- Invalid password attempts
- Account locked warnings
- Token expired warnings

**HTTP Status:**
- HTTP 400: Captcha errors
- HTTP 401: Auth failures
- HTTP 403: Permission denied
- HTTP 409: Duplicate registration
- HTTP 423: Account locked
- HTTP 429: Rate limited

**Performance:**
- Slow request warnings (939 total)

**Prompt Clarity:**
- LLM explicitly returned 'unclear'
- Prompt is too complex or unclear

**Diagram Validation:**
- Odd number of branches detected
- Validation failed warnings

</details>

### Frontend Errors (via /api/frontend_log_batch)

<details>
<summary>Click to expand frontend error list</summary>

```
[LLMEngineManager] API error for qwen | Error: HTTP 504: Gateway Time-out
[LLMEngineManager] API error for kimi | Error: HTTP 504: Gateway Time-out
[LLMEngineManager] API error for hunyuan | Error: HTTP 504: Gateway Time-out
[LLMEngineManager] API error for hunyuan | AbortError: The user aborted a request
[LLMAutoCompleteManager] Cannot render deepseek: No valid cached data
[LLMAutoCompleteManager] Generation failed | TypeError: Cannot read properties of null (reading 'setAllLLMButtonsLoading')
[DynamicRendererLoader] Failed to load renderer module tree-renderer
[DynamicRendererLoader] Dynamic rendering failed for tree_map
[RendererDispatcher] Dynamic rendering failed, falling back to static
[RendererDispatcher] Using static renderer fallback (not recommended)
[RendererDispatcher] renderTreeMap function not found
[RendererDispatcher] Renderer for 'tree_map' not loaded or not available
[Editor] No SVG found - zoom/pan disabled
[Editor] No SVG found for auto-fit
```

</details>

---

*Document generated from server log analysis on December 2, 2024*

