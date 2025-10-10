# Middleware Migration Plan - Complete Node Type Fix

**Date:** October 10, 2025  
**Author:** lycosa9527, MindSpring Team  
**Status:** 🚧 ACTIONABLE - READY FOR IMPLEMENTATION  
**Reference:** `docs/CIRCLE_MAP_SPEC_UPDATE_FIX.md`

---

## 📋 Executive Summary

This document provides **detailed, step-by-step instructions** to fix auto-complete for Flow Map and Multi-Flow Map diagrams. These diagrams have the same bug that Circle Map had - `identifyMainTopic()` doesn't check their main topic fields in Strategy 1.

**Problem Pattern** (Same as Circle Map):
1. User edits main topic �?spec is updated correctly �?
2. User triggers auto-complete �?`identifyMainTopic()` doesn't check the right spec field �?
3. Falls back to Strategy 2 (less reliable) instead of using Strategy 1 (spec source of truth)
4. Auto-complete may send wrong/stale topic to LLMs

**Solution Pattern** (Follow Circle Map Fix):
- Add Strategy 1 handling for Flow Map and Multi-Flow Map
- Check their specific spec fields (`spec.title` and `spec.event`)
- Same as we did for Circle Map's `spec.topic`

---

## 🎯 Goals

1. �?**COMPLETE:** All diagram agents use LLM middleware through `LLMServiceWrapper`
2. 🚧 **IN PROGRESS:** Fix auto-complete for Flow Map and Multi-Flow Map
3. �?**COMPLETE:** Spec update logic verified in `interactive-editor.js`
4. 🚧 **TODO:** Test auto-complete for all diagram types
5. 📝 **TODO:** Document node type conventions

---

## 📊 Status Assessment

### �?Middleware Migration - COMPLETE!

**ALL 10 agents already use middleware** through `agents/core/agent_utils.py` �?`LLMServiceWrapper`

This was completed in earlier work. No action needed.

---

## 🔍 Code Audit Results

### Spec Update Methods - Interactive-Editor.js �?ALL CORRECT

**File:** `static/js/editor/interactive-editor.js`

| Diagram | Update Method | Checks NodeType | Updates Spec Field | Status |
|---------|--------------|-----------------|-------------------|--------|
| **Circle Map** | `updateCircleMapText()` | `'topic'` OR `'center'` | `spec.topic` | �?FIXED |
| **Bubble Map** | `updateBubbleMapText()` | `'topic'` | `spec.topic` | �?CORRECT |
| **Tree Map** | `updateTreeMapText()` | `'topic'` | `spec.topic` | �?CORRECT |
| **Brace Map** | `updateBraceMapText()` | `'topic'` | `spec.topic` | �?CORRECT |
| **Flow Map** | `updateFlowMapText()` | `'title'` | `spec.title` | �?CORRECT |
| **Multi-Flow Map** | `updateMultiFlowMapText()` | `'event'` | `spec.event` | �?CORRECT |
| **Double Bubble Map** | `updateDoubleBubbleMapText()` | `'left'`, `'right'` | `spec.left`, `spec.right` | �?CORRECT |
| **Bridge Map** | `updateBridgeMapText()` | `'dimension'`, `'left'`, `'right'` | `spec.dimension`, `spec.analogies[]` | �?CORRECT |
| **Mind Map** | `updateGenericNodeText()` | N/A (generic) | Various | ⚠️ NEEDS INVESTIGATION |

**Conclusion:** Spec update methods are ALL correct. They properly update the spec when user edits nodes.

---

### Auto-Complete Topic Identification - Toolbar-Manager.js 🐛 ISSUES FOUND

**File:** `static/js/editor/toolbar-manager.js`  
**Method:** `identifyMainTopic()` (starts line 1638)

**Problem:** Strategy 1 (lines 1645-1661) only handles diagrams with `spec.topic`:
```javascript
if (diagramType === 'bubble_map' || diagramType === 'circle_map' || 
    diagramType === 'tree_map' || diagramType === 'brace_map') {
    if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
        return spec.topic;
    }
}
```

