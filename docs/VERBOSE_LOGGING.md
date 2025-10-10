# Verbose Logging System

## Overview

The Verbose Logging System provides comprehensive, real-time logging of all user interactions and backend operations for debugging and development purposes.

## Quick Start

### Enable Verbose Logging

1. **Copy `.env.example` to `.env`** (if not already done):
   ```bash
   cp env.example .env
   ```

2. **Set the flag in `.env`**:
   ```bash
   VERBOSE_LOGGING=True
   ```

3. **Restart the application**:
   ```bash
   python run_server.py
   ```

4. **Verify activation** - You should see:
   ```
   [INIT] VERBOSE_LOGGING enabled - setting log level to DEBUG
   [HH:MM:SS] INFO | MAIN | VERBOSE mode ENABLED
   ```

## What Gets Logged

### Frontend Events (Browser → Backend Terminal)

| Event Type | Icon | Information Logged |
|------------|------|-------------------|
| **Mouse Click** | 🖱️ | Node ID, modifier keys (Ctrl/Alt/Shift), coordinates, diagram type |
| **Double-Click** | ✏️ | Node ID, diagram type, timestamp (for edit mode) |
| **Text Edit** | 📝 | Node ID, text preview (first 50 chars), text length, diagram type |
| **Node Selection** | 🎯 | Selected node IDs (array), selection count, diagram type |
| **Drag Start** | 🖱️ | Node ID, diagram type, mouse coordinates |
| **Drag End** | 🖱️ | Node ID, final position (x, y), diagram type |

### Backend Operations

| Component | What's Logged |
|-----------|--------------|
| **ThinkGuide Agent** | Workflow state transitions, intent detection, LLM calls, diagram updates |
| **API Endpoints** | Request parameters, response times, errors |
| **LLM Clients** | Model selection, token usage, API calls |
| **Services** | Diagram generation, file operations |

## Log Format

All logs use a unified, color-coded format:

```
[HH:MM:SS] LEVEL | SRC  | Message
```

- **Timestamp**: `[HH:MM:SS]` - 24-hour format
- **Level**: Color-coded (DEBUG=cyan, INFO=green, WARN=yellow, ERROR=red)
- **Source**: 4-char abbreviation (FRNT=Frontend, AGNT=Agent, API=API, etc.)
- **Message**: Detailed log message with context data

## Example Output

### Frontend Events
```
[10:15:32] DEBUG | FRNT | [InteractiveEditor] 🖱️ Mouse Click | {"nodeId":"node_1","ctrlKey":false,"clientX":450,"clientY":320,"diagramType":"circle_map"}
[10:15:34] DEBUG | FRNT | [InteractiveEditor] ✏️ Double-Click for Edit | {"nodeId":"node_1","diagramType":"circle_map","timestamp":1760093334567}
[10:15:38] DEBUG | FRNT | [InteractiveEditor] 📝 Text Edit Applied | {"nodeId":"node_1","newText":"Updated Topic","textLength":13,"diagramType":"circle_map"}
[10:15:40] DEBUG | FRNT | [InteractiveEditor] 🎯 Node Selection Changed | {"count":2,"nodeIds":["node_1","node_3"],"diagramType":"circle_map"}
```

### Backend Agent Operations
```
[10:16:15] DEBUG | AGNT | [ThinkGuide] User intent detected: update_properties
[10:16:15] DEBUG | AGNT | [ThinkGuide] Applying property update to node_2: {"fillColor":"#ff0000","bold":true}
[10:16:16] INFO  | AGNT | [ThinkGuide] Diagram update sent: update_properties
```

## Use Cases

### 1. Bug Investigation
**Scenario**: User reports "clicking doesn't work sometimes"

**Solution**: Enable verbose logging and ask user to reproduce:
```
[10:20:15] DEBUG | FRNT | 🖱️ Mouse Click | {"nodeId":"node_3","ctrlKey":false}
[10:20:15] DEBUG | FRNT | 🎯 Node Selection Changed | {"count":0,"nodeIds":[]}
```
→ Selection cleared but not set! Found the bug.

### 2. Performance Analysis
**Scenario**: Check how long operations take

**Solution**: Use timestamps to calculate deltas:
```
[10:25:10] DEBUG | FRNT | ✏️ Double-Click for Edit | {"timestamp":1760093510234}
[10:25:12] DEBUG | FRNT | 📝 Text Edit Applied | {"timestamp":1760093512891}
```
→ Edit took 2.657 seconds (2891 - 510 = 2657ms)

### 3. Agent Debugging
**Scenario**: ThinkGuide makes unexpected diagram changes

