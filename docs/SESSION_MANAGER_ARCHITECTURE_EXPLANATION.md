# SessionManager Architecture Explanation

## Current Situation: Two Different "Session" Systems

**⚠️ IMPORTANT**: There are **TWO separate systems** with similar names:

1. **SessionManager** (`session-manager.js`) - Toolbar instance tracking
2. **SessionLifecycleManager** (`session-lifecycle.js`) - Manager lifecycle tracking

They serve **different purposes** and work **independently**.

---

## 1. SessionManager (`managers/toolbar/session-manager.js`)

### Purpose
**Manages ToolbarManager instance lifecycle** - specifically tracks which ToolbarManager belongs to which session.

### What It Does

1. **Tracks ToolbarManager Instances**
   - Maintains `window.toolbarManagerRegistry` (global Map: `sessionId → ToolbarManager`)
   - Registers new ToolbarManager instances when sessions start
   - Cleans up old ToolbarManager instances when sessions end

2. **Session Validation**
   - Validates if a session ID is still active
   - Used by other modules to check if they should execute operations

3. **Session Cleanup**
   - Removes ToolbarManager from registry when session ends
   - Destroys old ToolbarManager instances

### How It Works

**Uses Event Bus: ✅ YES**
```javascript
// Listens to:
- 'session:register_requested' → Register ToolbarManager instance
- 'session:validate_requested' → Validate session ID
- 'session:cleanup_requested' → Cleanup session

// Emits:
- 'session:registered' → When instance registered
- 'session:validation_result' → Session validation result
- 'session:cleanup_completed' → When cleanup done
- 'session:old_instance_cleanup' → When old instance cleaned
```

**Uses State Manager: ❌ NO (not really)**
- Receives `stateManager` in constructor but **doesn't use it**
- Only stores it as `this.stateManager` but never calls methods on it
- **Could be removed from constructor** - not needed

**Works with Session Lifecycle Manager: ❌ NO (separate systems)**
- SessionManager is **tracked BY** SessionLifecycleManager (one of the 18 managers)
- But they don't communicate with each other
- They track different things (ToolbarManager instances vs. all managers)

### Current Usage

**Where it's used:**
- `diagram-selector.js` line 484: Created and registered with SessionLifecycleManager
- Other modules emit `session:validate_requested` to validate sessions
- `autocomplete-manager.js` listens to `session:cleanup_requested`
- `node-counter-feature-mode-manager.js` listens to `session:validate_requested`

**Global Registry:**
```javascript
window.toolbarManagerRegistry = new Map(); // sessionId → ToolbarManager
```

---

## 2. SessionLifecycleManager (`core/session-lifecycle.js`)

### Purpose
**Centralized manager lifecycle tracking** - ensures ALL 18 managers are properly destroyed during session cleanup.

### What It Does

1. **Tracks ALL Managers**
   - Registers all 18 managers (ViewManager, InteractionHandler, SessionManager, etc.)
   - Tracks them in `this.managers` array
   - Calls `destroy()` on all managers when session ends

2. **Automatic Cleanup**
   - Ensures no memory leaks
   - Destroys managers in reverse order (LIFO)
   - Handles errors gracefully

### How It Works

**Uses Event Bus: ❌ NO**
- Does NOT use Event Bus
- Direct method calls only (`register()`, `cleanup()`)

**Uses State Manager: ❌ NO**
- Does NOT use State Manager
- Pure manager registry system

**Works with SessionManager: ✅ YES (indirectly)**
- SessionManager is **one of the managers** tracked by SessionLifecycleManager
- When SessionLifecycleManager calls `cleanup()`, it calls `SessionManager.destroy()`
- SessionManager.destroy() then cleans up ToolbarManager instances

---

## Key Differences