**Flow Map and Multi-Flow Map are NOT included!** They fall through to Strategy 2 (lines 1764-1768), which is less reliable.

| Diagram | Strategy 1? | Spec Field Checked | Status |
|---------|-------------|-------------------|--------|
| Circle Map | �?Yes (line 1647) | `spec.topic` | �?FIXED |
| Bubble Map | �?Yes (line 1647) | `spec.topic` | �?CORRECT |
| Tree Map | �?Yes (line 1648) | `spec.topic` | �?CORRECT |
| Brace Map | �?Yes (line 1648) | `spec.topic` | �?CORRECT |
| Double Bubble Map | �?Yes (line 1665) | `spec.left`, `spec.right` | �?CORRECT |
| Bridge Map | �?Yes (line 1676) | `spec.analogies[0]` | �?CORRECT |
| Mind Map | �?Yes (line 1689) | `spec.topic` | �?CORRECT |
| **Flow Map** | �?NO | Falls to Strategy 2 | 🐛 **NEEDS FIX** |
| **Multi-Flow Map** | �?NO | Falls to Strategy 2 | 🐛 **NEEDS FIX** |

**Root Cause:** Same pattern as Circle Map bug - Strategy 1 doesn't check the right spec fields!

---

## 🔧 IMPLEMENTATION INSTRUCTIONS

### Reference Pattern: Circle Map Fix

**Circle Map was fixed by:**
1. File: `static/js/editor/interactive-editor.js` line 1448
2. Changed: `if (nodeType === 'topic')` �?`if (nodeType === 'topic' || nodeType === 'center')`

**That fix was for spec UPDATE. Our fixes are for spec READING in auto-complete.**

---

## 🎯 FIX #1: Flow Map Auto-Complete

###Problem
When user edits Flow Map title and triggers auto-complete, `identifyMainTopic()` doesn't check `spec.title` in Strategy 1. It falls through to Strategy 2 which may return stale data.

### Solution
Add Strategy 1 handling for Flow Map, similar to how we handle Bubble/Circle/Tree/Brace maps.

### File to Modify
`static/js/editor/toolbar-manager.js`

### Location
After line 1661 (after the bubble/circle/tree/brace Strategy 1 block)

### Exact Code Change

**FIND THIS CODE (lines 1662-1672):**
```javascript
        }
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        // CONSISTENCY FIX: Like bridge_map, use spec as source of truth
        if (diagramType === 'double_bubble_map') {
            if (spec && spec.left && spec.right) {
                const combinedTopic = `${spec.left} vs ${spec.right}`;
                return combinedTopic;
            }
            logger.warn('ToolbarManager', 'Double bubble map: No valid left/right topics in spec');
        }
```

**INSERT BEFORE "Strategy 1b" (after line 1661, before line 1663):**
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

**Result:** Flow Map now gets Strategy 1 (highest priority) handling, using `spec.title` as source of truth.

---

## 🎯 FIX #2: Multi-Flow Map Auto-Complete

### Problem
When user edits Multi-Flow Map event and triggers auto-complete, `identifyMainTopic()` doesn't check `spec.event` in Strategy 1. It falls through to Strategy 2.

### Solution
Add Strategy 1 handling for Multi-Flow Map.

### File to Modify
`static/js/editor/toolbar-manager.js`

### Location
After the Flow Map fix we just added (after line 1661 + the new Flow Map block)

### Exact Code Change

**INSERT AFTER the Flow Map block we just added:**
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

**Result:** Multi-Flow Map now gets Strategy 1 handling, using `spec.event` as source of truth.

---

## 📋 Complete Code Change Summary

**File:** `static/js/editor/toolbar-manager.js`  
**Method:** `identifyMainTopic()`  
**Location:** After line 1661

**Add TWO new Strategy 1 blocks:**

