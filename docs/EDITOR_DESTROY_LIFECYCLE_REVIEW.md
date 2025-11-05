# InteractiveEditor Destroy Lifecycle Review

## Root Cause Analysis

### Problem
When deleting nodes in bubble map, error occurs:
```
ERROR | EventBus | Listener error for diagram:nodes_deleted
"Cannot read properties of null (reading 'clearSelection')"
at interactive-editor.js:246:39
```

### Root Cause Identified

**Issue**: Event Bus listeners are NOT removed when `InteractiveEditor.destroy()` is called.

**Evidence**:
1. `destroy()` method (line 1262-1348) removes:
   - ✅ DOM event listeners (resetViewClick, orientationChange, windowResize)
   - ✅ Sets `this.selectionManager = null` (line 1301)
   - ❌ **DOES NOT remove Event Bus listeners**

2. Event Bus listeners registered in `initialize()` (lines 200-300):
   - `diagram:render_requested`
   - `diagram:operations_loaded`
   - `diagram:operations_unavailable`
   - `diagram:node_added` (stored in `eventBusListeners.nodeAdded`)
   - `diagram:nodes_deleted` (stored in `eventBusListeners.nodesDeleted`)
   - `diagram:node_updated` (stored in `eventBusListeners.nodeUpdated`)
   - `mindmap:layout_recalculation_requested`
   - `mindmap:selection_restore_requested`

3. Other modules properly clean up:
   - `NodePropertyOperationsManager.destroy()` uses `eventBus.off()` for all listeners
   - `MindMateManager.destroy()` uses `eventBus.off()` for all listeners
   - `LLMValidationManager.destroy()` uses `eventBus.off()` for all listeners

4. **The Problem**:
   - When `destroy()` is called, `this.selectionManager = null`
   - But Event Bus listeners remain active
   - When `diagram:nodes_deleted` is emitted later (from an async operation or cached event), the handler tries to access `this.selectionManager.clearSelection()` 
   - Since `this.selectionManager` is null, it throws the error

### Sequence of Events

1. User deletes node in bubble map
2. `BubbleMapOperations.deleteNodes()` emits `diagram:nodes_deleted` event
3. Event Bus dispatches to all listeners, including `InteractiveEditor` handler
4. Handler tries to call `this.selectionManager.clearSelection()` (line 265)
5. **IF** editor was destroyed between steps 1-4, `this.selectionManager` is null
6. Error occurs

### Why This Happens

The Event Bus listeners are **persistent** and **not bound to editor lifecycle**:
- Event Bus is global (`window.eventBus`)
- Listeners persist until explicitly removed with `eventBus.off()`
- When editor is destroyed, listeners remain active
- If events are emitted after destroy (async operations, delayed events), handlers execute on destroyed instances

---

## Solution

### Fix Required

**File**: `static/js/editor/interactive-editor.js`

**Add to `destroy()` method**:
```javascript
// Remove Event Bus listeners
if (this.eventBus && this.eventBusListeners) {
    if (this.eventBusListeners.nodeAdded) {
        this.eventBus.off('diagram:node_added', this.eventBusListeners.nodeAdded);
    }
    if (this.eventBusListeners.nodesDeleted) {
        this.eventBus.off('diagram:nodes_deleted', this.eventBusListeners.nodesDeleted);
    }
    if (this.eventBusListeners.nodeUpdated) {
        this.eventBus.off('diagram:node_updated', this.eventBusListeners.nodeUpdated);
    }
    // Remove other listeners that don't have stored references yet
    // For listeners without stored references, we need to store them first
}
```

**Also need to store references for ALL listeners** (not just the ones we already stored):
- `diagram:render_requested`
- `diagram:operations_loaded`
- `diagram:operations_unavailable`
- `mindmap:layout_recalculation_requested`
- `mindmap:selection_restore_requested`

---

## Comparison with Other Modules

### ✅ Correct Pattern (NodePropertyOperationsManager)
```javascript
constructor() {
    this.callbacks = {
        applyAll: () => this.applyAllProperties(),
        // ... store all callbacks
    };
    this.eventBus.on('properties:apply_all_requested', this.callbacks.applyAll);
}

destroy() {
    this.eventBus.off('properties:apply_all_requested', this.callbacks.applyAll);
    // ... remove all listeners
}
```

### ❌ Current Pattern (InteractiveEditor)
```javascript
initialize() {
    this.eventBus.on('diagram:nodes_deleted', (data) => {
        // ... handler code
    });
    // No reference stored initially
}

destroy() {
    this.selectionManager = null; // ❌ Listener still active!
    // No eventBus.off() calls
}
```

---

## Action Items

1. **Store ALL Event Bus listener references** in `eventBusListeners` object
2. **Remove ALL Event Bus listeners** in `destroy()` using `eventBus.off()`
3. **Add guard checks** in handlers (already done, but should be temporary)
4. **Verify** no other modules have the same issue

---

## Impact

- **Critical**: Causes errors when operations complete after editor destruction
- **Severity**: Medium (error logged but doesn't crash app)
- **Frequency**: Happens when async operations complete after editor switch/destroy
- **User Impact**: Console errors, potential memory leaks from orphaned listeners

