# Middleware Migration Plan - Step-by-Step Implementation Guide

**Date:** October 10, 2025  
**Author:** lycosa9527, MindSpring Team  
**Status:** ✅ READY FOR IMPLEMENTATION  
**Reference:** `docs/CIRCLE_MAP_SPEC_UPDATE_FIX.md`

---

## 📋 Executive Summary

This document provides **linear, step-by-step instructions** to:
1. **Phase 4:** Fix Flow Map and Multi-Flow Map auto-complete (frontend)
2. **Phase 5:** Remove LLMServiceWrapper and use middleware directly (backend)

**Implementation Order:** Phase 4 FIRST, then Phase 5.

---

## 🎯 What We're Fixing

### Problem
- Flow Map and Multi-Flow Map auto-complete sends wrong/stale topics to LLMs
- Same bug pattern as Circle Map (which we already fixed)
- Cause: `identifyMainTopic()` doesn't check `spec.title` and `spec.event` in Strategy 1

### Solution
- **Phase 4:** Add Strategy 1 handling for Flow/Multi-Flow maps
- **Phase 5:** Simplify architecture by removing unnecessary wrapper layer

### Expected Results
- ✅ Auto-complete works correctly for ALL 10 diagram types
- ✅ ~220 lines of code removed
- ✅ Cleaner, more maintainable architecture
- ✅ Slightly better performance

---

# PHASE 4: Frontend Fixes (DO THIS FIRST)

## Step 1: Understand the Problem

**Current State:**
```javascript
// toolbar-manager.js line 1647
if (diagramType === 'bubble_map' || diagramType === 'circle_map' || 
    diagramType === 'tree_map' || diagramType === 'brace_map') {
    if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
        return spec.topic;
    }
}
// Flow Map and Multi-Flow Map are NOT included! ❌
```

**Issue:** Flow Map uses `spec.title`, Multi-Flow Map uses `spec.event`. They're not checked in Strategy 1, so they fall back to Strategy 2 (less reliable).

**Verification:**
- ✅ `updateFlowMapText()` correctly updates `spec.title` (line 1639 of interactive-editor.js)
- ✅ `updateMultiFlowMapText()` correctly updates `spec.event` (line 1690 of interactive-editor.js)
- ❌ But `identifyMainTopic()` doesn't read these fields in Strategy 1!

---

## Step 2: Open the File

**File:** `static/js/editor/toolbar-manager.js`

**Location to modify:** After line 1661

**Find this code:**
```javascript
        }
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        // CONSISTENCY FIX: Like bridge_map, use spec as source of truth
        if (diagramType === 'double_bubble_map') {
```

---

## Step 3: Insert Code for Flow Map

**INSERT BETWEEN line 1661 and "Strategy 1b":**

```javascript
        
        // Strategy 1-flow: For Flow Map, check spec.title (NOT spec.topic)
        // Flow Map uses 'title' field, similar to how Circle Map uses 'center' nodeType
        if (diagramType === 'flow_map') {
            // Check spec first (updated by updateFlowMapText)
            if (spec && spec.title && !this.validator.isPlaceholderText(spec.title)) {
                return spec.title;
            }
            // Fallback: Check DOM if spec is not available
            const titleNode = nodes.find(node => node.nodeType === 'title');
            if (titleNode && titleNode.text && !this.validator.isPlaceholderText(titleNode.text)) {
                return titleNode.text;
            }
        }
```

---

## Step 4: Insert Code for Multi-Flow Map

**INSERT IMMEDIATELY AFTER the Flow Map block:**

```javascript
        
        // Strategy 1-multiflow: For Multi-Flow Map, check spec.event (NOT spec.topic)
        // Multi-Flow Map uses 'event' field for the central event
        if (diagramType === 'multi_flow_map') {
            // Check spec first (updated by updateMultiFlowMapText)
            if (spec && spec.event && !this.validator.isPlaceholderText(spec.event)) {
                return spec.event;
            }
            // Fallback: Check DOM if spec is not available
            const eventNode = nodes.find(node => node.nodeType === 'event');
            if (eventNode && eventNode.text && !this.validator.isPlaceholderText(eventNode.text)) {
                return eventNode.text;
            }
        }
```

