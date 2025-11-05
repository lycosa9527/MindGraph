# Event Bus Listener Management Analysis

## Current Architecture

### Separation of Concerns

1. **Event Bus** (`event-bus.js`)
   - Purpose: Pub/sub communication system
   - Responsibilities: Event emission, listener registration/removal
   - Pattern: Each module manages its own listeners

2. **State Manager** (`state-manager.js`)
   - Purpose: Single source of truth for application state
   - Responsibilities: State updates, state change notifications
   - Pattern: State changes emit events via Event Bus

3. **Session Lifecycle Manager** (`session-lifecycle.js`)
   - Purpose: Manager lifecycle tracking
   - Responsibilities: Registration, cleanup verification
   - Pattern: Ensures `destroy()` is called on all managers

## Why State Manager Should NOT Manage Listeners

### ❌ Problems with State Manager Approach

1. **Violates Separation of Concerns**
   - State Manager is for **state**, not **event coordination**
   - Would mix state management with event lifecycle management
   - Creates tight coupling between State Manager and Event Bus

2. **Architectural Issues**
   - State Manager would need to know about Event Bus internals
   - Would create circular dependencies (State Manager → Event Bus → State Manager)
   - Makes State Manager a "God Object" (too many responsibilities)

3. **Maintainability Issues**
   - Harder to understand who's responsible for what
   - Violates Single Responsibility Principle
   - Makes testing more complex

### ✅ Current Pattern is Better

**Current Approach (Each Module Manages Its Own Listeners):**
```javascript
class MyManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        // Store listener references
        this.callbacks = {
            event1: (data) => this.handleEvent1(data),
            event2: (data) => this.handleEvent2(data)
        };
        // Register listeners
        this.eventBus.on('event:1', this.callbacks.event1);
        this.eventBus.on('event:2', this.callbacks.event2);
    }
    
    destroy() {
        // Remove listeners
        this.eventBus.off('event:1', this.callbacks.event1);
        this.eventBus.off('event:2', this.callbacks.event2);
    }
}
```

**Benefits:**
- ✅ Clear ownership (each module owns its listeners)
- ✅ Standard pattern (matches React, Vue, Angular)
- ✅ Easy to understand and maintain
- ✅ No architectural violations

---

## Better Centralization Options

### Option 1: Enhance Event Bus with Listener Registry (RECOMMENDED)

**Add listener tracking to Event Bus itself:**

```javascript
// In event-bus.js
class EventBus {
    constructor(logger) {
        // ... existing code ...
        this.listenerRegistry = new Map(); // Track listeners by owner
    }
    
    /**
     * Register listener with owner tracking
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @param {string} owner - Owner identifier (e.g., "InteractiveEditor", "ViewManager")
     * @returns {Function} Unsubscribe function
     */
    onWithOwner(event, callback, owner) {
        this.on(event, callback);
        
        // Track ownership
        if (!this.listenerRegistry.has(owner)) {
            this.listenerRegistry.set(owner, []);
        }
        this.listenerRegistry.get(owner).push({ event, callback });
        
        // Return unsubscribe function
        return () => {
            this.off(event, callback);
            this.removeFromRegistry(owner, event, callback);
        };
    }
    
    /**
     * Remove all listeners for an owner
     * @param {string} owner - Owner identifier
     */
    removeAllListenersForOwner(owner) {
        const listeners = this.listenerRegistry.get(owner) || [];
        listeners.forEach(({ event, callback }) => {
            this.off(event, callback);
        });
        this.listenerRegistry.delete(owner);
    }
    
    /**
     * Get all listeners for an owner
     * @param {string} owner - Owner identifier
     * @returns {Array} List of {event, callback}
     */
    getListenersForOwner(owner) {
        return this.listenerRegistry.get(owner) || [];
    }
    
    /**
     * Get all active listeners (for debugging)
     * @returns {Object} { owner: [{event, callback}, ...] }
     */
    getAllListeners() {
        const result = {};
        this.listenerRegistry.forEach((listeners, owner) => {
            result[owner] = listeners;
        });
        return result;
    }
}
```

