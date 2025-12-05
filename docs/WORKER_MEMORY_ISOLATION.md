# Why In-Memory Storage Doesn't Work Across Workers

## The Problem

When uvicorn runs with `workers=4`, it creates **4 separate processes**, each with **isolated memory**.

### Scenario: Captcha Generation and Verification

```
Time 0: User requests captcha
  ↓
Request → Master Process → Routes to Worker 1
  ↓
Worker 1 generates captcha: "ABCD"
Worker 1 stores in memory: captcha_store["abc-123"] = "ABCD"
  ↓
[Worker 1's memory: {"abc-123": "ABCD"}]
[Worker 2's memory: {}]  ← Empty!
[Worker 3's memory: {}]  ← Empty!
[Worker 4's memory: {}]  ← Empty!

Time 1: User submits login with captcha "ABCD"
  ↓
Request → Master Process → Routes to Worker 3 (load balancing)
  ↓
Worker 3 checks memory: captcha_store["abc-123"]
  ↓
Result: NOT FOUND! ❌
  ↓
Error: "Captcha not found"
```

## Why This Happens

### Process Isolation

Each worker process has:
- **Separate memory space** (can't access other processes' memory)
- **Separate Python interpreter** (separate `captcha_store` dict)
- **Separate file descriptors** (separate connections)

### Visual Representation

```
┌─────────────────────────────────────────────────┐
│  Worker 1 Process (PID 1001)                    │
│  ┌───────────────────────────────────────────┐  │
│  │ Memory Space                               │  │
│  │ captcha_store = {"abc-123": "ABCD"}        │  │
│  │                                             │  │
│  │ ❌ Cannot access Worker 2's memory          │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Worker 2 Process (PID 1002)                    │
│  ┌───────────────────────────────────────────┐  │
│  │ Memory Space                               │  │
│  │ captcha_store = {}  ← Empty!              │  │
│  │                                             │  │
│  │ ❌ Cannot access Worker 1's memory          │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Solutions Comparison

### ❌ Pure In-Memory (Doesn't Work)

```python
# routers/auth.py
captcha_store = {}  # Each worker has its own copy!

# Worker 1 generates captcha
captcha_store["abc-123"] = "ABCD"

# Worker 2 tries to verify
if "abc-123" in captcha_store:  # False! Different dict!
    ...
```

**Problem**: Each worker has separate `captcha_store` dict.

### ✅ File-Based (Works, but Slow)

```python
# services/captcha_storage.py
def store(captcha_id, code):
    # Write to file (shared across all workers)
    with open("captcha_store.json", "w") as f:
        json.dump({captcha_id: code}, f)

def get(captcha_id):
    # Read from file (shared across all workers)
    with open("captcha_store.json", "r") as f:
        return json.load(f).get(captcha_id)
```

**Works**: File is shared across processes.
**Slow**: Every read/write hits disk (~1-10ms).

### ✅ Hybrid: In-Memory Cache + File Sync (Best)

```python
# services/captcha_storage.py
class HybridCaptchaStorage:
    def __init__(self):
        self._cache = {}  # In-memory (fast)
        self._file = "captcha_store.json"  # File (persistent)
    
    def store(self, captcha_id, code):
        # Fast: Write to memory
        self._cache[captcha_id] = code
        
        # Background: Sync to file (non-blocking)
        self._sync_to_file()
    
    def get(self, captcha_id):
        # Fast: Read from memory first
        if captcha_id in self._cache:
            return self._cache[captcha_id]
        
        # Fallback: Read from file (if cache miss)
        return self._load_from_file(captcha_id)
```

**Works**: File sync ensures all workers see updates.
**Fast**: In-memory cache for reads (~0.001ms).
**Best of both worlds**: Speed + multi-worker support.

## Why Not Use Threads Instead?

You might ask: "Why not use threads instead of processes?"

### Threads vs Processes

| Feature | Threads | Processes (Workers) |
|---------|---------|-------------------|
| Memory | Shared | Isolated |
| Crash isolation | One crash kills all | One crash isolated |
| GIL (Python) | Shared GIL (blocks) | Separate GILs (parallel) |
| CPU usage | Single core | Multiple cores |

### Why Uvicorn Uses Processes

1. **Python GIL**: Threads share Global Interpreter Lock (can't truly parallelize CPU-bound work)
2. **Crash isolation**: If one worker crashes, others continue
3. **True parallelism**: Processes can use multiple CPU cores
4. **Better for async**: Each process has its own event loop

## Alternative: Shared Memory (Advanced)

You *could* use shared memory, but it's complex:

```python
import multiprocessing

# Create shared dict
manager = multiprocessing.Manager()
captcha_store = manager.dict()  # Shared across processes
```

**Problems**:
- More complex
- Slower than pure in-memory (IPC overhead)
- Still needs persistence for restarts
- Not worth it for this use case

## Conclusion

**In-memory doesn't work across workers** because:
1. Workers are separate processes
2. Processes have isolated memory
3. Each process has its own `captcha_store` dict

**Solution**: Use file-based storage (or hybrid cache) that all workers can access.