| Feature | SessionManager | SessionLifecycleManager |
|---------|---------------|------------------------|
| **Purpose** | Track ToolbarManager instances | Track ALL 18 managers |
| **Scope** | ToolbarManager only | All managers |
| **Registry** | `window.toolbarManagerRegistry` | `this.managers` array |
| **Event Bus** | ✅ YES (3 listeners) | ❌ NO |
| **State Manager** | ❌ NO (not used) | ❌ NO |
| **Lifecycle** | ToolbarManager lifecycle | All managers lifecycle |
| **Location** | `managers/toolbar/` | `core/` |
| **Global** | `window.toolbarManagerRegistry` | `window.sessionLifecycle` |

---

## Current Architecture Flow

```
┌─────────────────────────────────────────────────────────┐
│ DiagramSelector.transitionToEditor()                     │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 1. SessionLifecycleManager.startSession()                │
│    - Sets currentSessionId                               │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Create all 18 managers                                │
│    - ViewManager, InteractionHandler, SessionManager...   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 3. SessionLifecycleManager.register() for each           │
│    - Adds to this.managers array                         │
│    - SessionManager is one of them                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 4. SessionManager (via Event Bus)                       │
│    - Listens to 'session:register_requested'           │
│    - Registers ToolbarManager in window.toolbarManagerRegistry │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 5. User closes editor → DiagramSelector.backToGallery()  │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 6. SessionLifecycleManager.cleanup()                     │
│    - Calls destroy() on all 18 managers (reverse order) │
│    - Includes SessionManager.destroy()                  │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ 7. SessionManager.destroy()                              │
│    - Calls cleanupAllSessions()                        │
│    - Removes ToolbarManager from window.toolbarManagerRegistry │
│    - Destroys ToolbarManager instances                  │
└─────────────────────────────────────────────────────────┘
```

---

## Issues & Recommendations

### Issue 1: SessionManager Doesn't Use State Manager

**Current:**
```javascript
constructor(eventBus, stateManager, logger) {
    this.stateManager = stateManager; // ❌ Stored but never used
}
```

**Recommendation:**
- **Option A**: Remove `stateManager` from constructor (simplest)
- **Option B**: Use State Manager to track session state (if needed)

### Issue 2: Potential Overlap with SessionLifecycleManager

**Question**: Do we need both systems?

**Answer**: 
- **SessionManager**: Specific to ToolbarManager tracking (legacy/legacy support)
- **SessionLifecycleManager**: General manager lifecycle (newer, better)

**Recommendation**:
- Keep both for now (SessionManager might be used by legacy code)
- Consider deprecating SessionManager in future if ToolbarManager is always tracked by SessionLifecycleManager

### Issue 3: SessionManager Should Use Listener Registry

**Current:**
```javascript
this.eventBus.on('session:register_requested', ...);
this.eventBus.on('session:validate_requested', ...);
this.eventBus.on('session:cleanup_requested', ...);
```

**Recommendation:**
- Migrate to `onWithOwner()` when implementing Listener Registry
- Use `ownerId = 'SessionManager'`
- Simplify `destroy()` to use `removeAllListenersForOwner()`

---

## Summary

### SessionManager
- ✅ **MUST** work with Event Bus (listens to 3 events)
- ❌ Does NOT need State Manager (currently unused)
- ❌ Does NOT work with SessionLifecycleManager (separate systems)
- **Purpose**: Track ToolbarManager instances per session

### SessionLifecycleManager
- ❌ Does NOT use Event Bus
- ❌ Does NOT use State Manager
- ✅ **Tracks** SessionManager (as one of 18 managers)
- **Purpose**: Ensure all managers are destroyed properly

### Relationship
```
SessionLifecycleManager (parent)
    └── SessionManager (one of 18 tracked managers)
            └── ToolbarManager (tracked in window.toolbarManagerRegistry)
```

---

## Migration Checklist for Listener Registry

When implementing Listener Registry:

- [ ] **SessionManager**: Add `ownerId = 'SessionManager'`
- [ ] **SessionManager**: Replace 3 `eventBus.on()` with `eventBus.onWithOwner()`
- [ ] **SessionManager**: Update `destroy()` to use `removeAllListenersForOwner()`
- [ ] **SessionManager**: Consider removing unused `stateManager` parameter

