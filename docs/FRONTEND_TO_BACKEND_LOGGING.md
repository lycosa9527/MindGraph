# Frontend to Backend Logging

## Overview

The logging system now **bridges browser console logs to your Python backend terminal**, giving you full visibility of what's happening in users' browsers.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (Frontend)                          │
│                                                                     │
│  User Action → logger.debug('Editor', 'Node clicked')              │
│                                                                     │
│  ┌─────────────┐                                                   │
│  │  logger.js  │ ──> Console: [14:23:15] DEBUG | Editor | ...     │
│  └─────────────┘                                                   │
│         │                                                           │
│         │ fetch('/api/frontend_log')                               │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          │ HTTP POST
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                     Python Backend (FastAPI)                        │
│                                                                     │
│  /api/frontend_log endpoint                                        │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────┐                                               │
│  │ frontend_logger │ ──> Terminal: [TIME] DEBUG | FRNT | ...       │
│  └─────────────────┘                                               │
│                                                                     │
│  Your Python console shows browser logs in real-time! 🎉           │
└─────────────────────────────────────────────────────────────────────┘
```

## What Gets Sent to Backend

### Production Mode (debug=false, default)
```javascript
// Only critical logs sent to backend
logger.warn()  → Backend ✅ (always sent)
logger.error() → Backend ✅ (always sent)
logger.info()  → Backend ❌ (not sent)
logger.debug() → Backend ❌ (not sent)
```

### Debug Mode (debug=true or ?debug=1)
```javascript
// ALL logs sent to backend
logger.debug() → Backend ✅ (sent in debug mode)
logger.info()  → Backend ✅ (sent in debug mode)
logger.warn()  → Backend ✅ (always sent)
logger.error() → Backend ✅ (always sent)
```

## Example Flow

### Step 1: User visits editor with debug mode
```
URL: http://localhost:9527/editor?debug=1
```

### Step 2: User clicks "Add Node"
**Browser Console:**
```
[14:23:15] DEBUG | ToolbarManager       | Add node clicked
```

**Python Terminal (your backend):**
```
[14:23:15] DEBUG | FRNT | [ToolbarManager] Add node clicked
```

### Step 3: Error occurs
**Browser Console:**
```
[14:23:20] ERROR | Editor               | Rendering failed { error: 'Invalid spec' }
```

**Python Terminal:**
```
[14:23:20] ERROR | FRNT | [Editor] Rendering failed | {"error":"Invalid spec"}
```

## Backend Log Format

Logs from browser appear in your Python terminal as:

```
[TIME] LEVEL | FRNT | [Component] Message | Data
```

Where:
- `FRNT` = Frontend logs (easy to identify)
- `Component` = The JS component that logged (Editor, ToolbarManager, etc.)
- `Message` = The log message
- `Data` = Structured data (if provided)

## Real-World Example

**User performs auto-complete in debug mode:**

### Browser Console:
```
[14:25:10] INFO  | ToolbarManager       | Auto-complete started
[14:25:10] DEBUG | ToolbarManager       | Process started { diagramType: 'circle_map', nodeCount: 5 }
[14:25:12] DEBUG | ToolbarManager       | LLM request sent { model: 'qwen' }
[14:25:15] DEBUG | ToolbarManager       | Response received { nodes: 8 }
[14:25:15] INFO  | ToolbarManager       | Auto-complete completed
```

### Python Terminal (Backend):
```
[14:25:10] INFO  | FRNT | [ToolbarManager] Auto-complete started
[14:25:10] DEBUG | FRNT | [ToolbarManager] Process started | {"diagramType":"circle_map","nodeCount":5}
[14:25:12] DEBUG | FRNT | [ToolbarManager] LLM request sent | {"model":"qwen"}
[14:25:15] DEBUG | FRNT | [ToolbarManager] Response received | {"nodes":8}
[14:25:15] INFO  | FRNT | [ToolbarManager] Auto-complete completed
```

**You see everything happening in the browser, directly in your Python terminal!**

## Testing

### Test 1: Debug Mode ON

1. **Start your server:**
   ```bash
   python run_server.py
   ```

2. **Open browser with debug mode:**
   ```
   http://localhost:9527/editor?debug=1
   ```

3. **Perform actions** (create diagram, add nodes, etc.)

4. **Check Python terminal:**
   ```
   [TIME] DEBUG | FRNT | [Editor] Initializing editor for circle_map
   [TIME] DEBUG | FRNT | [Editor] Editor created | {"diagramType":"circle_map","hasTemplate":true}
   [TIME] DEBUG | FRNT | [ToolbarManager] Add node clicked
   ```

### Test 2: Production Mode

1. **Open browser WITHOUT debug:**
   ```
   http://localhost:9527/editor
   ```

2. **Perform actions**

3. **Check Python terminal:**
   ```
   (No DEBUG/INFO logs - only WARN/ERROR will appear)
   ```

4. **Trigger a warning** (e.g., try operation without selecting nodes):
   ```
   [TIME] WARN  | FRNT | [ToolbarManager] No nodes selected
   ```

## Benefits

### For K12 Teachers (Production)
- ✅ Clean experience (no console spam)
- ✅ Errors automatically reported to you
- ✅ No performance impact

### For You (Development)
- ✅ See what users are doing in real-time
- ✅ Debug issues remotely
- ✅ Full visibility into browser behavior
- ✅ Structured, searchable logs
- ✅ All logs in one place (Python terminal)

## Configuration

### Enable Debug Mode Persistently

**In browser console:**
```javascript
enableDebug()  // Stores in localStorage
// Refresh page - debug mode persists!
```

### Check Current State

```javascript
window.logger.debugMode  // true or false
```

### Backend Log Level

Your Python backend respects `LOG_LEVEL` from `.env`:

```bash
# In .env file
LOG_LEVEL=DEBUG   # See all frontend logs
LOG_LEVEL=INFO    # See INFO, WARN, ERROR
LOG_LEVEL=WARN    # See only WARN, ERROR
LOG_LEVEL=ERROR   # See only ERROR
```

## Advanced: Filtering Backend Logs

If you only want to see frontend logs:

```bash
# In your terminal, run:
python run_server.py | grep FRNT
```

Output:
```
[14:23:15] DEBUG | FRNT | [Editor] Initializing editor...
[14:23:16] DEBUG | FRNT | [ToolbarManager] Add node clicked
[14:23:20] ERROR | FRNT | [Editor] Rendering failed
```

## Troubleshooting

### Not seeing logs in backend?

**Check 1: Debug mode enabled?**
```javascript
// In browser console
window.logger.debugMode
// Should return: true
```

**Check 2: Backend LOG_LEVEL**
```bash
# In .env file
LOG_LEVEL=DEBUG  # Make sure it's set to DEBUG
```

**Check 3: Network requests**
```
Open DevTools → Network tab
Filter: "frontend_log"
Should see POST requests being sent
```

### Too many logs in production?

```javascript
// Disable debug mode
disableDebug()

// Or clear localStorage
localStorage.removeItem('mindgraph_debug')
```

## Summary

| Feature | Production | Debug Mode |
|---------|-----------|------------|
| **Browser Console** | Clean (WARN/ERROR only) | Full logs (all levels) |
| **Backend Terminal** | WARN/ERROR only | Full logs (all levels) |
| **Performance** | Minimal overhead | Slight overhead (logging) |
| **Use Case** | End users (teachers) | Development & debugging |

---

**Made by MindSpring Team | Author: lycosa9527**

