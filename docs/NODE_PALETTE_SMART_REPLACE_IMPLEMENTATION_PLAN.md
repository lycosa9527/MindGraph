# Node Palette Smart Replace Implementation Plan

**Goal**: Make Node Palette work like Auto-Complete - intelligently replace template placeholders instead of just appending nodes.

**Author**: lycosa9527  
**Made by**: MindSpring Team  
**Date**: October 14, 2025
**Last Updated**: October 14, 2025 (Final Code Review Complete)

---

## 📋 Executive Summary

### ✅ What's Already Done (No Action Needed)
1. **Verbose Logging** - Complete tracking from backend generation → frontend reception → template addition → DOM rendering
2. **Node Lifecycle Tracking** - Full tracking of `selected` and `added_to_diagram` flags throughout the system
3. **Bug Fix** - The "[object Object]" bug is fixed (line 813 pushes strings, not objects)
4. **Multi-Diagram Support** - Metadata system supports 10 diagram types with correct terminology
5. **Centralized Placeholders** - `DiagramValidator` class exists with comprehensive placeholder patterns

### ⚠️ What Needs Implementation (This Plan)
1. **🐛 Critical Bug Fix** (30 sec) - Line 329 in `routers/thinking.py` calls non-existent function
2. **Backend Modularization** (1-2 hrs) - Refactor single file into base + diagram-specific classes
3. **Cancel Button** (30 min) - Add quit functionality to Node Palette
4. **Smart Replace Logic** (2-3 hrs) - Implement 3 strategies (REPLACE/SMART_REPLACE/APPEND)
5. **Placeholder Patterns** (5 min) - Add "Context 1"/"背景1" patterns to DiagramValidator

**Total Time**: ~4-6 hours (modularization is biggest chunk)

---

## Phase 0: Code Review & Current State Analysis

### 📋 Summary

**What We Found** (Final Code Review):
- ✅ Node Palette infrastructure is **excellent** (backend, frontend all solid)
- ✅ **Verbose logging ALREADY IMPLEMENTED**: Complete tracking from generation to display
- ✅ **Critical bug fixed**: "[object Object]" bug resolved (line 813 pushes strings not objects)
- ✅ **Centralized placeholder system exists**: `DiagramValidator` class
- ⚠️ **To Implement**: Smart Replace logic (currently only APPEND mode - lines 796-821)
- ⚠️ **To Implement**: Add "Context" patterns to DiagramValidator
- ⚠️ **Future Work**: Context-aware generation (currently Circle Map only)

**What We're Building**:
- **Phase 2-8 (Current Scope)**: Modularization + Smart Replace for Circle Map
  - **Phase 2.0**: Backend modularization + Bug fix + Cancel button (1.5-2.5 hours)
    - Fix line 329 bug (30 sec)
    - Create `base_palette_generator.py` (shared logic)
    - Migrate to `circle_map_palette.py`
    - Add cancel button (30 min)
  - **Phase 2.1-2.3**: Smart Replace Implementation (2-3 hours) ⚠️ **NOT YET IMPLEMENTED**
    - Add "Context" patterns to DiagramValidator
    - Add `isPlaceholder()` helper method
    - Implement 3 strategies in `assembleNodesToCircleMap()`:
      - REPLACE mode: All placeholders → replace with selected
      - SMART REPLACE mode: Keep user nodes, replace placeholders
      - APPEND mode: All user nodes → append selected (current behavior)
  
- **Phase 9 (Future Work)**: Add 9 More Diagram Types
  - ✅ Backend architecture: Already done in Phase 2.0!
  - Generate different node types based on user selection
  - Hierarchical node support (substeps, sub-branches, etc.)
  - Just create 9 new palette files (1 hour each = 9 hours)

**Files to Modify**:
1. 🐛 **routers/thinking.py** Line 329 - Fix critical bug (30 sec)
2. `node_palette/` directory - Create modular structure (Phase 2.0)
3. `diagram-validator.js` - Add "Context" patterns (5 min)
4. `node-palette-manager.js` - Smart Replace logic (main work)

**📋 Code Review Complete**: All analysis is in Phase 0 sections below

---

### 0.1 Backend Node Generation (✅ COMPLETE & WORKING)

**File**: `agents/thinking_modes/node_palette_generator.py`

**Current Implementation**:
- ✅ Concurrent multi-LLM streaming (qwen, deepseek, hunyuan, kimi)
- ✅ Real-time deduplication across all LLMs
- ✅ Progressive node generation with SSE streaming
- ✅ Batch management with session tracking
- ✅ Verbose logging on node generation (lines 170-173, 207-210)

**Logging Coverage**:
```python
# Line 170-173: Node generated event
logger.info(
    "[NodePalette-Stream] Node generated | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
    llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
)

# Line 207-210: Final node in stream
logger.info(
    "[NodePalette-Complete] Final node | LLM: %s | Batch: %d | ID: %s | Text: '%s'",
    llm_name, batch_num, node['id'], node_text[:50] + ('...' if len(node_text) > 50 else '')
)
```

**Node Object Structure** (Generated):
```python
node = {
    'id': f"{session_id}_{llm_name}_{batch_num}_{count}",
    'text': node_text,
    'source_llm': llm_name,
    'batch_number': batch_num,
    'relevance_score': 0.8,
    'selected': False  # Initial state
}
```

**Assessment**: ✅ Backend is solid. Logging is clean and professional. No changes needed.

---

### 0.2 Frontend Node Reception & Display (✅ COMPLETE & WORKING)

**File**: `static/js/editor/node-palette-manager.js`

**SSE Event Handling** (Lines 332-397):
- ✅ Receives `batch_start`, `node_generated`, `llm_complete`, `batch_complete` events
- ✅ Handles errors gracefully
- ✅ Real-time UI updates

**✅ VERBOSE LOGGING ALREADY IMPLEMENTED** - No action needed!