```javascript
// Existing code ends at line 1661:
        }
        
        // ===== NEW CODE STARTS HERE =====
        
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
        
        // ===== NEW CODE ENDS HERE =====
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        // (existing code continues...)
```

---

## �?Verification Steps

### Test Flow Map

1. **Create or open a Flow Map**
2. **Edit the title** (the main topic box at the top)
   - Type a new title, e.g., "软件开发流�?
   - Press Enter or click away
3. **Verify spec update:**
   - Open browser DevTools console
   - Type: `window.interactiveEditor?.currentSpec?.title`
   - Should show: "软件开发流�? �?
4. **Trigger auto-complete** (click auto-complete button)
5. **Check backend logs:**
   ```
   INFO  | ToolbarManager | Main topic identified: "软件开发流�?
   DEBUG | AGNT | User prompt: 软件开发流�?
   ```
   **NOT** the old/default title

### Test Multi-Flow Map

1. **Create or open a Multi-Flow Map**
2. **Edit the central event** (the middle box)
   - Type a new event, e.g., "数字化转�?
   - Press Enter or click away
3. **Verify spec update:**
   - Open browser DevTools console
   - Type: `window.interactiveEditor?.currentSpec?.event`
   - Should show: "数字化转�? �?
4. **Trigger auto-complete**
5. **Check backend logs:**
   ```
   INFO  | ToolbarManager | Main topic identified: "数字化转�?
   DEBUG | AGNT | User prompt: 数字化转�?
   ```
   **NOT** the old/default event

### Expected Behavior (After Fix)

| Action | Expected Result |
|--------|----------------|
| User edits Flow Map title | `spec.title` updates immediately |
| Auto-complete triggered | `identifyMainTopic()` returns `spec.title` |
| Backend logs show | Correct title sent to LLMs |
| All 4 LLMs receive | Correct parallel prompts |
| User edits Multi-Flow event | `spec.event` updates immediately |
| Auto-complete triggered | `identifyMainTopic()` returns `spec.event` |
| Backend logs show | Correct event sent to LLMs |

---

## 🧪 Complete Testing Checklist

After implementing the fixes, test ALL diagram types:

- [ ] **Bubble Map** - Edit topic �?auto-complete uses new topic
- [ ] **Circle Map** - Edit center �?auto-complete uses new topic �?(Already fixed)
- [ ] **Tree Map** - Edit topic �?auto-complete uses new topic
- [ ] **Brace Map** - Edit topic �?auto-complete uses new topic
- [ ] **Flow Map** - Edit title �?auto-complete uses new title 🔧 (This fix)
- [ ] **Multi-Flow Map** - Edit event �?auto-complete uses new event 🔧 (This fix)
- [ ] **Double Bubble Map** - Edit left/right �?auto-complete uses both
- [ ] **Bridge Map** - Edit first analogy �?auto-complete uses it
- [ ] **Mind Map** - Edit topic �?auto-complete uses new topic
- [ ] **Concept Map** - Edit topic �?auto-complete uses new topic

---

## 📝 Why This Fix Works

### The Pattern (Learned from Circle Map)

1. **Spec Update is Correct** �?
   - `updateFlowMapText()` already checks `nodeType === 'title'` and updates `spec.title`
   - `updateMultiFlowMapText()` already checks `nodeType === 'event'` and updates `spec.event`

2. **Problem is in Topic Identification** �?
   - `identifyMainTopic()` didn't check these spec fields in Strategy 1
   - Fell through to Strategy 2 (fallback) which is less reliable

3. **Solution: Add Strategy 1 Handling** �?
   - Check the correct spec fields (`spec.title`, `spec.event`)
   - Use spec as source of truth (highest priority)
   - Fallback to DOM only if spec not available

### Why Strategy 1 is Better Than Strategy 2

**Strategy 1:**
- Checked FIRST (highest priority)
- Uses spec directly (source of truth)
- Reliable and fast

**Strategy 2:**
- Only reached if Strategy 1 fails
- Uses switch/case fallback logic
- May have edge cases