**Solution**: Trace the entire decision flow:
```
[10:30:05] DEBUG | AGNT | [ThinkGuide] Received message: "make the first node red"
[10:30:06] DEBUG | AGNT | [ThinkGuide] LLM intent: {"action":"update_properties","target":"node_0","properties":{"fillColor":"red"}}
[10:30:06] INFO  | AGNT | [ThinkGuide] Applying property update to node_0
[10:30:06] DEBUG | AGNT | [ThinkGuide] Sending SSE: diagram_update
```
→ See exactly how LLM interpreted the command and what action was taken

## Technical Details

### Frontend Implementation

**File**: `static/js/logger.js`
- `verboseMode` flag set from backend via `window.VERBOSE_LOGGING`
- Automatically enables DEBUG level when active
- All DEBUG and INFO logs sent to backend via `/api/frontend_log`

**File**: `static/js/editor/interactive-editor.js`
- Event handlers enhanced with `logger.debug()` calls
- Rich context data attached to each log
- Non-blocking: logging errors don't break UI

### Backend Implementation

**File**: `config/settings.py`
- `VERBOSE_LOGGING` property reads from environment
- Returns boolean `True`/`False`

**File**: `main.py`
- Checks `config.VERBOSE_LOGGING` during startup
- Overrides `LOG_LEVEL` to `DEBUG` when enabled
- Applies to all loggers (agents, services, API)

**File**: `routers/pages.py`
- Passes `verbose_logging` flag to Jinja2 template
- Rendered as `window.VERBOSE_LOGGING` in HTML

**API Endpoint**: `/api/frontend_log`
- Receives frontend logs via POST
- Routes to dedicated `frontend` logger
- Non-blocking (failures ignored)

## Best Practices

### 1. Development Mode Only
```bash
# Development .env
VERBOSE_LOGGING=True
DEBUG=True

# Production .env
VERBOSE_LOGGING=False
DEBUG=False
```

### 2. Filter Logs in Console
Since verbose mode generates many logs, use browser console filters:
```javascript
// Show only mouse clicks
logger.debug('InteractiveEditor', '🖱️ Mouse Click', ...)

// Filter in Chrome DevTools: "🖱️"
// Filter in console: Ctrl+F "Mouse Click"
```

### 3. Log File Review
All logs also saved to `logs/app.log`:
```bash
# View recent logs
tail -f logs/app.log

# Filter specific events
grep "Mouse Click" logs/app.log

# Filter by timestamp
grep "10:30:" logs/app.log
```

## Disabling Verbose Logging

1. **Option 1**: Set to `False` in `.env`:
   ```bash
   VERBOSE_LOGGING=False
   ```

2. **Option 2**: Comment out the line:
   ```bash
   # VERBOSE_LOGGING=True
   ```

3. **Option 3**: Delete from `.env` (defaults to `False`)

4. **Restart the application** for changes to take effect

## Performance Impact

### Frontend
- **Minimal**: Logs only sent when verbose mode enabled
- **Non-blocking**: `fetch()` with `.catch(() => {})` 
- **Debounced**: Duplicate log detection prevents spam

### Backend
- **Low**: DEBUG level adds ~5-10% overhead
- **Disk I/O**: Logs written to `logs/app.log` asynchronously
- **Network**: Frontend logs sent over existing HTTP connection

### Recommendations
- ✅ Enable during development and debugging
- ✅ Enable temporarily in production for specific user sessions
- ❌ Do NOT enable by default in production (log file growth)

## Troubleshooting

### Issue: Verbose logging not working

**Check 1**: Verify `.env` file
```bash
cat .env | grep VERBOSE_LOGGING
# Should show: VERBOSE_LOGGING=True
```

**Check 2**: Restart application
```bash
# Must restart for .env changes
python run_server.py
```

**Check 3**: Check startup logs
```
[INIT] VERBOSE_LOGGING enabled - setting log level to DEBUG
```

### Issue: Too many logs, performance degraded

**Solution**: Temporarily disable and restart
```bash
echo "VERBOSE_LOGGING=False" >> .env
python run_server.py
```

### Issue: Logs not showing in browser console

**Solution**: Open browser DevTools (F12) and check Console tab
```javascript
// Check if verbose mode is active
console.log(window.VERBOSE_LOGGING); // Should be true
logger.isVerbose(); // Should return true
```

## Related Documentation

- **Feature Flags**: See `env.example` for all available flags
- **Logging Configuration**: See `config/settings.py` for `LOG_LEVEL` options
- **Agent Logging**: See `agents/thinking_modes/circle_map_agent.py` for backend examples
- **Frontend Logger**: See `static/js/logger.js` for full API

---

**Author**: lycosa9527  
**Made by**: MindSpring Team  
**Last Updated**: 2025-10-10

