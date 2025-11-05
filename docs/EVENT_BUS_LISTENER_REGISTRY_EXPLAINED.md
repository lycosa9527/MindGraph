# Event Bus Listener Registry - Detailed Explanation

## The Problem We're Solving

### Current Situation

**Without Listener Registry:**
```javascript
// InteractiveEditor registers listeners
this.eventBus.on('diagram:node_added', (data) => { ... });
this.eventBus.on('diagram:nodes_deleted', (data) => { ... });
this.eventBus.on('diagram:node_updated', (data) => { ... });

// Later, in destroy():
this.eventBus.off('diagram:node_added', callback1);  // ❌ Need to store callback reference
this.eventBus.off('diagram:nodes_deleted', callback2); // ❌ Need to store callback reference
this.eventBus.off('diagram:node_updated', callback3);  // ❌ Need to store callback reference
```

**Problems:**
1. Must manually store all callback references
2. Must manually remove each listener individually
3. Easy to forget to remove a listener (memory leak)
4. No way to see "who owns which listeners" (debugging is hard)
5. No centralized tracking of listener ownership

---

## The Solution: Listener Registry

### Concept

**Listener Registry = Ownership Tracking System**

The Event Bus tracks which module/owner registered each listener, enabling:
- Automatic cleanup by owner
- Debugging: "Show me all listeners owned by InteractiveEditor"
- Leak detection: "Which modules have listeners that weren't cleaned up?"

---

## How It Works

### Step 1: Enhanced Event Bus API

```javascript
// In event-bus.js
class EventBus {
    constructor(logger) {
        // ... existing code ...
        this.listeners = {}; // Existing: { eventName: [callback1, callback2, ...] }
        this.listenerRegistry = new Map(); // NEW: Track ownership
        // Map structure: {
        //   'InteractiveEditor' => [{ event: 'diagram:node_added', callback: fn1 }, ...],
        //   'ViewManager' => [{ event: 'view:zoom_in_requested', callback: fn2 }, ...]
        // }
    }
    
    /**
     * Register listener WITH owner tracking
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @param {string} owner - Owner identifier (e.g., "InteractiveEditor", "ViewManager")
     * @returns {Function} Unsubscribe function
     */
    onWithOwner(event, callback, owner) {
        // 1. Register listener normally (existing behavior)
        this.on(event, callback);
        
        // 2. Track ownership in registry
        if (!this.listenerRegistry.has(owner)) {
            this.listenerRegistry.set(owner, []);
        }
        this.listenerRegistry.get(owner).push({ event, callback });
        
        // 3. Return unsubscribe function that removes from both places
        return () => {
            this.off(event, callback); // Remove from listeners
            this.removeFromRegistry(owner, event, callback); // Remove from registry
        };
    }
    
    /**
     * Remove specific listener from registry
     */
    removeFromRegistry(owner, event, callback) {
        const ownerListeners = this.listenerRegistry.get(owner);
        if (!ownerListeners) return;
        
        const index = ownerListeners.findIndex(
            item => item.event === event && item.callback === callback
        );
        if (index > -1) {
            ownerListeners.splice(index, 1);
        }
        
        // Clean up empty owner entries
        if (ownerListeners.length === 0) {
            this.listenerRegistry.delete(owner);
        }
    }
    
    /**
     * Remove ALL listeners for an owner (ONE LINE CLEANUP!)
     * @param {string} owner - Owner identifier
     */
    removeAllListenersForOwner(owner) {
        const listeners = this.listenerRegistry.get(owner) || [];
        
        listeners.forEach(({ event, callback }) => {
            this.off(event, callback); // Remove from Event Bus
        });
        
        this.listenerRegistry.delete(owner); // Remove from registry
        
        if (listeners.length > 0) {
            this.logger.debug('EventBus', `Removed ${listeners.length} listeners for ${owner}`);
        }
    }
    
    /**
     * Get all listeners for an owner (for debugging)
     * @param {string} owner - Owner identifier
     * @returns {Array} List of {event, callback}
     */
    getListenersForOwner(owner) {
        return this.listenerRegistry.get(owner) || [];
    }
    
    /**
     * Get all active listeners grouped by owner (for debugging)
     * @returns {Object} { owner: [{event, callback}, ...] }
     */
    getAllListeners() {
        const result = {};
        this.listenerRegistry.forEach((listeners, owner) => {
            result[owner] = listeners.map(l => ({ event: l.event, callback: l.callback.toString() }));
        });
        return result;
    }
}
```