**Node Reception Logging** (Lines 339-369):
```javascript
// EXCELLENT: Full node tracking on reception
console.log(`[NodePalette-Stream] ${metadata.nodeName} #${nodeCount} received:`, {
    // Node Identity
    id: data.node.id,
    text: data.node.text,
    
    // Node Metadata
    source_llm: data.node.source_llm,
    batch_number: data.node.batch_number,
    relevance_score: data.node.relevance_score,
    
    // Diagram Context
    node_type: metadata.nodeType,
    diagram_type: this.diagramType,
    target_array: metadata.arrayName,
    
    // Selection Status - TRACKED
    selected: data.node.selected,
    added_to_diagram: false,  // Not added yet
    
    // Object Structure Verification
    type: typeof data.node,
    keys: Object.keys(data.node),
    
    // Tracking Info
    total_nodes_received: nodeCount,
    current_selections: this.selectedNodes.size
});
```

**Assessment**: ✅ Reception and logging are comprehensive. Tracks all node metadata and status.

---

### 0.3 Node Selection Tracking (✅ COMPLETE & WORKING)

**File**: `static/js/editor/node-palette-manager.js`

**Selection/Deselection Logic** (Lines 488-562):

**Selection Logging** (Lines 529-553):
```javascript
console.log(`[NodePalette-Selection] ✓ Selected ${metadata.nodeName}:`, {
    // Node Identity
    id: node.id,
    text: node.text,
    source_llm: node.source_llm,
    batch: node.batch_number,
    
    // Diagram Context
    diagram_type: this.diagramType,
    node_type: metadata.nodeType,
    target_array: metadata.arrayName,
    
    // STATUS TRACKED - Changed from false → true
    selected: true,  // Just changed!
    added_to_diagram: false,  // Not added yet
    
    // Aggregate Info
    totalSelected: this.selectedNodes.size,
    totalNodes: this.nodes.length,
    selectionRate: `${((this.selectedNodes.size / this.nodes.length) * 100).toFixed(1)}%`,
    
    // Object Structure
    type: typeof node,
    keys: Object.keys(node)
});
```

**Deselection Logging** (Lines 510-521):
```javascript
console.log(`[NodePalette-Selection] ✗ Deselected ${metadata.nodeName}:`, {
    id: node.id,
    text: node.text,
    source_llm: node.source_llm,
    
    // STATUS CHANGE TRACKED
    selected: false,  // Changed from true → false
    added_to_diagram: false,
    
    totalSelected: this.selectedNodes.size,
    totalNodes: this.nodes.length
});
```

**Assessment**: ✅ Selection tracking is excellent. Status changes are clearly logged.

---

### 0.4 Node Assembly & Adding to Diagram (✅ MOSTLY COMPLETE, ⚠️ NEEDS SMART REPLACE)

**File**: `static/js/editor/node-palette-manager.js`

**Current `assembleNodesToCircleMap()` Method** (Lines 726-902):

**✅ What's Working**:
1. **Diagram Type Awareness** (Lines 734-742):
   - Uses metadata system for all 10 diagram types
   - Correctly identifies target array (context, adjectives, steps, etc.)
   - Logs diagram type and target array

2. **Editor Validation** (Lines 750-768):
   - Checks for `window.currentEditor`
   - Validates `currentSpec` exists
   - Initializes array if needed
   - Logs editor state

3. **Before/After State Logging** (Lines 782-831):
   - Logs existing nodes BEFORE modification
   - Shows type and value of each existing node
   - Tracks added node IDs
   - Shows complete final array state

4. **Correct Data Type Handling** (Lines 798-820):
   - **CRITICAL FIX**: Extracts `node.text` (string) instead of pushing full object
   - **This fixed the "[object Object]" bug**
   ```javascript
   const nodeText = node.text; // Extract just the text string
   currentSpec[arrayName].push(nodeText); // Push as string (not object!)
   ```

5. **Status Tracking** (Lines 809-820):
   - Logs status BEFORE: `selected=true, added_to_diagram=false`
   - Marks node as added: `node.added_to_diagram = true`
   - Logs status AFTER: `selected=true, added_to_diagram=true`

6. **Rendering** (Lines 834-854):
   - Tries multiple render methods: `render()`, `renderDiagram()`, `update()`
   - Handles errors gracefully
   - Logs which method was used

7. **DOM Verification** (Lines 857-866):
   - Queries rendered nodes by `data-node-type`
   - Verifies text content in DOM
   - Logs node count and details

8. **History Saving** (Lines 869-878):
   - Saves to undo/redo history
   - Uses `saveHistoryState()` or `saveHistory()`

**⚠️ What's Missing (TO IMPLEMENT IN PHASE 2.1-2.3)**:
1. **Placeholder Detection**: Need `isPlaceholder()` method using `DiagramValidator`
2. **Smart Replace Mode**: Currently only APPEND mode (lines 796-821)
3. **Strategy Logic**: Need to add detection → strategy → execution phases

**Current Code** (Lines 796-821 - APPEND only):
```javascript
// CURRENT: Simple for loop that always appends
const addedNodeIds = [];
for (let i = 0; i < selectedNodes.length; i++) {
    const node = selectedNodes[i];
    const nodeText = node.text;
    // ... logging ...
    currentSpec[arrayName].push(nodeText);  // ← Always pushes to end (APPEND mode)
    node.added_to_diagram = true;
    addedNodeIds.push(node.id);
}
```

**What We'll Add** (Phase 2.3):
```javascript
// NEW: Add BEFORE the for loop (Phase 2.3.2)
// 1. Detection phase - analyze existing nodes for placeholders
// 2. Strategy determination - choose REPLACE/SMART_REPLACE/APPEND

// NEW: REPLACE the for loop (Phase 2.3.4-2.3.6)
// 3. Execute chosen strategy
if (strategy === 'replace') { /* clear all, add selected */ }
else if (strategy === 'smart_replace') { /* keep user nodes, add selected */ }  
else { /* append (current behavior) */ }
```

**Assessment**: ✅ Logging is excellent. ✅ APPEND mode works. ⚠️ Need to add Smart Replace (Phase 2.3).

---

### 0.5 Diagram Rendering System (✅ COMPLETE & WORKING)

**Files**: 
- `static/js/editor/interactive-editor.js` (Lines 156-210)
- `static/js/renderers/bubble-map-renderer.js`

**InteractiveEditor.renderDiagram()** (Lines 156-210):
```javascript
async renderDiagram() {
    this.log('InteractiveEditor: Starting diagram render', {
        specKeys: Object.keys(this.currentSpec || {})
    });
    
    // Calls renderGraph() which dispatches to specific renderer
    await renderGraph(this.diagramType, this.currentSpec, theme, dimensions);
    
    // Adds interaction handlers
    this.addInteractionHandlers();
    this.enableZoomAndPan();
    
    // Dispatches 'diagram-rendered' event
    window.dispatchEvent(new CustomEvent('diagram-rendered'));
}
```

**CircleMap Renderer Logging** (Lines 263-281, 471-473):
```javascript
// RECEPTION LOGGING
logger.info('[CircleMap-Renderer] ========================================');
logger.info('[CircleMap-Renderer] RECEIVING SPEC FOR RENDERING');
logger.info('[CircleMap-Renderer] ========================================');
logger.info('[CircleMap-Renderer] Spec validation:', {
    hasSpec: !!spec,
    hasTopic: !!spec?.topic,
    hasContext: Array.isArray(spec?.context),
    contextCount: spec?.context?.length || 0,
    contextType: typeof spec?.context
});