By adding Flow/Multi-Flow to Strategy 1, we ensure they get the same reliable handling as other diagrams.

---

## 🎯 Summary

### What We're Fixing

**2 diagram types** that don't get Strategy 1 handling:
1. Flow Map - needs to check `spec.title`
2. Multi-Flow Map - needs to check `spec.event`

### How We're Fixing It

Add 2 new Strategy 1 blocks in `identifyMainTopic()`:
- After line 1661 in `toolbar-manager.js`
- Before the existing "Strategy 1b" (double bubble map)
- Following the same pattern as bubble/circle/tree/brace maps

### Why This Works

- Spec update methods are already correct (no changes needed)
- We're just making auto-complete check the right spec fields
- Same successful pattern we used for Circle Map

### Expected Outcome

- �?Flow Map auto-complete uses current title (not stale data)
- �?Multi-Flow Map auto-complete uses current event (not stale data)
- �?All 10 diagram types work correctly with auto-complete
- �?Consistent Strategy 1 handling across all diagrams

---

## 🐛 Node Type Audit - Status

### Circle Map Issue - FIXED �?

**Problem:** Circle Map renderer set `data-node-type='center'` but `updateCircleMapText()` only checked for `nodeType === 'topic'`, causing spec to never update.

**Fix:** Changed condition to `if (nodeType === 'topic' || nodeType === 'center')` in `interactive-editor.js` line 1448.

**Reference:** `docs/CIRCLE_MAP_SPEC_UPDATE_FIX.md`

### All Other Diagrams - CORRECT �?

After audit, all other diagram types have matching node types between renderer and spec update methods:
- Bubble Map: `'topic'` �?
- Tree Map: `'topic'` �?
- Brace Map: `'topic'` �?
- Flow Map: `'title'` �?
- Multi-Flow Map: `'event'` �?
- Double Bubble Map: `'left'`, `'right'` �?
- Bridge Map: `'dimension'`, `'left'`, `'right'` �?

**No additional node type fixes needed.**

### 📋 Complete Node Type Inventory

| Diagram Type | Main Topic Node Type | Other Node Types | Spec Update Method |
|--------------|---------------------|------------------|-------------------|
| Bubble Map | `'topic'` | `'adjective'` | `updateBubbleMapText()` |
| Circle Map | `'center'` ⚠️ | `'context'` | `updateCircleMapText()` |
| Tree Map | `'topic'` | `'category'`, `'item'` | `updateTreeMapText()` |
| Brace Map | `'topic'` | `'category'`, `'detail'` | `updateBraceMapText()` |
| Flow Map | `'title'` | `'step'`, `'substep'` | `updateFlowMapText()` |
| Multi-Flow Map | `'event'` | `'cause'`, `'effect'` | `updateMultiFlowMapText()` |
| Double Bubble Map | `'left'`, `'right'` | `'shared'`, `'unique_left'`, `'unique_right'` | `updateDoubleBubbleMapText()` |
| Bridge Map | `'dimension'` | `'left'`, `'right'` | `updateBridgeMapText()` |
| Mind Map | `'topic'` | Generic nodes | `updateGenericNodeText()` |
| Concept Map | `'node'` | Generic nodes, edges | (Various methods) |

⚠️ **Note:** Circle Map uses `'center'` instead of `'topic'` - this is now handled correctly after the fix.

---

## 📚 Quick Reference for Future Development

### When Adding New Diagram Types

1. **Choose a Node Type Name** for the main topic
   - Prefer `'topic'` for consistency
   - Use specific names only if semantically different (e.g., `'event'`, `'title'`)

2. **In Renderer:** Set `data-node-type` attribute
   ```javascript
   svg.append('text')
       .attr('data-node-type', 'topic')  // or 'event', 'title', etc.
       .text(spec.topic);
   ```