---

## Usage Examples

### Example 1: InteractiveEditor (Before → After)

**BEFORE (Current Approach - Manual Management):**
```javascript
class InteractiveEditor {
    constructor() {
        this.eventBus = window.eventBus;
        
        // Must store all callback references manually
        this.eventBusListeners = {};
        
        this.eventBusListeners.nodeAdded = (data) => {
            if (!this.selectionManager) return; // Guard check
            // ... handle event
        };
        this.eventBusListeners.nodesDeleted = (data) => {
            if (!this.selectionManager) return; // Guard check
            // ... handle event
        };
        this.eventBusListeners.nodeUpdated = (data) => {
            if (!this.selectionManager) return; // Guard check
            // ... handle event
        };
        
        // Register each listener individually
        this.eventBus.on('diagram:node_added', this.eventBusListeners.nodeAdded);
        this.eventBus.on('diagram:nodes_deleted', this.eventBusListeners.nodesDeleted);
        this.eventBus.on('diagram:node_updated', this.eventBusListeners.nodeUpdated);
    }
    
    destroy() {
        // Must manually remove each listener
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
        }
    }
}
```

**AFTER (With Listener Registry - Automatic Cleanup):**
```javascript
class InteractiveEditor {
    constructor() {
        this.eventBus = window.eventBus;
        this.ownerId = 'InteractiveEditor'; // Unique owner identifier
        
        // Register listeners with owner tracking
        this.eventBus.onWithOwner('diagram:node_added', 
            (data) => {
                if (!this.selectionManager) return; // Guard check
                // ... handle event
            },
            this.ownerId
        );
        
        this.eventBus.onWithOwner('diagram:nodes_deleted',
            (data) => {
                if (!this.selectionManager) return; // Guard check
                // ... handle event
            },
            this.ownerId
        );
        
        this.eventBus.onWithOwner('diagram:node_updated',
            (data) => {
                if (!this.selectionManager) return; // Guard check
                // ... handle event
            },
            this.ownerId
        );
    }
    
    destroy() {
        // ONE LINE CLEANUP - removes ALL listeners for this owner!
        this.eventBus.removeAllListenersForOwner(this.ownerId);
    }
}
```

**Benefits:**
- ✅ **Fewer lines of code** (no need to store callback references)
- ✅ **One-line cleanup** instead of 8+ lines
- ✅ **Impossible to forget** a listener (automatic cleanup)
- ✅ **No manual tracking** needed

---

### Example 2: ViewManager

**BEFORE:**
```javascript
class ViewManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        // ... store 10+ callback references
        this.setupListeners();
    }
    
    setupListeners() {
        this.callbacks = {
            zoomIn: () => this.zoomIn(),
            zoomOut: () => this.zoomOut(),
            fitToWindow: () => this.fitToWindow(),
            // ... 10+ more
        };
        
        Object.entries(this.callbacks).forEach(([key, callback], index) => {
            const eventName = this.getEventName(key); // Complex mapping
            this.eventBus.on(eventName, callback);
        });
    }
    
    destroy() {
        // Must manually remove all 10+ listeners
        Object.entries(this.callbacks).forEach(([key, callback]) => {
            const eventName = this.getEventName(key);
            this.eventBus.off(eventName, callback);
        });
    }
}
```

**AFTER:**
```javascript
class ViewManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.ownerId = 'ViewManager';
        this.setupListeners();
    }
    
    setupListeners() {
        // Register with owner tracking
        this.eventBus.onWithOwner('view:zoom_in_requested', 
            () => this.zoomIn(), 
            this.ownerId
        );
        this.eventBus.onWithOwner('view:zoom_out_requested',
            () => this.zoomOut(),
            this.ownerId
        );
        // ... 10+ more listeners
    }
    
    destroy() {
        // ONE LINE - removes all listeners!
        this.eventBus.removeAllListenersForOwner(this.ownerId);
    }
}
```

---

### Example 3: Debugging