if (spec?.context) {
    logger.info('[CircleMap-Renderer] Context nodes received:');
    spec.context.forEach((item, idx) => {
        logger.info(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
    });
}

// ... rendering logic ...

// COMPLETION LOGGING
logger.info('[CircleMap-Renderer] ========================================');
logger.info(`[CircleMap-Renderer] ✓ RENDERING COMPLETE: ${spec.context.length} context nodes displayed`);
logger.info('[CircleMap-Renderer] ========================================');
```

**BubbleMap Renderer Logging** (Lines 21-37, similar pattern):
- Validates spec structure
- Logs each attribute node type and value
- Confirms rendering completion

**Assessment**: ✅ Renderers are well-instrumented with verbose logging. They correctly receive and display string nodes.

---

### 0.6 Complete Node Lifecycle Tracking

**Full Journey of a Node**:

| Stage | Location | Status Flags | Logging | Assessment |
|-------|----------|--------------|---------|------------|
| 1. **Generation** | Backend Python | `selected=False` | ✅ `[NodePalette-Stream]` | ✅ Complete |
| 2. **Reception** | Frontend JS (SSE) | `selected=False, added_to_diagram=False` | ✅ `[NodePalette-Stream]` with full tracking | ✅ Complete |
| 3. **Display in Palette** | Node card appended | Same | ✅ `[NodePalette-Append]` | ✅ Complete |
| 4. **User Selection** | Toggle click | `selected=True, added_to_diagram=False` | ✅ `[NodePalette-Selection] ✓` | ✅ Complete |
| 5. **Finish Click** | Button click | Same | ✅ `[NodePalette-Finish]` | ✅ Complete |
| 6. **Assembly** | `assembleNodesToCircleMap()` | `selected=True, added_to_diagram=True` | ✅ `[NodePalette-Assemble]` with before/after | ✅ Complete |
| 7. **Spec Update** | `currentSpec[arrayName].push(text)` | Same | ✅ Shows array before/after | ✅ Complete |
| 8. **Rendering** | `editor.render()` | Same | ✅ `[NodePalette-Assemble] Rendering...` | ✅ Complete |
| 9. **Renderer Reception** | Circle/Bubble Map renderer | N/A | ✅ `[CircleMap-Renderer]` with type checks | ✅ Complete |
| 10. **DOM Display** | SVG elements created | N/A | ✅ DOM verification logs | ✅ Complete |

**Assessment**: ✅ **EXCELLENT!** Complete end-to-end tracking from generation to display.

---

### 0.7 Log Quality Analysis

**Current Logging Standards**:
- ✅ Clean and professional (no unnecessary emojis)
- ✅ Consistent prefixes: `[NodePalette-Stream]`, `[NodePalette-Selection]`, etc.
- ✅ Structured data with clear labels
- ✅ Before/After comparisons
- ✅ Status change tracking (false → true)
- ✅ Type verification (typeof checks)
- ✅ Diagram-type aware (uses metadata)
- ✅ Multi-language support mentioned

**Sample Log Flow** (What you'd see in console):
```
[NodePalette-Stream] Context node #1 received: {...}
[NodePalette-Append] Appending context node to this.nodes array: {...}
[NodePalette-Selection] ✓ Selected context node: {selected: true, added_to_diagram: false, ...}
[NodePalette-Finish] USER CLICKED FINISH BUTTON
[NodePalette-Finish] Selected: 5/20 | Batches: 2 | Rate: 25.0%
[NodePalette-Assemble] ASSEMBLING CONTEXT NODES TO CIRCLE_MAP
[NodePalette-Assemble] BEFORE: spec.context has 8 items
[NodePalette-Assemble]   [0] "Context 1" → "Photosynthesis"
[NodePalette-Assemble]   Status BEFORE: selected=true, added_to_diagram=false
[NodePalette-Assemble]   ✓ Pushed to spec.context[8]
[NodePalette-Assemble]   Status AFTER: selected=true, added_to_diagram=true ✓
[NodePalette-Assemble] AFTER: spec.context has 13 items (+5)
[NodePalette-Assemble] Rendering diagram...
[NodePalette-Assemble] ✓ editor.render() completed
[CircleMap-Renderer] RECEIVING SPEC FOR RENDERING
[CircleMap-Renderer] Context nodes received:
  [8] Type: string | Value: Photosynthesis
[CircleMap-Renderer] ✓ RENDERING COMPLETE: 13 context nodes displayed
```

**Assessment**: ✅ **OUTSTANDING!** Logging is comprehensive, clean, and tells the complete story.

---

### 0.8 Missing Features (To Implement)

Based on the code review, here's what we need to add:

| Feature | Current State | Required Action | Priority |
|---------|---------------|-----------------|----------|
| **Placeholder Detection** | ❌ Not implemented | Add `isPlaceholder()` method | 🔴 HIGH |
| **Language Detection** | ❌ Not implemented | Add language detection for EN/ZH patterns | 🔴 HIGH |
| **Smart Replace Mode** | ❌ Only appends | Implement REPLACE/SMART_REPLACE/APPEND strategies | 🔴 HIGH |
| **Count Validation** | ❌ Not checked | Validate selected vs. existing count | 🟡 MEDIUM |
| **Template Analysis** | ❌ No detection | Analyze existing nodes for placeholders | 🔴 HIGH |
| **Strategy Logging** | ❌ Not present | Log which strategy was chosen and why | 🟡 MEDIUM |
| **Before/After Diff** | ⚠️ Partial | Show what was REPLACED vs. ADDED vs. REMOVED | 🟢 LOW |

---

### 0.9 Smooth User Transition Analysis

**Current User Experience**:
1. ✅ User opens Node Palette → Smooth transition (d3-container hidden, palette shown)
2. ✅ Nodes stream in progressively → Real-time cards appear
3. ✅ User selects nodes → Visual feedback (card highlights, checkmark, counter updates)
4. ✅ User clicks "Next" → Button shows count "Next (5 selected)"
5. ✅ Palette hides → Smooth fade out (300ms)
6. ⚠️ **Nodes are added** → Currently APPENDS to existing (creates duplicates on templates)
7. ✅ Diagram renders → Smooth re-render with new nodes
8. ✅ DOM updates → Nodes appear in correct positions

**Pain Points**:
- ⚠️ **Issue**: Default template has "Context 1", "Context 2", etc. → After selecting 5 palette nodes → Diagram now has "Context 1-8" + 5 new nodes = 13 total (expected: 5)
- ⚠️ **Issue**: No feedback about what happened (replaced vs. appended)
- ⚠️ **Issue**: Template placeholders are treated as real nodes

**Desired Experience** (After Smart Replace):
1. ✅ Everything current stays the same
2. ✅ **New**: Detection logs show "8 placeholders detected"
3. ✅ **New**: Strategy log shows "REPLACE mode - replacing all placeholders"
4. ✅ **New**: Assembly log shows "REPLACE 'Context 1' → 'Photosynthesis'"
5. ✅ **New**: Final diagram has exactly 5 nodes (clean, matches user expectation)

---

### 0.10 Code Review Summary

**Overall Assessment**: 🟢 **EXCELLENT FOUNDATION**

**Strengths**:
- ✅ Backend generation is solid and concurrent
- ✅ Frontend streaming and reception work perfectly
- ✅ Selection tracking is comprehensive
- ✅ Logging is professional and complete
- ✅ Rendering system handles string nodes correctly
- ✅ **Critical Bug Fixed**: No more "[object Object]" (thanks to line 813 fix!)
- ✅ End-to-end lifecycle tracking is complete
- ✅ Multi-diagram support via metadata system

**What Needs Implementation** (From this plan):
- ⚠️ Placeholder detection (Phase 2.1)
- ⚠️ Smart Replace logic (Phase 2.3)
- ⚠️ Strategy determination (Phase 2.3.2)
- ⚠️ Enhanced before/after logging for replacement (Phase 4.1)

**Recommendation**: 
✅ **Proceed with Phase 1-2 implementation**. The foundation is solid. We just need to add the Smart Replace logic to make it behave like Auto-Complete.

---

### 0.11 Context-Aware Node Generation (DESIGN DECISION)

**Current Implementation**:
- ⚠️ Node Palette currently generates **context nodes** for Circle Map only
- ⚠️ Not context-aware based on user selection
- ⚠️ Always targets the same array (e.g., `spec.context`)

**Desired Behavior (Diagram-Specific & Selection-Aware)**:

The Node Palette should generate **different node types** based on:
1. **Which diagram type** is active
2. **Which node** the user selected to trigger the palette

**Context-Aware Generation Matrix**:

| Diagram Type | User Selected | Should Generate | Target Array |
|--------------|---------------|-----------------|--------------|
| **Circle Map** | Center topic | Context nodes | `spec.context` |
| **Circle Map** | Context node | More context nodes | `spec.context` |
| **Bubble Map** | Main topic | Attribute nodes | `spec.attributes` |
| **Bubble Map** | Attribute node | More attributes | `spec.attributes` |
| **Mind Map** | Root topic | Branch nodes | `spec.branches` |
| **Mind Map** | Branch node | Sub-branches | `branch.children` |
| **Flow Map** | Event topic | Step nodes | `spec.steps` |
| **Flow Map** | Step node | Substeps | `step.substeps` |
| **Multi-Flow Map** | Event topic | Cause/Effect nodes | `spec.causes` or `spec.effects` |
| **Tree Map** | Root | Category nodes | `spec.categories` |
| **Tree Map** | Category | Item nodes | `category.items` |
| **Double Bubble Map** | Left/Right topic | Similarities | `spec.similarities` |
| **Double Bubble Map** | Similarity node | More similarities | `spec.similarities` |
| **Brace Map** | Whole | Part nodes | `spec.parts` |
| **Brace Map** | Part | Subpart nodes | `part.subparts` |
| **Bridge Map** | Main topic | Analogy pairs | `spec.analogies` |
| **Concept Map** | Any concept | Related concepts | `spec.concepts` |

**Implementation Strategy**:
- ✅ **Phase 2-3**: Implement Smart Replace for Circle Map (current scope)
- 🔜 **Phase 9**: Make Node Palette context-aware (future work)
  - Detect which node was selected
  - Determine appropriate node type to generate
  - Target correct array based on selection
  - Work on each diagram type one by one

**Current Scope**: 
Focus on Circle Map's Smart Replace first, then extend to other diagrams incrementally.

---

## Phase 1: Analysis & Preparation

### 1.1 Understand Current Behavior ✅ COMPLETE
- [x] Document current `assembleNodesToCircleMap()` logic → **Documented in Phase 0.4**
- [x] Identify where nodes are added: `currentSpec[arrayName].push(nodeText)` → **Line 813**
- [x] Note: Current behavior just appends, creating duplicates → **Confirmed**

### 1.2 Study Auto-Complete Reference ✅ COMPLETE
- [x] Read `renderCachedLLMResult()` in `toolbar-manager.js` (lines 440-542) → **Analyzed**
- [x] Understand how it replaces entire spec → **Pattern: `editor.currentSpec = newSpec` → `editor.render()`**
- [x] Note how editor handles size/position adjustments automatically → **Confirmed in Phase 0.5**

### 1.3 Identify Centralized Placeholder System ✅ COMPLETE (DISCOVERED!)
- [x] ✅ **FOUND**: `DiagramValidator` class in `diagram-validator.js` (Lines 15-82)
- [x] ✅ **FOUND**: Comprehensive placeholder patterns for EN/ZH
- [x] ✅ **FOUND**: `allPlaceholders` array with 47+ patterns
- [x] ⚠️ **MISSING**: "Context" patterns need to be added
- [x] Check `diagram-selector.js` for default templates → **Lines 600-602**:
  - Circle Map EN: `['Context 1', 'Context 2', ..., 'Context 8']`
  - Bubble Map EN: Uses `attributes` not `adjectives`
  - Flow Map EN: `['Step 1', 'Step 2', 'Step 3', 'Step 4']`
  - Double Bubble Map EN: `['Similarity 1', 'Similarity 2']`, `['Difference A1', 'A2']`, `['Difference B1', 'B2']`
  - All other types: Covered by existing `DiagramValidator` patterns

---

## Phase 2: Implementation

### 2.0 Backend Modularization (DO THIS FIRST!) 🔴 HIGH PRIORITY

**Why Now?**: 
- ✅ Only have Circle Map implemented - easiest time to refactor
- ✅ Sets up clean architecture for future diagrams
- ✅ Avoids painful migration later when we have 10 diagram types

**🐛 CRITICAL BUG TO FIX FIRST**:
- **File**: `routers/thinking.py` Line 329
- **Current**: `generator = get_node_palette_generator_v2()`  ❌ DOES NOT EXIST
- **Fix**: Change to `generator = get_node_palette_generator()` ✅
- **Impact**: Currently crashes when user clicks "Finish" button
- **Time**: 30 seconds
- **See**: Phase 0.9 below for bug details

**Refactoring Steps**:

#### Step 2.0.1: Create Directory Structure
```bash
mkdir -p agents/thinking_modes/node_palette
touch agents/thinking_modes/node_palette/__init__.py
```

#### Step 2.0.2: Create Base Class
- [ ] Create `agents/thinking_modes/node_palette/base_palette_generator.py`
- [ ] Extract ALL shared logic from current `node_palette_generator.py`:
  - Concurrent multi-LLM streaming
  - Real-time deduplication (`_deduplicate_node`)
  - Session management (sessions dict, seen_texts, batch_counts)
  - SSE event generation (batch_start, node_generated, llm_complete, batch_complete)
  - Temperature calculation (`_get_temperature_for_batch`)
  - Text normalization (`_normalize_text`)
  - Session cleanup (`end_session`)
- [ ] Define abstract method: `_build_prompt(center_topic, context, count, batch)` 
- [ ] Define abstract method: `_get_system_message(context)`

#### Step 2.0.3: Create Circle Map Palette
- [ ] Create `agents/thinking_modes/node_palette/circle_map_palette.py`
- [ ] Inherit from `BasePaletteGenerator`
- [ ] Implement `_build_prompt()` - use existing Circle Map logic (line 273-305)
- [ ] Implement `_get_system_message()` - use existing logic (line 307-313)
- [ ] Keep Circle Map-specific imports: `from prompts.thinking_modes.circle_map import get_prompt`

#### Step 2.0.4: Update Router
- [ ] Update `routers/thinking.py` to import from new location:
  ```python
  # OLD: from agents.thinking_modes.node_palette_generator import get_node_palette_generator
  # NEW: from agents.thinking_modes.node_palette.circle_map_palette import get_circle_map_palette_generator
  ```

#### Step 2.0.5: Update __init__.py
- [ ] Create `agents/thinking_modes/node_palette/__init__.py`:
  ```python
  from .circle_map_palette import get_circle_map_palette_generator
  
  __all__ = ['get_circle_map_palette_generator']
  ```

#### Step 2.0.6: Deprecate Old File
- [ ] Keep `agents/thinking_modes/node_palette_generator.py` temporarily (for reference)
- [ ] Add deprecation notice at top
- [ ] Remove after confirming new structure works

**Time Estimate**: 1-2 hours (well worth it!)

---

### 2.0.7 Add Cancel/Quit Button 🔵 UX ENHANCEMENT

**User Request**: Allow users to exit Node Palette at any stage without selecting nodes

**Frontend Changes** (`static/js/editor/node-palette-manager.js`):

**Add Cancel Button to UI**:
```javascript
// In showPalettePanel() or HTML template
<button id="cancel-palette-btn" class="cancel-btn">
    Cancel
</button>
```

**Add Handler**:
```javascript
attachCancelButtonListener() {
    const cancelBtn = document.getElementById('cancel-palette-btn');
    if (cancelBtn) {
        cancelBtn.replaceWith(cancelBtn.cloneNode(true));
        const newBtn = document.getElementById('cancel-palette-btn');
        
        newBtn.addEventListener('click', () => {
            console.log('[NodePalette] User clicked Cancel button');
            this.cancelPalette();
        });
        console.log('[NodePalette] Cancel button listener attached');
    }
}

async cancelPalette() {
    console.log('[NodePalette-Cancel] ========================================');
    console.log('[NodePalette-Cancel] USER CANCELLED NODE PALETTE');
    console.log('[NodePalette-Cancel] ========================================');
    console.log('[NodePalette-Cancel] Session: %s | Nodes generated: %d | Selected: %d', 
        this.sessionId, this.nodes.length, this.selectedNodes.size);
    
    // Log cancellation to backend
    try {
        await auth.fetch('/thinking_mode/node_palette/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.sessionId,
                nodes_generated: this.nodes.length,
                nodes_selected: this.selectedNodes.size,
                batches_loaded: this.currentBatch
            })
        });
    } catch (e) {
        console.error('[NodePalette-Cancel] Failed to log cancellation:', e);
    }
    
    // Clear state
    this.nodes = [];
    this.selectedNodes.clear();
    this.currentBatch = 0;
    
    console.log('[NodePalette-Cancel] ✓ State cleared');
    
    // Hide palette, show diagram (no changes to diagram)
    this.hidePalettePanel();
    
    console.log('[NodePalette-Cancel] ✓ Returned to diagram');
    console.log('[NodePalette-Cancel] ========================================');
}
```

**Backend Changes** (`routers/thinking.py`):

**Add Cancel Endpoint**:
```python
@router.post('/thinking_mode/node_palette/cancel')
async def cancel_node_palette(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Log when user cancels Node Palette without selecting nodes.
    Cleans up session and returns them to diagram.
    """
    session_id = request.get('session_id')
    nodes_generated = request.get('nodes_generated', 0)
    nodes_selected = request.get('nodes_selected', 0)
    batches_loaded = request.get('batches_loaded', 0)
    
    logger.info("[NodePalette-Cancel] User cancelled | Session: %s", session_id[:8])
    logger.info("[NodePalette-Cancel]   Generated: %d | Selected: %d | Batches: %d", 
               nodes_generated, nodes_selected, batches_loaded)
    
    # End session in generator
    generator = get_node_palette_generator()
    generator.end_session(session_id, reason="user_cancelled")
    
    return {"status": "cancelled"}
```

**Benefits**:
- ✅ Better UX - Users not forced to complete
- ✅ Clean exit - No orphaned sessions
- ✅ Analytics - Track cancellation rates
- ✅ No diagram changes - Preserves user work

**Time Estimate**: 30 minutes

---

### 2.1 Add Missing Patterns to DiagramValidator - STEP BY STEP

**File**: `static/js/editor/diagram-validator.js`  
**Goal**: Add "Context" placeholder patterns for Circle Map

---

#### Step 2.1.1: Add English Context Pattern

**Location**: Line ~56 (in `this.englishPlaceholders` array)

- [ ] Add after the `Step` pattern (around line 56)

```javascript
// In the englishPlaceholders array
/^Step\s+\d+$/i,          // Step 1, Step 2
/^Context\s+\d+$/i,       // Context 1, Context 2 (Circle Map) ← ADD THIS
/^Cause\s+\d+$/i,         // Cause 1
```

---

#### Step 2.1.2: Add Chinese Context Pattern

**Location**: Line ~23 (in `this.chinesePlaceholders` array)

- [ ] Add after the `步骤` pattern (around line 23)

```javascript
// In the chinesePlaceholders array
/^步骤\s*\d+$/,           // 步骤1, 步骤2
/^背景\s*\d+$/,           // 背景1, 背景2 (Circle Map) ← ADD THIS
/^原因\s*\d+$/,           // 原因1
```

---

#### Step 2.1.3: Test the Patterns

- [ ] Open browser console
- [ ] Test with DiagramValidator:

```javascript
const validator = new DiagramValidator();

// Test English
validator.allPlaceholders.some(p => p.test('Context 1'))  // → should be true
validator.allPlaceholders.some(p => p.test('Context 8'))  // → should be true

// Test Chinese  
validator.allPlaceholders.some(p => p.test('背景1'))      // → should be true
validator.allPlaceholders.some(p => p.test('背景8'))      // → should be true

// Test non-placeholders
validator.allPlaceholders.some(p => p.test('Photosynthesis'))  // → should be false
```

---

**That's it!** The centralized system now supports Circle Map placeholders.

**Benefits**:
- ✅ No code duplication
- ✅ Single source of truth for all placeholder patterns
- ✅ Already tested and used in Learning Mode validation
- ✅ Automatically supports all diagram types and languages (47+ patterns total)

### 2.2 Preparation - No Action Needed ✅

The Smart Replace logic doesn't need separate helper functions.

All logic is implemented directly in Phase 2.3:
- ✅ Placeholder detection uses `DiagramValidator` (Phase 2.1)
- ✅ Count validation is part of strategy determination (Phase 2.3.3)
- ✅ Strategy selection is automated based on placeholder analysis

**Skip to Phase 2.3** →

### 2.3 Modify `assembleNodesToCircleMap()` Method - STEP BY STEP

**File**: `static/js/editor/node-palette-manager.js`  
**Method**: `assembleNodesToCircleMap()` (lines 726-902)  
**Goal**: Add Smart Replace logic with 3 strategies

---

#### Step 2.3.1: Add `isPlaceholder()` Helper Method

- [ ] Add new method to `NodePaletteManager` class (before `assembleNodesToCircleMap`)
- [ ] Use `DiagramValidator` for placeholder detection

```javascript
isPlaceholder(text) {
    /**
     * Check if text is a template placeholder using DiagramValidator.
     * 
     * @param {string} text - Node text to check
     * @returns {boolean} True if placeholder, false if user content
     */
    if (!text || typeof text !== 'string') return false;
    
    // Get or create DiagramValidator instance
    const validator = window.diagramValidator || new DiagramValidator();
    
    // Check against all placeholder patterns (EN + ZH)
    const isPlaceholder = validator.allPlaceholders.some(pattern => pattern.test(text));
    
    return isPlaceholder;
}
```

**Test it works**: 
```javascript
this.isPlaceholder('Context 1')  // → true
this.isPlaceholder('背景1')       // → true
this.isPlaceholder('Photosynthesis')  // → false
```

---

#### Step 2.3.2: Add Detection Phase to `assembleNodesToCircleMap()`

**Location**: After line 789 (after getting `currentSpec[arrayName]`)

- [ ] Add detection code BEFORE the current `for` loop (line 796)

```javascript
// Step 4: Add selected nodes as STRINGS (not objects!)
// CRITICAL: Most diagram arrays (context, adjectives, steps) expect simple strings, not objects
console.log(`[NodePalette-Assemble] Adding ${metadata.nodeNamePlural} to spec.${arrayName} array...`);

// ============================================================
// DETECTION PHASE - NEW CODE STARTS HERE
// ============================================================
const existingNodes = currentSpec[arrayName] || [];
const existingCount = existingNodes.length;
let placeholderCount = 0;
let userNodeCount = 0;

console.log(`[NodePalette-Assemble] ========================================`);
console.log(`[NodePalette-Assemble] DETECTION PHASE`);
console.log(`[NodePalette-Assemble] ========================================`);
console.log(`[NodePalette-Assemble] Existing ${metadata.nodeNamePlural}: ${existingCount}`);

// Analyze each existing node
existingNodes.forEach((nodeText, idx) => {
    const isPlaceholder = this.isPlaceholder(nodeText);
    if (isPlaceholder) {
        placeholderCount++;
        console.log(`  [${idx}] "${nodeText}" - PLACEHOLDER`);
    } else {
        userNodeCount++;
        console.log(`  [${idx}] "${nodeText}" - USER NODE`);
    }
});

console.log(`[NodePalette-Assemble] Analysis:`);
console.log(`[NodePalette-Assemble]   Total existing: ${existingCount}`);
console.log(`[NodePalette-Assemble]   Placeholders: ${placeholderCount}`);
console.log(`[NodePalette-Assemble]   User nodes: ${userNodeCount}`);
console.log(`[NodePalette-Assemble]   Selected to add: ${selectedNodes.length}`);
// ============================================================
// DETECTION PHASE - NEW CODE ENDS HERE
// ============================================================
```

---

#### Step 2.3.3: Add Strategy Determination

- [ ] Add strategy logic AFTER detection phase

```javascript
// ============================================================
// STRATEGY DETERMINATION - NEW CODE STARTS HERE
// ============================================================
let strategy = 'append';  // Default: add to end

if (existingCount === 0) {
    strategy = 'append';  // Empty array, just add
} else if (placeholderCount === existingCount) {
    strategy = 'replace';  // All are placeholders, replace them
} else if (placeholderCount > 0) {
    strategy = 'smart_replace';  // Mix: replace placeholders, keep user nodes
} else {
    strategy = 'append';  // All user nodes, append to end
}

console.log(`[NodePalette-Assemble] ========================================`);
console.log(`[NodePalette-Assemble] STRATEGY: ${strategy.toUpperCase()}`);
console.log(`[NodePalette-Assemble] ========================================`);

switch (strategy) {
    case 'replace':
        console.log(`[NodePalette-Assemble] Action: Replace ALL placeholders with selected nodes`);
        console.log(`[NodePalette-Assemble]   Will clear ${existingCount} placeholders`);
        console.log(`[NodePalette-Assemble]   Will add ${selectedNodes.length} selected nodes`);
        break;
    case 'smart_replace':
        console.log(`[NodePalette-Assemble] Action: Keep user nodes, replace placeholders`);
        console.log(`[NodePalette-Assemble]   Will keep ${userNodeCount} user nodes`);
        console.log(`[NodePalette-Assemble]   Will replace ${placeholderCount} placeholders`);
        console.log(`[NodePalette-Assemble]   Will add ${selectedNodes.length} selected nodes`);
        break;
    case 'append':
        console.log(`[NodePalette-Assemble] Action: Append to existing content`);
        console.log(`[NodePalette-Assemble]   Will keep ${existingCount} existing nodes`);
        console.log(`[NodePalette-Assemble]   Will append ${selectedNodes.length} selected nodes`);
        break;
}
// ============================================================
// STRATEGY DETERMINATION - NEW CODE ENDS HERE
// ============================================================
```

---

#### Step 2.3.4: Execute Strategy - REPLACE Mode

- [ ] Replace the current `for` loop (lines 796-821) with strategy-based execution

**REPLACE MODE** (all placeholders → replace with selected):
```javascript
// ============================================================
// EXECUTION PHASE - NEW CODE REPLACES OLD FOR LOOP
// ============================================================
const addedNodeIds = [];

if (strategy === 'replace') {
    // REPLACE MODE: Clear all placeholders, add selected nodes
    console.log(`[NodePalette-Assemble] Clearing ${existingCount} placeholders...`);
    currentSpec[arrayName] = [];  // Clear entire array
    
    console.log(`[NodePalette-Assemble] Adding ${selectedNodes.length} selected nodes...`);
    for (let i = 0; i < selectedNodes.length; i++) {
        const node = selectedNodes[i];
        const nodeText = node.text;
        
        console.log(`  [${i}] REPLACE → "${nodeText}" (from ${node.source_llm})`);
        
        currentSpec[arrayName].push(nodeText);
        node.added_to_diagram = true;
        addedNodeIds.push(node.id);
    }
    
    console.log(`[NodePalette-Assemble] ✓ REPLACE complete: ${existingCount} placeholders → ${selectedNodes.length} nodes`);
}
```

---

#### Step 2.3.5: Execute Strategy - SMART REPLACE Mode

**SMART REPLACE MODE** (keep user nodes, replace placeholders):
```javascript
else if (strategy === 'smart_replace') {
    // SMART REPLACE: Keep user nodes, replace placeholders with selected
    console.log(`[NodePalette-Assemble] Filtering out ${placeholderCount} placeholders...`);
    
    // Keep only user nodes
    const userNodes = existingNodes.filter(nodeText => !this.isPlaceholder(nodeText));
    currentSpec[arrayName] = userNodes;
    
    console.log(`[NodePalette-Assemble] Kept ${userNodes.length} user nodes`);
    userNodes.forEach((nodeText, idx) => {
        console.log(`  [${idx}] KEPT → "${nodeText}"`);
    });
    
    console.log(`[NodePalette-Assemble] Adding ${selectedNodes.length} selected nodes...`);
    for (let i = 0; i < selectedNodes.length; i++) {
        const node = selectedNodes[i];
        const nodeText = node.text;
        
        console.log(`  [${userNodes.length + i}] ADD → "${nodeText}" (from ${node.source_llm})`);
        
        currentSpec[arrayName].push(nodeText);
        node.added_to_diagram = true;
        addedNodeIds.push(node.id);
    }
    
    console.log(`[NodePalette-Assemble] ✓ SMART REPLACE complete: ${userNodeCount} kept + ${selectedNodes.length} added = ${currentSpec[arrayName].length} total`);
}
```

---

#### Step 2.3.6: Execute Strategy - APPEND Mode

**APPEND MODE** (current behavior - add to end):
```javascript
else {
    // APPEND MODE: Keep everything, add selected to end (current behavior)
    console.log(`[NodePalette-Assemble] Appending to existing content...`);
    
    for (let i = 0; i < selectedNodes.length; i++) {
        const node = selectedNodes[i];
        const nodeText = node.text;
        
        console.log(`  [${existingCount + i}] APPEND → "${nodeText}" (from ${node.source_llm})`);
        
        currentSpec[arrayName].push(nodeText);
        node.added_to_diagram = true;
        addedNodeIds.push(node.id);
    }
    
    console.log(`[NodePalette-Assemble] ✓ APPEND complete: ${existingCount} existing + ${selectedNodes.length} added = ${currentSpec[arrayName].length} total`);
}
// ============================================================
// EXECUTION PHASE - NEW CODE ENDS HERE
// ============================================================
```

---

#### Step 2.3.7: Update Final Logging

- [ ] Update lines 823-831 to show final state

```javascript
// (Keep existing line 823)
console.log(`[NodePalette-Assemble] Successfully added ${addedNodeIds.length} ${metadata.nodeNamePlural}`);
console.log(`[NodePalette-Assemble] Added node IDs:`, addedNodeIds);

const afterCount = currentSpec[arrayName].length;
console.log(`[NodePalette-Assemble] ========================================`);
console.log(`[NodePalette-Assemble] FINAL RESULT`);
console.log(`[NodePalette-Assemble] ========================================`);
console.log(`[NodePalette-Assemble] Strategy used: ${strategy.toUpperCase()}`);
console.log(`[NodePalette-Assemble] Before: ${beforeCount} nodes | After: ${afterCount} nodes | Change: ${afterCount - beforeCount > 0 ? '+' : ''}${afterCount - beforeCount}`);
console.log(`[NodePalette-Assemble] Final spec.${arrayName} array:`);
currentSpec[arrayName].forEach((item, idx) => {
    console.log(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
});
```

---

#### Step 2.3.8: Keep Existing Rendering Logic

- [ ] **DO NOT CHANGE** lines 833-902 (rendering, DOM verification, history)
- [ ] These parts work perfectly, leave them as-is

**Summary of Changes**:
- ✅ Add `isPlaceholder()` helper (new method)
- ✅ Add detection phase (before old line 796)
- ✅ Add strategy determination (before old line 796)
- ✅ Replace old `for` loop (lines 796-821) with strategy-based execution
- ✅ Update final logging (lines 823-831)
- ✅ Keep rendering logic untouched (lines 833-902)

### 2.4 Testing Smart Replace (Quick Verification)

Before moving to Phase 3, do a quick test:

- [ ] Load Circle Map default template (has "Context 1-8")
- [ ] Open Node Palette
- [ ] Select 5 nodes
- [ ] Click "Next" (finish)
- [ ] **Expected**: Diagram should show ONLY 5 selected nodes (not 13)
- [ ] Check console logs:
  - Should see `DETECTION PHASE`
  - Should see `STRATEGY: REPLACE`
  - Should see placeholder detection working
- [ ] **If working**: Proceed to Phase 3
- [ ] **If broken**: Debug using the comprehensive logs

---

## Phase 3: Edge Cases & Validation

### 3.1 Handle Edge Cases

#### Case 1: Empty Template
- [ ] Test: User starts with completely empty diagram
- [ ] Expected: Should just add selected nodes (no spec.context array exists)
- [ ] Verify: Array is created and populated

#### Case 2: Fresh Template with All Placeholders
- [ ] Test: User loads default template with 8 "Context 1", "Context 2", etc.
- [ ] Test: User selects 5 nodes from palette
- [ ] Expected: Replace first 5 placeholders, remove last 3 placeholders
- [ ] Verify: Final array has exactly 5 nodes (selected ones)

#### Case 3: Fresh Template with More Selected Than Placeholders
- [ ] Test: Template has 5 placeholders, user selects 8 nodes
- [ ] Expected: Replace all 5 placeholders, add 3 more nodes
- [ ] Verify: Final array has exactly 8 nodes (all selected)

#### Case 4: Mixed Content (Some User Nodes + Some Placeholders)
- [ ] Test: User has added 3 custom nodes, template still has 5 placeholders
- [ ] Test: User selects 4 nodes from palette
- [ ] Expected: Keep 3 user nodes, replace 4 placeholders, remove 1 placeholder
- [ ] Verify: Final array has 7 nodes (3 user + 4 selected)

#### Case 5: All User Nodes (No Placeholders)
- [ ] Test: User has manually created diagram with 6 nodes
- [ ] Test: User selects 3 nodes from palette
- [ ] Expected: APPEND mode - add 3 nodes to end
- [ ] Verify: Final array has 9 nodes (6 existing + 3 new)

#### Case 6: Language Mismatch
- [ ] Test: Template in Chinese, user interface in English
- [ ] Expected: Detect Chinese placeholders correctly
- [ ] Verify: Replace works regardless of UI language

#### Case 7: Different Diagram Types
- [ ] Test each diagram type's placeholder patterns
- [ ] Verify metadata is correct for each type
- [ ] Verify detection works for all patterns

#### Case 8: User Cancels Node Palette
- [ ] Test: User opens palette, doesn't select any nodes, clicks Cancel
- [ ] Expected: Returns to diagram, no changes, session cleaned up
- [ ] Verify: No memory leaks, no orphaned sessions
- [ ] Test: User opens palette, selects 5 nodes, clicks Cancel (before Finish)
- [ ] Expected: Returns to diagram, selections discarded, no nodes added
- [ ] Verify: Diagram unchanged, session ended in backend logs
- [ ] Test: User opens palette, loads 3 batches, clicks Cancel
- [ ] Expected: Clean exit regardless of how many batches loaded

### 3.2 Validate Rendering
- [ ] After replacement, verify `editor.render()` is called
- [ ] Verify renderer receives correct spec structure
- [ ] Verify nodes display with correct text (not "[object Object]")
- [ ] Verify sizes/positions auto-adjust
- [ ] Verify no layout breaks

---

## Phase 4: Logging & Debugging

### 4.1 Add Comprehensive Logging

**At each stage, log:**
- [ ] **Detection Phase**: What was detected (placeholders, user nodes, language)
- [ ] **Strategy Phase**: Which strategy was chosen and why
- [ ] **Execution Phase**: What operations were performed
- [ ] **Validation Phase**: Before/after comparison
- [ ] **Rendering Phase**: Confirmation spec sent to renderer

**Log format:**
```javascript
[NodePalette-Assemble] ========================================
[NodePalette-Assemble] SMART REPLACE MODE
[NodePalette-Assemble] ========================================
[NodePalette-Assemble] BEFORE:
  Total nodes: 8
  Placeholders: 8 (Context 1, Context 2, ...)
  User nodes: 0
  Selected nodes: 5

[NodePalette-Assemble] STRATEGY: REPLACE
  Action: Replace all placeholders
  Will replace: 5 placeholders
  Will remove: 3 placeholders

[NodePalette-Assemble] EXECUTING REPLACEMENT:
  [0] REPLACE "Context 1" → "Photosynthesis"
  [1] REPLACE "Context 2" → "Chloroplast"
  [2] REPLACE "Context 3" → "Mitochondria"
  [3] REPLACE "Context 4" → "ATP production"
  [4] REPLACE "Context 5" → "Cell membrane"
  [5] REMOVE "Context 6"
  [6] REMOVE "Context 7"
  [7] REMOVE "Context 8"

[NodePalette-Assemble] AFTER:
  Total nodes: 5
  All nodes are from palette selection
  
[NodePalette-Assemble] ✓ SMART REPLACE COMPLETE
```

### 4.2 Add Status Tracking
- [ ] Track which nodes were: REPLACED, ADDED, REMOVED, KEPT
- [ ] Update node objects with operation type
- [ ] Include in final summary

---

## Phase 5: Testing

### 5.1 Unit Testing (Manual Console Testing)
- [ ] Test placeholder detection with various patterns
- [ ] Test language detection (EN/ZH)
- [ ] Test count validation logic
- [ ] Test each strategy independently

### 5.2 Integration Testing
- [ ] Test Circle Map with default template
- [ ] Test Bubble Map with default template
- [ ] Test Flow Map with default template
- [ ] Test each edge case from Phase 3.1
- [ ] Verify logging output is clean and informative
- [ ] **Test Cancel button**: Click cancel at different stages
  - After 0 selections
  - After 5 selections
  - After 3 batches loaded
  - Verify clean return to diagram
  - Verify session cleanup in backend logs

### 5.3 End-to-End Testing
- [ ] Full workflow: Load template → Open palette → Select nodes → Finish → Verify
- [ ] Test with 4 LLMs generating different nodes
- [ ] Test with multiple batches
- [ ] Test selection/deselection
- [ ] Verify final diagram matches expectations

### 5.4 Cross-Diagram Testing
- [ ] Test on all 10 supported diagram types
- [ ] Verify metadata is correct for each
- [ ] Verify placeholder patterns work for each

---

## Phase 6: Documentation

### 6.1 Update Code Comments
- [ ] Add JSDoc comments to new helper functions
- [ ] Document the three strategies (replace, smart_replace, append)
- [ ] Add examples in comments

### 6.2 Update Technical Documentation
- [ ] Update this implementation plan with actual results
- [ ] Document the three Smart Replace strategies
- [ ] Add before/after examples in comments
- [ ] Document placeholder patterns added to DiagramValidator
- [ ] Update workflow diagrams

### 6.3 Update User-Facing Docs (if any)
- [ ] Explain how Node Palette interacts with templates
- [ ] Clarify replacement vs. append behavior

---

## Phase 7: Optimization & Cleanup

### 7.1 Performance Checks
- [ ] Verify no performance regression with large node counts (100+ nodes)
- [ ] Verify detection is fast (should be O(n) where n = existing nodes)
- [ ] Verify no memory leaks

### 7.2 Code Quality
- [ ] Remove any debug/test code
- [ ] Ensure consistent naming conventions
- [ ] Follow existing code style
- [ ] Check for linter errors

### 7.3 Logging Cleanup
- [ ] Ensure logs are clean and professional (no emojis unless tasteful)
- [ ] Verify log levels are appropriate (info vs. debug vs. error)
- [ ] Remove excessive/redundant logs

---

## Phase 8: Final Validation

### 8.1 Pre-Deployment Checklist
- [ ] All edge cases tested and passing
- [ ] Logging is comprehensive but not overwhelming
- [ ] No linter errors
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Backward compatibility maintained (append mode still works)

### 8.2 Regression Testing
- [ ] Verify existing Node Palette functionality still works
- [ ] Verify auto-complete still works
- [ ] Verify manual node editing still works
- [ ] Verify template loading still works

---

## Files to Modify

### Primary Files:

1. **agents/thinking_modes/node_palette/** (NEW DIRECTORY) 🔴 **PHASE 2.0**
   - Create directory structure
   - Create `base_palette_generator.py` - Extract shared logic
   - Create `circle_map_palette.py` - Migrate existing code
   - Update `__init__.py` - Export new generator
   
2. **routers/thinking.py** 🔴 **PHASE 2.0**
   - Update import path to use new modular structure
   
3. **static/js/editor/diagram-validator.js** (Lines 50-79) 🟡 **PHASE 2.1**
   - Add missing "Context" patterns:
     - English: `/^Context\s+\d+$/i` (line ~56)
     - Chinese: `/^背景\s*\d+$/` (line ~23)
   - This makes the centralized system complete

4. **static/js/editor/node-palette-manager.js** (Lines 726-902) 🟡 **PHASE 2.2-2.3**
   - Add `cancelPalette()` method - Handle cancel button 🔵 (Phase 2.0.7)
   - Add `attachCancelButtonListener()` - Setup cancel handler 🔵 (Phase 2.0.7)
   - Add helper method: `isPlaceholder(text)` - wraps `DiagramValidator`
   - Add helper method: `validateNodeCount(currentCount, selectedCount)`
   - Modify `assembleNodesToCircleMap()` method:
     - Add detection phase (analyze existing nodes)
     - Add strategy phase (replace vs. smart_replace vs. append)
     - Add execution phase (perform the chosen strategy)
     - Enhance logging for replacement operations

5. **routers/thinking.py** 🔵 **PHASE 2.0.7**
   - Add `/thinking_mode/node_palette/cancel` endpoint
   - Handle cancellation logging and session cleanup

### Secondary Files (Documentation):
3. **This Plan** (`NODE_PALETTE_SMART_REPLACE_IMPLEMENTATION_PLAN.md`)
   - Update Phase 6-8 sections with actual results after implementation
   - Add code snippets showing the three strategies in action
   - Document any edge cases discovered during testing

4. **docs/NODE_PALETTE_SMART_REPLACE_IMPLEMENTATION_PLAN.md** (this file)
   - Keep as reference
   - Update with actual line numbers after implementation
   - Mark completed items as ✅

### Future Files (Phase 9 - Context-Aware Generation):

5. **agents/thinking_modes/node_palette/** (ALREADY EXISTS after Phase 2.0!)
   - ✅ Base class already created in Phase 2.0
   - ✅ Circle Map already migrated in Phase 2.0
   - Add 9 more diagram-specific palette generators (one per diagram)
   
6. **prompts/thinking_modes/** (Existing directory)
   - Add `NODE_GENERATION` prompts to each diagram's prompt file
   - Currently only `circle_map.py` has it
   - Need to add for: bubble_map, mind_map, flow_map, etc.

7. **routers/thinking.py** (Update routing)
   - Route to appropriate palette generator based on diagram type
   - Currently hardcoded to `node_palette_generator`

8. **static/js/editor/node-palette-manager.js**
   - Add selection context detection
   - Pass diagram type and selection context to backend
   - Handle different target arrays per diagram

---

## Success Criteria

✅ **Functional**:
- [ ] Placeholders are correctly detected in all supported languages
- [ ] Fresh templates are replaced (not appended to)
- [ ] User nodes are preserved when replacing placeholders
- [ ] Diagram renders correctly after replacement
- [ ] No "[object Object]" issues

✅ **Quality**:
- [ ] All edge cases handled gracefully
- [ ] Logging is comprehensive and clean
- [ ] Code is well-documented
- [ ] No linter errors
- [ ] Performance is acceptable

✅ **User Experience**:
- [ ] Behavior matches auto-complete (intuitive)
- [ ] No unexpected node duplication
- [ ] Clear feedback in logs for debugging
- [ ] Works across all diagram types

---

## Risk Assessment

### High Risk:
- **Breaking existing functionality**: Changing core assembly logic could break current workflows
  - **Mitigation**: Keep append mode as fallback, test thoroughly
  
### Medium Risk:
- **Language detection edge cases**: Mixed language diagrams could confuse detection
  - **Mitigation**: Make detection robust, prefer explicit metadata over heuristics

- **Diagram type variations**: Some diagram types may have unique patterns
  - **Mitigation**: Test all 10 diagram types individually

### Low Risk:
- **Performance**: Detection adds minimal overhead
- **Logging volume**: New logs are well-structured and optional

---

## Timeline Estimate

**Current Scope (Circle Map Smart Replace + Modularization + Cancel Button)**:
- **Phase 1 (Analysis)**: ✅ COMPLETE (done via code review)
- **Phase 2.0 (Backend Modularization)**: 1-2 hours 🔴 **DO THIS FIRST**
  - Includes: Bug fix (30 sec), Modularization (1-2 hrs), Cancel button (30 min)
- **Phase 2.1-2.4 (Smart Replace Implementation)**: 2-3 hours
- **Phase 3 (Edge Cases)**: 1-2 hours (includes cancel testing)
- **Phase 4 (Logging)**: 30 minutes
- **Phase 5 (Testing)**: 2-3 hours (includes cancel button tests)
- **Phase 6 (Documentation)**: 1 hour
- **Phase 7 (Optimization)**: 1 hour
- **Phase 8 (Validation)**: 1 hour

**Current Scope Total**: ~10.5-14.5 hours (includes modularization + cancel button)

**Future Work (Context-Aware Generation)**:
- **Phase 9 (Add 9 More Diagram Types)**: ~12-15 hours
  - ✅ Backend architecture: Already done in Phase 2.0!
  - Design selection detection: 1-2 hours
  - Frontend selection detection: 2-3 hours
  - Implementation per diagram (9 types × 1 hour each): 9 hours
  - Testing all contexts: 2-3 hours

**Grand Total (All Phases)**: ~22-29 hours

---

## Phase 9: Context-Aware Node Generation (Future Work)

**Goal**: Make Node Palette generate different node types based on user selection context.

### 9.1 Design System
- [ ] Design node selection detection system
- [ ] Map selection types to generation targets
- [ ] Define prompt variations for each context
- [ ] Document expected behavior for each diagram type

### 9.2 Selection Detection
- [ ] Capture which node user clicked/selected before opening palette
- [ ] Store selection context: `{ nodeType, nodeId, nodeText, parentNode }`
- [ ] Pass context to backend for appropriate prompt generation

### 9.3 Add New Diagram Palette Generators ✅ Architecture Ready

**✅ DONE IN PHASE 2.0**: Backend architecture is already modularized!

**Current Structure** (After Phase 2.0):
```
agents/thinking_modes/node_palette/
├── __init__.py
├── base_palette_generator.py      ← ✅ Base class (shared logic)
└── circle_map_palette.py          ← ✅ Circle Map specific
```

**What's Left for Phase 9**: Just add 9 more palette generators!

**New Files to Create** (one per diagram):
- [ ] `bubble_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `mind_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `flow_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `multi_flow_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `tree_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `brace_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `bridge_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `double_bubble_map_palette.py` - Inherit from `BasePaletteGenerator`
- [ ] `concept_map_palette.py` - Inherit from `BasePaletteGenerator`

**Each file only needs**:
- Implement `_build_prompt()` - Custom prompt for that diagram
- Implement `_get_system_message()` - Same or diagram-specific
- Import appropriate prompt file: `from prompts.thinking_modes.{diagram} import get_prompt`

**Estimated Time**: ~1 hour per diagram (9 diagrams = 9 hours)

### 9.4 Frontend Target Detection
- [ ] Modify `assembleNodesToCircleMap()` to detect target array from context
- [ ] For hierarchical structures (Mind Map, Tree Map, Flow Map):
  - Detect if adding to top-level or nested array
  - Handle `branch.children`, `step.substeps`, etc.
- [ ] Smart Replace should respect hierarchy

### 9.5 Diagram-Specific Prompts

Each palette generator needs custom prompts:

| Diagram | Prompt Example | Target Node Type |
|---------|----------------|------------------|
| **Circle Map** | "Generate 15 contextual observations about {topic} for K12 education..." | Context nodes |
| **Bubble Map** | "Generate 15 descriptive attributes or adjectives for {topic}..." | Attribute nodes |
| **Mind Map** | "Generate 15 main branches/subtopics related to {topic}..." | Branch nodes |
| **Flow Map** | "Generate 15 sequential steps in the process of {event}..." | Step nodes |
| **Multi-Flow Map** | "Generate 15 causes/effects of {event}..." | Cause or Effect nodes |
| **Tree Map** | "Generate 15 categories/items for organizing {topic}..." | Category or Item nodes |
| **Brace Map** | "Generate 15 parts that compose {whole}..." | Part nodes |
| **Double Bubble Map** | "Generate 15 similarities between {left} and {right}..." | Similarity nodes |
| **Bridge Map** | "Generate 15 analogy pairs related to {topic}..." | Analogy pairs |
| **Concept Map** | "Generate 15 related concepts to {concept}..." | Concept nodes |

**Prompt Files** (Already exist in centralized system):
```
prompts/thinking_modes/
├── circle_map.py      ← Already has NODE_GENERATION
├── bubble_map.py      ← Need to add NODE_GENERATION
├── mind_map.py        ← Need to add NODE_GENERATION
└── ... (add for each)
```

### 9.6 Implementation Order (One by one)
1. [ ] **Circle Map** (Already works - context nodes) ✅
2. [ ] **Bubble Map** (Simple - attributes array)
   - Files: `bubble_map_palette.py`, update `prompts/thinking_modes/bubble_map.py`
3. [ ] **Double Bubble Map** (Medium - similarities/differences)
   - Files: `double_bubble_map_palette.py`, update prompts
4. [ ] **Flow Map** (Complex - steps with substeps)
   - Files: `flow_map_palette.py`, update prompts
5. [ ] **Mind Map** (Complex - branches with children)
   - Files: `mind_map_palette.py`, update prompts
6. [ ] **Multi-Flow Map** (Medium - causes/effects)
   - Files: `multi_flow_map_palette.py`, update prompts
7. [ ] **Tree Map** (Complex - categories with items)
   - Files: `tree_map_palette.py`, update prompts
8. [ ] **Brace Map** (Medium - parts with subparts)
   - Files: `brace_map_palette.py`, update prompts
9. [ ] **Bridge Map** (Simple - analogy pairs)
   - Files: `bridge_map_palette.py`, update prompts
10. [ ] **Concept Map** (Simple - concepts array)
    - Files: `concept_map_palette.py`, update prompts

### 9.7 Testing Strategy
- [ ] Test each diagram type individually
- [ ] Test top-level vs. nested node generation
- [ ] Verify correct array targeting
- [ ] Verify Smart Replace works for all contexts
- [ ] Test with different selection contexts

**Note**: This is future work. Complete Phase 2-8 (Circle Map Smart Replace) first!

---

## 🎯 Current Status & Next Steps

### ✅ Completed (No Further Action)
- **Phase 0**: Code review complete - all analysis in sections 0.1-0.11
- **Verbose Logging**: Already implemented - comprehensive tracking throughout system
- **Bug Identification**: Line 329 bug confirmed in actual codebase
- **Architecture Analysis**: Centralized systems discovered (DiagramValidator, etc.)

### ⚠️ Ready to Implement
- **Phase 1**: Analysis & Preparation (mostly done in Phase 0)
- **Phase 2**: Implementation - START HERE!
  - **2.0**: Backend modularization (1-2 hrs)
  - **2.0.1**: Fix line 329 bug (30 sec) 🐛 **DO FIRST!**
  - **2.0.7**: Add cancel button (30 min)
  - **2.1-2.3**: Smart Replace logic (2-3 hrs)
- **Phase 3-8**: Testing, validation, documentation (2-3 hrs)

### 🔮 Future Work (Not in Current Scope)
- **Phase 9**: Context-aware generation for 9 more diagrams (~9 hours)

**Recommendation**: Start with Phase 2.0.1 (30 second bug fix), then proceed with backend modularization (Phase 2.0).

---

## Notes

- This implementation makes Node Palette behave like Auto-Complete
- Maintains backward compatibility with append mode
- **Verbose logging already complete** - no logging tasks needed in Phase 4
- Diagram-type aware using existing metadata system
- Language-aware (EN/ZH support)
- **Context-aware generation** is planned for Phase 9 (future work)
- Current focus: Circle Map Smart Replace (Phases 2-8)

**Ready to implement Phase 2.0.1 (bug fix) immediately!**