3. **In Interactive-Editor:** Create update method
   ```javascript
   updateYourMapText(nodeId, shapeNode, newText) {
       const nodeType = d3.select(shapeNode).attr('data-node-type');
       
       if (nodeType === 'topic') {  // Match renderer!
           this.currentSpec.topic = newText;  // Update spec!
       }
       // ... update other node types
   }
   ```

4. **In Toolbar-Manager:** Add Strategy 1 handling
   ```javascript
   // In identifyMainTopic()
   if (diagramType === 'your_map') {
       if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
           return spec.topic;  // Match spec field!
       }
   }
   ```

### The Golden Rule

**Renderer �?Spec Update �?Auto-Complete must all use matching names:**
- Renderer sets `data-node-type='X'`
- Spec update checks `nodeType === 'X'` �?updates `spec.Y`
- Auto-complete checks `spec.Y`

---

## 🔍 How to Debug Auto-Complete Issues

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

## 📈 Timeline Summary

### Phase 1: Middleware Integration �?COMPLETE
- All 10 agents migrated to use `LLMServiceWrapper`
- No direct LLM client calls anymore
- All benefits: error handling, retry, performance tracking, rate limiting

### Phase 2: Parallel Auto-Complete �?COMPLETE
- Frontend calls `/api/generate_multi_parallel`
- Backend runs all 4 LLMs in parallel using `asyncio.gather`
- 75% time reduction (from ~38s sequential to ~15s parallel)

### Phase 3: Circle Map Fix �?COMPLETE
- Fixed `updateCircleMapText()` to check `'topic' || 'center'`
- Fixed `identifyMainTopic()` to check `'topic' || 'center'` in DOM
- Auto-complete now works correctly for Circle Map

### Phase 4: Flow/Multi-Flow Fix 🚧 FRONTEND FIXES
- Add Strategy 1 for Flow Map checking `spec.title`
- Add Strategy 1 for Multi-Flow Map checking `spec.event`
- Complete auto-complete consistency across all diagrams

### Phase 5: Remove Wrapper 🚧 BACKEND REFACTORING
- **Simplify Architecture**: Remove `LLMServiceWrapper`, use `llm_service` directly
- **Performance**: Eliminate unnecessary message list conversion overhead
- **Maintainability**: 50% less code, clearer intent, better type safety
- **Impact**: Refactor all 10 agent files to call middleware natively
- **Details**: See "Phase 5: Remove Wrapper Refactoring" section below

### Phase 6: Testing 📝 TODO
- Test auto-complete for all 10 diagram types
- Verify spec updates when editing main topics
- Verify correct prompts sent to LLMs
- Verify direct middleware calls work correctly

---

## 🔧 PHASE 5: Remove Wrapper Refactoring

### Problem: Unnecessary Abstraction Layer

**Current Architecture:**
```
Agent → LLMServiceWrapper → llm_service → LLM Client
```

**What happens:**
1. Agent builds `messages = [{'role': 'system', ...}, {'role': 'user', ...}]`
2. Calls `wrapper.chat_completion(messages)`
3. **Wrapper tears apart the messages list** to extract system/user prompts
4. Calls `llm_service.chat(prompt=user_prompt, system_message=system_message)`

**This is inefficient!** We're building a list just to deconstruct it immediately.

---

### Solution: Direct Middleware Usage

**Simplified Architecture:**
```
Agent → llm_service → LLM Client
```

**Direct approach:**
1. Agent has system_prompt and user_prompt as strings
2. Calls `llm_service.chat(prompt=user_prompt, system_message=system_prompt)` directly
3. No wrapper, no message list conversion, no overhead

**Benefits:**
- ✅ **50% less code** - Remove 100+ lines of wrapper logic
- ✅ **Better performance** - No list construction/deconstruction
- ✅ **Clearer intent** - Direct middleware usage
- ✅ **Easier maintenance** - Fewer abstractions
- ✅ **Type safety** - Direct parameter passing

---

### Refactoring Pattern