**Before (Can't see ownership):**
```javascript
// How many listeners does InteractiveEditor have?
// ❌ Can't tell - no way to query by owner

// Did InteractiveEditor clean up properly?
// ❌ Can't check - no tracking
```

**After (Full visibility):**
```javascript
// See all listeners owned by InteractiveEditor
const editorListeners = window.eventBus.getListenersForOwner('InteractiveEditor');
console.log('InteractiveEditor listeners:', editorListeners);
// Output: [
//   { event: 'diagram:node_added', callback: [Function] },
//   { event: 'diagram:nodes_deleted', callback: [Function] },
//   { event: 'diagram:node_updated', callback: [Function] }
// ]

// See ALL listeners grouped by owner
const allListeners = window.eventBus.getAllListeners();
console.log('All listeners by owner:', allListeners);
// Output: {
//   'InteractiveEditor': [ ... ],
//   'ViewManager': [ ... ],
//   'InteractionHandler': [ ... ]
// }

// Check for leaks after cleanup
window.sessionLifecycle.cleanup();
const remaining = window.eventBus.getAllListeners();
if (Object.keys(remaining).length > 0) {
    console.warn('Listener leak detected:', remaining);
}
```

---

## Migration Strategy

### Phase 1: Add Feature to Event Bus (Backward Compatible)

```javascript
// Existing code still works:
eventBus.on('event', callback);  // ✅ Still works
eventBus.off('event', callback);   // ✅ Still works

// New feature available:
eventBus.onWithOwner('event', callback, 'Owner'); // ✅ New feature
eventBus.removeAllListenersForOwner('Owner');     // ✅ New feature
```

### Phase 2: Gradual Migration

**Option A: Migrate module by module**
1. Start with `InteractiveEditor` (most complex)
2. Then `ViewManager`, `InteractionHandler`
3. Then other modules
4. Old code continues to work

**Option B: Hybrid approach**
- New code uses `onWithOwner()`
- Old code continues using `on()`
- Both work together

### Phase 3: Add Verification

```javascript
// In SessionLifecycleManager
cleanup() {
    // ... existing cleanup ...
    
    // Verify listeners are cleaned up
    const remaining = window.eventBus.getAllListeners();
    const sessionOwners = ['InteractiveEditor', 'ViewManager', 'InteractionHandler', ...];
    
    sessionOwners.forEach(owner => {
        if (remaining[owner] && remaining[owner].length > 0) {
            logger.warn('SessionLifecycle', `Listener leak detected for ${owner}`, {
                count: remaining[owner].length,
                events: remaining[owner].map(l => l.event)
            });
        }
    });
}
```

---

## Key Benefits

### 1. **Simplified Cleanup**
```javascript
// Before: 20+ lines of manual cleanup
// After: 1 line
this.eventBus.removeAllListenersForOwner(this.ownerId);
```

### 2. **Automatic Leak Prevention**
- Can't forget to remove a listener (automatic cleanup)
- Can detect leaks (query by owner)

### 3. **Better Debugging**
- See all listeners by owner
- Identify which module has too many listeners
- Track listener lifecycle

### 4. **Backward Compatible**
- Existing code continues to work
- No breaking changes
- Gradual migration possible

### 5. **Centralized but Correct**
- Event Bus manages listeners (correct place)
- No architectural violations
- Clear separation of concerns

---

## Comparison: Before vs After

| Feature | Before | After |
|--------|--------|-------|
| **Manual cleanup** | ✅ Must store callbacks, remove individually | ✅ One-line automatic cleanup |
| **Listener tracking** | ❌ No tracking | ✅ Tracked by owner |
| **Debugging** | ❌ Can't see ownership | ✅ Full visibility |
| **Leak detection** | ❌ Manual inspection | ✅ Automatic detection |
| **Code complexity** | ❌ High (store + remove) | ✅ Low (just register) |
| **Error-prone** | ❌ Easy to forget cleanup | ✅ Impossible to forget |
| **Architectural** | ✅ Good | ✅ Good (no violations) |

---

## Summary

**Listener Registry** = Event Bus tracks which module owns each listener

**Key Methods:**
- `onWithOwner(event, callback, owner)` - Register with ownership
- `removeAllListenersForOwner(owner)` - One-line cleanup
- `getListenersForOwner(owner)` - Debugging
- `getAllListeners()` - Full visibility

**Result:**
- Centralized management ✅
- Automatic cleanup ✅
- Better debugging ✅
- No architectural violations ✅
- Backward compatible ✅