---

## Step 5: Verify the Complete Addition

**After your changes, the code should look like:**

```javascript
        // End of bubble/circle/tree/brace Strategy 1 block
        }
        
        // ===== YOUR NEW CODE STARTS HERE =====
        
        // Strategy 1-flow: For Flow Map, check spec.title (NOT spec.topic)
        if (diagramType === 'flow_map') {
            if (spec && spec.title && !this.validator.isPlaceholderText(spec.title)) {
                return spec.title;
            }
            const titleNode = nodes.find(node => node.nodeType === 'title');
            if (titleNode && titleNode.text && !this.validator.isPlaceholderText(titleNode.text)) {
                return titleNode.text;
            }
        }
        
        // Strategy 1-multiflow: For Multi-Flow Map, check spec.event (NOT spec.topic)
        if (diagramType === 'multi_flow_map') {
            if (spec && spec.event && !this.validator.isPlaceholderText(spec.event)) {
                return spec.event;
            }
            const eventNode = nodes.find(node => node.nodeType === 'event');
            if (eventNode && eventNode.text && !this.validator.isPlaceholderText(eventNode.text)) {
                return eventNode.text;
            }
        }
        
        // ===== YOUR NEW CODE ENDS HERE =====
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        if (diagramType === 'double_bubble_map') {
```

---

## Step 6: Test Phase 4

### Test Flow Map:
1. Create or open a Flow Map
2. Edit the title (main topic box at top)
3. Type a new title: `"软件开发流程"`
4. Press Enter
5. Verify in console: `window.interactiveEditor?.currentSpec?.title` should show `"软件开发流程"`
6. Click auto-complete button
7. Check backend logs for: `DEBUG | AGNT | User prompt: 软件开发流程`

### Test Multi-Flow Map:
1. Create or open a Multi-Flow Map
2. Edit the central event (middle box)
3. Type a new event: `"数字化转型"`
4. Press Enter
5. Verify in console: `window.interactiveEditor?.currentSpec?.event` should show `"数字化转型"`
6. Click auto-complete button
7. Check backend logs for: `DEBUG | AGNT | User prompt: 数字化转型`

### Success Criteria:
- ✅ Flow Map auto-complete uses current title (not old/default)
- ✅ Multi-Flow Map auto-complete uses current event (not old/default)
- ✅ All 4 LLMs receive correct parallel prompts
- ✅ No regression in other diagram types

**If tests pass, Phase 4 is COMPLETE! ✅**

---

# PHASE 5: Backend Refactoring (DO THIS AFTER PHASE 4)

## Overview: Why Remove the Wrapper?

**Current Architecture (Inefficient):**
```
Agent → builds messages list → LLMServiceWrapper → tears apart messages → llm_service → LLM
```

**New Architecture (Clean):**
```
Agent → llm_service → LLM
```

**Benefits:**
- Remove ~220 lines of unnecessary code
- Better performance (no list construction/deconstruction)
- Clearer code (direct middleware usage)
- Easier to maintain (fewer abstractions)

---

## Step 1: Update Base Agent

**File:** `agents/core/base_agent.py`

**Current code (lines 38-49):**
```python
@property
def llm_client(self):
    """
    Get the LLM client for this agent's model.
    Each agent instance uses its own model (no global state).
    """
    try:
        from ..core.agent_utils import get_llm_client
        return get_llm_client(model_id=self.model)
    except Exception as e:
        logger.warning(f"Failed to get LLM client for model {self.model}: {e}")
        return None
```

**Action:** DELETE the entire `@property llm_client` method (lines 38-49)

**Result:** Agents will no longer have `self.llm_client` - they'll call `llm_service` directly.

---

## Step 2: Update Circle Map Agent (Example Pattern)

**File:** `agents/thinking_maps/circle_map_agent.py`

### 2a. Update Import Section