#### BEFORE (With Wrapper):
```python
# agents/thinking_maps/circle_map_agent.py

async def _generate_circle_map_spec(self, prompt: str, language: str):
    from prompts import get_prompt
    from config.settings import config
    
    # Get prompts
    system_prompt = get_prompt("circle_map_agent", language, "generation")
    user_prompt = f"请为以下描述创建一个圆圈图：{prompt}"
    
    # Build messages list
    messages = config.prepare_llm_messages(system_prompt, user_prompt, model='qwen')
    
    # Call wrapper (which will tear apart the messages)
    response = await self.llm_client.chat_completion(messages)
    
    return response
```

#### AFTER (Direct Middleware):
```python
# agents/thinking_maps/circle_map_agent.py

async def _generate_circle_map_spec(self, prompt: str, language: str):
    from prompts import get_prompt
    from services.llm_service import llm_service
    
    # Get prompts
    system_prompt = get_prompt("circle_map_agent", language, "generation")
    user_prompt = f"请为以下描述创建一个圆圈图：{prompt}"
    
    # Call middleware directly - clean and simple!
    response = await llm_service.chat(
        prompt=user_prompt,
        model=self.model or 'qwen',
        system_message=system_prompt,
        max_tokens=1000,
        temperature=1.0
    )
    
    return response
```

**Changes:**
- ❌ Remove: `config.prepare_llm_messages()`, `self.llm_client`
- ✅ Add: Direct `llm_service.chat()` call
- 📉 Lines: 6 → 4 (33% reduction)

---

### Step-by-Step Refactoring

#### Step 1: Update Agent Base Class

**File:** `agents/core/base_agent.py`

**FIND AND REMOVE:**
```python
def __init__(self):
    from agents.core.agent_utils import get_llm_client
    self.llm_client = get_llm_client(model_id='qwen')
```

**REPLACE WITH:**
```python
def __init__(self):
    # Model ID for this agent - can be overridden per request
    self.model = 'qwen'
```

**Rationale:** Agents don't need a client instance anymore. They'll call `llm_service` directly.

---

#### Step 2: Update Circle Map Agent

**File:** `agents/thinking_maps/circle_map_agent.py`

**Lines 71-89** - Change the LLM call:

**FIND:**
```python
async def _generate_circle_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
    try:
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
async def _generate_circle_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
    try:
        from prompts import get_prompt
        from services.llm_service import llm_service
        
        system_prompt = get_prompt("circle_map_agent", language, "generation")
        
        if not system_prompt:
            logger.error(f"CircleMapAgent: No prompt found for language {language}")
            return None
            
        user_prompt = f"请为以下描述创建一个圆圈图：{prompt}" if language == "zh" else f"Please create a circle map for the following description: {prompt}"
        
        # Call middleware directly - simple and efficient!
        response = await llm_service.chat(
            prompt=user_prompt,
            model=self.model,
            system_message=system_prompt,
            max_tokens=1000,
            temperature=1.0
        )
```

---

#### Step 3: Apply Pattern to All Agents

**Files to Update (10 files):**
1. `agents/thinking_maps/bubble_map_agent.py`
2. `agents/thinking_maps/circle_map_agent.py`
3. `agents/thinking_maps/tree_map_agent.py`
4. `agents/thinking_maps/brace_map_agent.py`
5. `agents/thinking_maps/flow_map_agent.py`
6. `agents/thinking_maps/multi_flow_map_agent.py`
7. `agents/thinking_maps/double_bubble_map_agent.py`
8. `agents/thinking_maps/bridge_map_agent.py`
9. `agents/mind_maps/mind_map_agent.py`
10. `agents/concept_maps/concept_map_agent.py`

**Pattern to apply in each:**
```python
# REMOVE these imports:
from config.settings import config

# ADD this import:
from services.llm_service import llm_service

# REPLACE this pattern:
messages = config.prepare_llm_messages(system_prompt, user_prompt, model=MODEL_ID)
response = await self.llm_client.chat_completion(messages)

# WITH this pattern:
response = await llm_service.chat(
    prompt=user_prompt,
    model=self.model,
    system_message=system_prompt,
    max_tokens=1000,
    temperature=1.0  # Adjust per diagram type if needed
)
```