**Usage:**
```javascript
class InteractiveEditor {
    constructor() {
        this.eventBus = window.eventBus;
        this.ownerId = 'InteractiveEditor';
        
        // Register with owner tracking
        this.eventBus.onWithOwner('diagram:nodes_deleted', 
            (data) => this.handleDelete(data), 
            this.ownerId
        );
    }
    
    destroy() {
        // Automatic cleanup - removes all listeners for this owner
        this.eventBus.removeAllListenersForOwner(this.ownerId);
    }
}
```

**Benefits:**
- ✅ Centralized tracking (in Event Bus where it belongs)
- ✅ Automatic cleanup capabilities
- ✅ Better debugging (can see all listeners by owner)
- ✅ No architectural violations
- ✅ Optional (modules can still use `on()` if preferred)

---

### Option 2: Session Lifecycle Manager Verification

**Add listener cleanup verification to Session Lifecycle Manager:**

```javascript
// In session-lifecycle.js
class SessionLifecycleManager {
    cleanup() {
        // ... existing cleanup code ...
        
        // After cleanup, verify Event Bus listeners are cleaned up
        if (window.eventBus && typeof window.eventBus.getAllListeners === 'function') {
            const remainingListeners = window.eventBus.getAllListeners();
            const sessionListenerCount = Object.values(remainingListeners)
                .reduce((sum, listeners) => sum + listeners.length, 0);
            
            if (sessionListenerCount > 0) {
                logger.warn('SessionLifecycle', 'Potential listener leak detected', {
                    remainingListeners: sessionListenerCount,
                    details: remainingListeners
                });
            }
        }
    }
}
```

**Benefits:**
- ✅ Detects listener leaks
- ✅ No architectural changes needed
- ✅ Can be added incrementally

---

### Option 3: Dedicated Listener Registry (NOT RECOMMENDED)

**Create a separate ListenerRegistry class:**

```javascript
class ListenerRegistry {
    constructor(eventBus) {
        this.eventBus = eventBus;
        this.registry = new Map();
    }
    
    register(owner, event, callback) {
        // Register listener
        this.eventBus.on(event, callback);
        
        // Track it
        if (!this.registry.has(owner)) {
            this.registry.set(owner, []);
        }
        this.registry.get(owner).push({ event, callback });
    }
    
    unregisterAll(owner) {
        const listeners = this.registry.get(owner) || [];
        listeners.forEach(({ event, callback }) => {
            this.eventBus.off(event, callback);
        });
        this.registry.delete(owner);
    }
}
```

**Problems:**
- ❌ Adds another layer of abstraction
- ❌ Modules need to know about Registry
- ❌ More complex than needed
- ❌ Event Bus already provides the functionality

---

## Recommendation

### ✅ **Option 1: Enhance Event Bus with Listener Registry**

This is the best approach because:

1. **Centralized but Correct**: Event Bus is the right place for listener management
2. **Backward Compatible**: Can be added alongside existing `on()`/`off()` methods
3. **Optional**: Modules can opt-in to owner tracking
4. **Better Debugging**: Can see all listeners by owner
5. **Automatic Cleanup**: `removeAllListenersForOwner()` simplifies cleanup
6. **No Architectural Violations**: Keeps separation of concerns

### Implementation Plan

1. **Phase 1**: Add `onWithOwner()` and `removeAllListenersForOwner()` to Event Bus
2. **Phase 2**: Update `InteractiveEditor` to use owner tracking
3. **Phase 3**: Gradually migrate other modules to use owner tracking
4. **Phase 4**: Add verification in Session Lifecycle Manager

### Migration Path

```javascript
// Old way (still works)
this.eventBus.on('event', callback);
this.eventBus.off('event', callback);

// New way (with owner tracking)
this.eventBus.onWithOwner('event', callback, 'MyManager');
this.eventBus.removeAllListenersForOwner('MyManager');
```

---

## Summary

**Question**: Should State Manager manage Event Bus listeners?

**Answer**: **No**. State Manager should focus on state. Event Bus should manage listeners.

**Better Solution**: Enhance Event Bus with listener registry/owner tracking for centralized management without violating separation of concerns.