**FIND (around line 75-87):**
```python
from prompts import get_prompt

system_prompt = get_prompt("circle_map_agent", language, "generation")

if not system_prompt:
    logger.error(f"CircleMapAgent: No prompt found for language {language}")
    return None
    
user_prompt = f"请为以下描述创建一个圆圈图：{prompt}" if language == "zh" else f"Please create a circle map for the following description: {prompt}"

# Generate response from LLM using centralized message preparation
from config.settings import config
messages = config.prepare_llm_messages(system_prompt, user_prompt, model='qwen')
response = await self.llm_client.chat_completion(messages)
```

**REPLACE WITH:**
```python
from prompts import get_prompt
from services.llm_service import llm_service

system_prompt = get_prompt("circle_map_agent", language, "generation")

if not system_prompt:
    logger.error(f"CircleMapAgent: No prompt found for language {language}")
    return None
    
user_prompt = f"请为以下描述创建一个圆圈图：{prompt}" if language == "zh" else f"Please create a circle map for the following description: {prompt}"

# Call middleware directly - clean and efficient!
response = await llm_service.chat(
    prompt=user_prompt,
    model=self.model,
    system_message=system_prompt,
    max_tokens=1000,
    temperature=1.0
)
```

### 2b. Summary of Changes:
- ❌ Remove: `from config.settings import config`
- ✅ Add: `from services.llm_service import llm_service`
- ❌ Remove: `messages = config.prepare_llm_messages(...)`
- ❌ Remove: `response = await self.llm_client.chat_completion(messages)`
- ✅ Add: Direct `llm_service.chat()` call with named parameters

---

## Step 3: Apply Same Pattern to All 9 Other Agents

**Files to update (same pattern as Circle Map):**

1. `agents/thinking_maps/bubble_map_agent.py`
   - Find `_generate_bubble_map_spec()` method
   - Apply same FIND/REPLACE pattern

2. `agents/thinking_maps/tree_map_agent.py`
   - Find `_generate_tree_map_spec()` method
   - Apply same FIND/REPLACE pattern

3. `agents/thinking_maps/brace_map_agent.py`
   - Find `_generate_brace_map_spec()` method
   - Apply same FIND/REPLACE pattern

4. `agents/thinking_maps/flow_map_agent.py`
   - Find `_generate_flow_map_spec()` method
   - Apply same FIND/REPLACE pattern

5. `agents/thinking_maps/multi_flow_map_agent.py`
   - Find `_generate_multi_flow_map_spec()` method
   - Apply same FIND/REPLACE pattern

6. `agents/thinking_maps/double_bubble_map_agent.py`
   - Find `_generate_double_bubble_map_spec()` method
   - Apply same FIND/REPLACE pattern

7. `agents/thinking_maps/bridge_map_agent.py`
   - Find `_generate_bridge_map_spec()` method
   - Apply same FIND/REPLACE pattern

8. `agents/mind_maps/mind_map_agent.py`
   - Find LLM call in generation method
   - Apply same FIND/REPLACE pattern

9. `agents/concept_maps/concept_map_agent.py`
   - Find LLM call in generation method
   - Apply same FIND/REPLACE pattern

**Pattern for each:**
```python
# REMOVE:
from config.settings import config
messages = config.prepare_llm_messages(system_prompt, user_prompt, model='MODEL')
response = await self.llm_client.chat_completion(messages)

# REPLACE WITH:
from services.llm_service import llm_service
response = await llm_service.chat(
    prompt=user_prompt,
    model=self.model,
    system_message=system_prompt,
    max_tokens=1000,
    temperature=1.0  # Adjust if needed per diagram type
)
```

---

## Step 4: Remove Wrapper Class

**File:** `agents/core/agent_utils.py`

### 4a. Remove LLMServiceWrapper Class

**FIND (lines ~23-130):**
```python
class LLMServiceWrapper:
    """
    Wrapper class that makes llm_service middleware compatible with agent interface.
    ...
    """
    def __init__(self, model_id='qwen'):
        # ... entire wrapper implementation ...
```

**Action:** DELETE the entire `LLMServiceWrapper` class (~100 lines)