---

#### Step 4: Remove Wrapper Class

**File:** `agents/core/agent_utils.py`

**REMOVE entirely (lines 23-130):**
```python
class LLMServiceWrapper:
    """..."""
    # All 100+ lines of wrapper code
```

**REMOVE (lines ~135-145):**
```python
def get_llm_client(model_id='qwen'):
    """..."""
    logger.info(f"get_llm_client() - Creating LLMServiceWrapper for model: {model_id}")
    return LLMServiceWrapper(model_id=model_id)
```

**Result:** Remove ~120 lines of unnecessary abstraction!

---

#### Step 5: Remove Wrapper Tests

**File:** `tests/test_agent_middleware_integration.py`

**Action:** Delete this file (it only tests the wrapper, which we're removing)

**Alternative:** Rename to `tests/test_agent_direct_middleware.py` and update tests to verify agents call `llm_service` directly.

---

### Migration Checklist

#### Phase 5.1: Base Agent
- [ ] Update `agents/core/base_agent.py` - Remove `llm_client`, add `model` attribute

#### Phase 5.2: Thinking Map Agents (8 agents)
- [ ] `bubble_map_agent.py` - Direct middleware call
- [ ] `circle_map_agent.py` - Direct middleware call
- [ ] `tree_map_agent.py` - Direct middleware call
- [ ] `brace_map_agent.py` - Direct middleware call
- [ ] `flow_map_agent.py` - Direct middleware call
- [ ] `multi_flow_map_agent.py` - Direct middleware call
- [ ] `double_bubble_map_agent.py` - Direct middleware call
- [ ] `bridge_map_agent.py` - Direct middleware call

#### Phase 5.3: Other Agents (2 agents)
- [ ] `mind_maps/mind_map_agent.py` - Direct middleware call
- [ ] `concept_maps/concept_map_agent.py` - Direct middleware call

#### Phase 5.4: Cleanup
- [ ] Remove `LLMServiceWrapper` from `agent_utils.py`
- [ ] Remove `get_llm_client()` from `agent_utils.py`
- [ ] Update or remove `tests/test_agent_middleware_integration.py`

#### Phase 5.5: Testing
- [ ] Test each diagram type generation
- [ ] Verify middleware features still work (retries, circuit breaker, etc.)
- [ ] Check performance (should be slightly faster)
- [ ] Verify all unit tests pass

---

### Expected Impact

**Code Reduction:**
- Remove ~120 lines from `agent_utils.py`
- Simplify ~100 lines across 10 agent files
- **Total:** ~220 lines removed ≈ 3-4% codebase reduction

**Performance:**
- Eliminate message list construction overhead
- ~5-10% faster agent calls (micro-optimization)

**Maintainability:**
- Direct middleware usage is more explicit
- Easier for new developers to understand
- Fewer abstractions = fewer bugs

---

### Risk Assessment

**Low Risk:**
- ✅ Middleware is battle-tested and production-ready
- ✅ No functionality changes - just removing a layer
- ✅ Easy to rollback if issues arise

**Testing Required:**
- Full integration test of all 10 diagram types
- Verify error handling still works
- Check that model selection works correctly
- Ensure temperature/max_tokens parameters are passed through

---

## 🎯 FINAL ACTION ITEMS

### Phase 4: Frontend Fixes (Immediate Priority)

**Objective:** Fix Flow Map and Multi-Flow Map auto-complete

1. **Open File:** `static/js/editor/toolbar-manager.js`

2. **Find Line 1661:** End of bubble/circle/tree/brace Strategy 1 block
   ```javascript
           }
           
           // Strategy 1b: For double bubble maps...
   ```

3. **Insert TWO blocks BETWEEN line 1661 and "Strategy 1b":**
   - Copy the complete code from section "📋 Complete Code Change Summary" above
   - This adds Strategy 1 for Flow Map and Multi-Flow Map

4. **Save and Test:**
   - Hard refresh browser (Ctrl+Shift+R)
   - Test Flow Map: edit title → auto-complete
   - Test Multi-Flow Map: edit event → auto-complete
   - Check backend logs for correct prompts

**Success Criteria:**
- ✅ Flow Map auto-complete uses current title (verify in logs)
- ✅ Multi-Flow Map auto-complete uses current event (verify in logs)
- ✅ All 10 diagram types work with auto-complete
- ✅ No regression in existing diagrams

---

### Phase 5: Backend Refactoring (After Phase 4)

**Objective:** Remove `LLMServiceWrapper`, use middleware directly

#### Step-by-Step Execution:

**5.1 Base Agent (1 file)**
1. Open: `agents/core/base_agent.py`
2. Remove: `self.llm_client = get_llm_client(model_id='qwen')`
3. Add: `self.model = 'qwen'`

**5.2 Circle Map Agent (Example - Apply to all 10)**
1. Open: `agents/thinking_maps/circle_map_agent.py`
2. Remove import: `from config.settings import config`
3. Add import: `from services.llm_service import llm_service`
4. Replace LLM call pattern (see Phase 5 section above for exact code)

**5.3 Apply to All Agents (Repeat 5.2 for each):**
- `bubble_map_agent.py`
- `tree_map_agent.py`
- `brace_map_agent.py`
- `flow_map_agent.py`
- `multi_flow_map_agent.py`
- `double_bubble_map_agent.py`
- `bridge_map_agent.py`
- `mind_maps/mind_map_agent.py`
- `concept_maps/concept_map_agent.py`

**5.4 Remove Wrapper**
1. Open: `agents/core/agent_utils.py`
2. Delete: `class LLMServiceWrapper` (lines 23-130)
3. Delete: `def get_llm_client()` function
4. Keep: Other utility functions (`extract_json_from_response`, etc.)

**5.5 Testing**
1. Run: `pytest tests/services/` (middleware tests should still pass)
2. Test each diagram type via UI
3. Verify middleware features (error handling, retries) work
4. Check performance (should be slightly faster)

**Success Criteria:**
- ✅ All 10 diagram types generate correctly
- ✅ Middleware error handling/retries still work
- ✅ ~220 lines of code removed
- ✅ All tests pass
- ✅ No functionality changes - just cleaner architecture

---

## 📖 Related Documentation

- **Circle Map Fix Reference:** `docs/CIRCLE_MAP_SPEC_UPDATE_FIX.md`
- **Middleware Architecture:** `docs/THINKGUIDE_ARCHITECTURE.md`
- **Parallel Auto-Complete:** `CHANGELOG.md` (Oct 10, 2025 entries)
- **LLM Service Docs:** `docs/LLM_SERVICE_PHASE4_COMPLETE.md`

---

## STATUS: READY FOR IMPLEMENTATION

### Phase 4 (Frontend) - READY
- Exact file paths and line numbers
- Complete code blocks to add
- Clear testing instructions
- Reference to Circle Map fix pattern

### Phase 5 (Backend) - READY
- Step-by-step refactoring guide
- Before/after code examples for each change
- Complete migration checklist for all 10 agents
- Risk assessment and testing strategy

**Implementation Order:**
1. **Phase 4 First** - Fix Flow/Multi-Flow auto-complete (frontend, low risk, immediate benefit)
2. **Phase 5 Second** - Remove wrapper (backend, simplification, better architecture)

**Cursor can now use this document to implement both phases systematically.**

---

**Document Version:** 3.0 (Added Phase 5: Remove Wrapper Refactoring)  
**Last Updated:** October 10, 2025  
**Author:** lycosa9527, MindSpring Team

**Changelog:**
- v3.0: Added Phase 5 backend refactoring (remove wrapper, use middleware natively)
- v2.0: Added Phase 4 frontend fixes (Flow Map & Multi-Flow Map auto-complete)
- v1.0: Initial middleware audit and Circle Map analysis