### 4b. Remove get_llm_client Function

**FIND (lines ~135-145):**
```python
def get_llm_client(model_id='qwen'):
    """..."""
    logger.info(f"get_llm_client() - Creating LLMServiceWrapper for model: {model_id}")
    return LLMServiceWrapper(model_id=model_id)
```

**Action:** DELETE the entire `get_llm_client()` function

### 4c. Keep Other Utility Functions

**KEEP:** Functions like `extract_json_from_response()` and other utilities - only remove wrapper-related code.

---

## Step 5: Update or Remove Wrapper Tests

**File:** `tests/test_agent_middleware_integration.py`

**Option 1 (Recommended):** Delete this file
- It only tests the wrapper which we're removing
- Run: `git rm tests/test_agent_middleware_integration.py`

**Option 2 (Alternative):** Rename and update to test direct middleware usage
- Rename to: `tests/test_agent_direct_middleware.py`
- Update tests to verify agents call `llm_service` directly

---

## Step 6: Test Phase 5

### 6a. Run Unit Tests
```bash
pytest tests/services/
```

**Expected:** All middleware tests pass (wrapper is gone, but middleware still works)

### 6b. Test Each Diagram Type

**For each of the 10 diagram types:**
1. Create diagram via UI
2. Verify it generates correctly
3. Check that it uses proper LLM
4. Test auto-complete (should still work)

**Checklist:**
- [ ] Bubble Map
- [ ] Circle Map
- [ ] Tree Map
- [ ] Brace Map
- [ ] Flow Map
- [ ] Multi-Flow Map
- [ ] Double Bubble Map
- [ ] Bridge Map
- [ ] Mind Map
- [ ] Concept Map

### 6c. Verify Middleware Features Still Work

**Test error handling:**
- Disconnect internet briefly
- Generate diagram
- Should see retry attempts in logs
- Should eventually fail gracefully with error message

**Test circuit breaker:**
- If a model repeatedly fails, circuit should open
- Logs should show circuit state changes

### 6d. Check Performance

**Before/After comparison:**
- Generate same diagram with old code (if you have backup)
- Generate with new code
- Should be ~5-10% faster (micro-optimization from removing overhead)

---

## Step 7: Success Criteria

**Phase 5 is complete when:**
- ✅ All 10 diagram types generate correctly
- ✅ Middleware error handling still works (retries, circuit breaker)
- ✅ ~220 lines of code removed
- ✅ All unit tests pass
- ✅ No functionality changes - just cleaner architecture
- ✅ Code is easier to read and understand

---

# APPENDIX: Reference Information

## Complete Node Type Inventory

| Diagram Type | Main Topic Node Type | Spec Field | Update Method |
|--------------|---------------------|------------|---------------|
| Bubble Map | `'topic'` | `spec.topic` | `updateBubbleMapText()` |
| Circle Map | `'center'` ⚠️ | `spec.topic` | `updateCircleMapText()` |
| Tree Map | `'topic'` | `spec.topic` | `updateTreeMapText()` |
| Brace Map | `'topic'` | `spec.topic` | `updateBraceMapText()` |
| Flow Map | `'title'` | `spec.title` | `updateFlowMapText()` |
| Multi-Flow Map | `'event'` | `spec.event` | `updateMultiFlowMapText()` |
| Double Bubble Map | `'left'`, `'right'` | `spec.left`, `spec.right` | `updateDoubleBubbleMapText()` |
| Bridge Map | `'dimension'` | `spec.dimension`, `spec.analogies[]` | `updateBridgeMapText()` |
| Mind Map | `'topic'` | `spec.topic` | `updateGenericNodeText()` |
| Concept Map | `'node'` | Various | (Various methods) |

⚠️ Circle Map uses `'center'` instead of `'topic'` - this is handled by checking both in the code.

---

## Quick Reference for Future Development

### When Adding New Diagram Types

**1. Choose Node Type Name:**
- Prefer `'topic'` for consistency
- Use specific names only if semantically different (e.g., `'event'`, `'title'`)

**2. In Renderer:**
```javascript
svg.append('text')
    .attr('data-node-type', 'topic')  // Match this name
    .text(spec.topic);
```

**3. In Interactive-Editor:**
```javascript
updateYourMapText(nodeId, shapeNode, newText) {
    const nodeType = d3.select(shapeNode).attr('data-node-type');
    
    if (nodeType === 'topic') {  // Match renderer!
        this.currentSpec.topic = newText;  // Update spec!
    }
}
```

**4. In Toolbar-Manager:**
```javascript
// In identifyMainTopic()
if (diagramType === 'your_map') {
    if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
        return spec.topic;  // Match spec field!
    }
}
```

**Golden Rule:** Renderer → Spec Update → Auto-Complete must use matching names!

---

## How to Debug Auto-Complete Issues

### Symptom: Auto-Complete Sends Wrong Topic

**Step 1: Check if spec is updating**
```javascript
// In browser console after editing main topic:
window.interactiveEditor?.currentSpec?.topic  // or .title, .event, etc.
```

**If spec is NOT updating:**
- Problem is in `interactive-editor.js`
- Check that `updateXxxMapText()` checks correct `nodeType`
- Check that it updates correct `spec` field

**If spec IS updating but auto-complete still wrong:**
- Problem is in `toolbar-manager.js`
- Check that `identifyMainTopic()` has Strategy 1 block for this diagram
- Check that it reads correct `spec` field

**Step 2: Add debug logging**
```javascript
// In identifyMainTopic(), add before return:
console.log('[DEBUG] Identified topic:', mainTopic, 'for', diagramType);
console.log('[DEBUG] Spec:', spec);
```

**Step 3: Check backend logs**
```
DEBUG | AGNT | User prompt: <should match what you typed>
```

---

## Timeline Summary

### ✅ Phase 1: Middleware Integration - COMPLETE
- All 10 agents migrated to use `LLMServiceWrapper`
- Benefits: error handling, retry, performance tracking, rate limiting

### ✅ Phase 2: Parallel Auto-Complete - COMPLETE
- Frontend calls `/api/generate_multi_parallel`
- Backend runs all 4 LLMs in parallel using `asyncio.gather`
- 75% time reduction (from ~38s sequential to ~15s parallel)

### ✅ Phase 3: Circle Map Fix - COMPLETE
- Fixed `updateCircleMapText()` to check `'topic' || 'center'`
- Fixed `identifyMainTopic()` to check `'topic' || 'center'` in DOM
- Auto-complete now works correctly for Circle Map

### 🚧 Phase 4: Flow/Multi-Flow Fix - THIS DOCUMENT
- Add Strategy 1 for Flow Map checking `spec.title`
- Add Strategy 1 for Multi-Flow Map checking `spec.event`
- Complete auto-complete consistency across all diagrams

### 🚧 Phase 5: Remove Wrapper - THIS DOCUMENT
- Simplify architecture by removing `LLMServiceWrapper`
- Use `llm_service` directly in all agents
- ~220 lines of code removed
- Cleaner, faster, more maintainable

---

## Related Documentation

- **Circle Map Fix Reference:** `docs/CIRCLE_MAP_SPEC_UPDATE_FIX.md`
- **Middleware Architecture:** `docs/THINKGUIDE_ARCHITECTURE.md`
- **Parallel Auto-Complete:** `CHANGELOG.md` (Oct 10, 2025 entries)
- **LLM Service Docs:** `docs/LLM_SERVICE_PHASE4_COMPLETE.md`

---

## Status: READY FOR IMPLEMENTATION ✅

**Document Version:** 4.0 (Fully Reorganized - Linear Step-by-Step)  
**Last Updated:** October 10, 2025  
**Author:** lycosa9527, MindSpring Team

**Changelog:**
- v4.0: Complete reorganization - true linear step-by-step flow
- v3.0: Added Phase 5 backend refactoring (remove wrapper)
- v2.0: Added Phase 4 frontend fixes (Flow/Multi-Flow auto-complete)
- v1.0: Initial middleware audit and Circle Map analysis
