# Auto-Complete Cache Framework Design Document

## Executive Summary

This document outlines the design for a server-side caching system to reduce duplicate LLM API calls when multiple users (e.g., 50 teachers in a workshop) request auto-complete for the same diagram topic simultaneously.

**Current Problem:**
- 50 teachers using the same diagram topic → 50 × 4 models = 200 LLM API calls
- High cost, slow response times, potential rate limiting issues

**Proposed Solution:**
- Cache LLM responses server-side using **cachetools TTLCache** (professional Python caching library)
- First request triggers LLM call, subsequent identical requests return cached result
- Expected reduction: 200 calls → 4 calls (98% reduction)

**Why NOT Database Table?**
- ❌ Too slow: Database lookup ~1-5ms vs cachetools ~0.001ms (1000x slower)
- ❌ Not designed for caching: Databases optimized for ACID, not speed
- ❌ Overhead: Connection pooling, query parsing, serialization
- ✅ **cachetools**: Industry-standard, used by requests, pip, and major Python projects

**Important: Response Format**
- ✅ **All responses are JSON-serializable dicts** (verified in codebase)
- ✅ **Simple caching**: Store dict directly, use `json.dumps()` for persistence
- ✅ **No complex serialization**: Everything already JSON-compatible
- ✅ **Simpler implementation**: No need for custom serializers

**Recommended Solutions (Ranked for Small Applications):**

1. **🥇 Simple Dict + asyncio.Lock** (BEST for small apps)
   - ✅ Zero dependencies (stdlib only)
   - ✅ Matches your existing patterns (rate_limiter.py style)
   - ✅ Simple and maintainable
   - ✅ Fast: ~0.001ms lookups

2. **🥈 cachetools TTLCache** (Professional option)
   - ✅ Professional library (used by requests, pip)
   - ✅ Built-in TTL + LRU
   - ⚠️ Requires `pip install cachetools`

3. **🥉 functools.lru_cache** (Built-in, but limited)
   - ✅ Zero dependencies (stdlib)
   - ❌ No TTL expiration (size-based only)
   - ❌ Not ideal for async/class methods

**See Section 3.2 for detailed comparison of all options.**

---

## 1. Current Architecture Analysis

### 1.1 Request Flow

```
Frontend (LLMAutoCompleteManager)
  ↓
POST /api/generate_graph
  {
    prompt: "Continue the following mindmap diagram...",
    diagram_type: "mindmap",
    language: "zh",
    llm: "qwen",
    request_type: "autocomplete"
  }
  ↓
Backend (routers/api.py → agents/main_agent.py)
  ↓
LLM Service (services/llm_service.py)
  ↓
External LLM API (Dashscope/Tencent/etc.)
```

### 1.2 Current Caching State

**Frontend Cache (`LLMResultCache`):**
- Location: `static/js/managers/toolbar/llm-result-cache.js`
- Scope: Per-session, client-side only
- TTL: 10 minutes
- Purpose: Cache results within a single user session
- Limitation: Not shared across users

**Backend Cache:**
- ❌ **No server-side caching exists**
- All requests trigger fresh LLM API calls

### 1.3 Request/Response Structure Analysis

**Request (from frontend):**
```javascript
// static/js/managers/toolbar/llm-autocomplete-manager.js (lines 186-192)
const requestBody = {
    prompt: `Continue the following ${currentDiagramType} diagram with ${existingNodes.length} existing nodes. Main topic/center: "${mainTopic}". Generate additional nodes to complete the diagram structure.`,
    diagram_type: currentDiagramType,
    language: language,
    request_type: 'autocomplete'
};
```

**Response (from backend):**
```python
# agents/main_agent.py (lines 1767-1776)
result = {
    'success': True,
    'spec': spec,  # Dict[str, Any] - JSON-serializable diagram spec
    'diagram_type': diagram_type,
    'topics': [],
    'style_preferences': {},
    'language': language,
    'is_learning_sheet': is_learning_sheet,
    'hidden_node_percentage': hidden_percentage
}
# routers/api.py (line 214) - FastAPI auto-serializes dict to JSON
return result
```

**Key Observations:**
1. ✅ **Response is already JSON-serializable**: Python dict → FastAPI auto-serializes to JSON
2. ✅ **Simple caching**: Can store dict directly in memory, use `json.dumps()` for persistence
3. ✅ **No complex serialization needed**: Everything is already JSON-compatible
4. Prompt includes `existingNodes.length` - this varies per user even for same topic
5. Main topic (`mainTopic`) is the core identifier
6. Diagram type and language are consistent for same diagram
7. `request_type: 'autocomplete'` distinguishes from regular generation

**Cache Key Components:**
- ✅ `diagram_type` - Required (different diagrams = different results)
- ✅ `language` - Required (zh vs en = different results)
- ✅ `mainTopic` - Required (core identifier)
- ✅ `llm` model - Required (different models = different results)
- ❌ `existingNodes.length` - Should be normalized (same topic with 1 vs 2 nodes should use same cache)

**Cache Value Structure:**
- Store the entire `result` dict (already JSON-serializable)
- No need for custom serialization/deserialization
- Simple `json.dumps()` / `json.loads()` for persistence (if needed)
- ❌ `user_id`, `session_id` - Should be excluded (cache shared across users)

---

## 2. Cache Design Requirements

### 2.1 Functional Requirements

1. **Cache Scope:**
   - Only cache `request_type: 'autocomplete'` requests
   - Do NOT cache regular `diagram_generation` requests (user-specific prompts)

2. **Cache Key Generation:**
   - Normalize prompt to extract core topic
   - Include: `diagram_type`, `language`, `normalized_topic`, `llm_model`
   - Exclude: `user_id`, `session_id`, `existingNodes.length` (normalized)

3. **Cache Storage:**
   - Server-side, shared across all users
   - Persistent across server restarts (database or file-based)

4. **Cache Invalidation:**
   - TTL-based: Default 24 hours (configurable)
   - Manual invalidation: Admin API endpoint
   - Size-based eviction: LRU when cache exceeds size limit

5. **Cache Hit/Miss Behavior:**
   - Cache Hit: Return cached result immediately (no LLM call)
   - Cache Miss: Call LLM, store result, return to user
   - Concurrent Requests: If cache miss, only first request calls LLM, others wait

### 2.2 Non-Functional Requirements

1. **Performance:**
   - Cache lookup: < 10ms
   - No blocking on cache operations
   - Thread-safe for concurrent access

2. **Reliability:**
   - Cache failures should not break auto-complete (fallback to direct LLM call)
   - Graceful degradation if cache unavailable

3. **Scalability:**
   - Support 1000+ concurrent cache lookups
   - Efficient memory usage (compress large responses)

4. **Observability:**
   - Log cache hits/misses
   - Track cache statistics (hit rate, size, evictions)
   - Admin endpoint to view cache status

---

## 3. Proposed Architecture

### 3.1 Cache Layer Location

**Option A: Service Layer (Recommended)**
```
routers/api.py
  ↓
services/autocomplete_cache.py (NEW)
  ↓ Check cache
  ↓ If miss → agents/main_agent.py → LLM Service
  ↓ Store result
  ↓ Return to user
```

**Option B: LLM Service Layer**
```
routers/api.py
  ↓
agents/main_agent.py
  ↓
services/llm_service.py
  ↓ Check cache (integrated)
  ↓ If miss → External LLM API
```

**Recommendation: Option A**
- Separation of concerns (cache logic separate from LLM logic)
- Easier to enable/disable caching
- Can be applied to other endpoints in future

### 3.2 Cache Storage Options - Comprehensive Comparison for Small Applications

#### Option 1: Simple Dict + Manual TTL (SIMPLEST ⭐⭐⭐)
**Zero dependencies - Matches your existing patterns**

- ✅ **Zero dependencies**: Uses only Python stdlib
- ✅ **Simple**: Just a dict with timestamps
- ✅ **Matches existing code**: Similar to `LazyJavaScriptCache` pattern
- ✅ **Fast**: ~0.001ms lookups (same as cachetools)
- ✅ **Full control**: You control expiration logic
- ❌ **Manual TTL**: Need to check expiration yourself
- ❌ **Manual cleanup**: Need to implement LRU/eviction yourself
- ⚠️ **Thread-safety**: Need to add asyncio.Lock (like rate_limiter.py)

**Implementation:**
```python
from typing import Dict, Any, Optional
import asyncio
import time

class SimpleCache:
    def __init__(self, ttl_seconds: int = 86400, maxsize: int = 10000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            
            # Check expiration
            if time.time() - self._timestamps[key] > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None
            
            return self._cache[key]
    
    async def set(self, key: str, value: Any):
        async with self._lock:
            # Simple LRU: remove oldest if at maxsize
            if len(self._cache) >= self.maxsize and key not in self._cache:
                oldest_key = min(self._timestamps.items(), key=lambda x: x[1])[0]
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            
            self._cache[key] = value
            self._timestamps[key] = time.time()
```

**Best for:** Small apps wanting zero dependencies, matching existing patterns

---

#### Option 2: functools.lru_cache (BUILT-IN ⭐⭐)
**Python stdlib - Zero dependencies**

- ✅ **Zero dependencies**: Built into Python
- ✅ **Simple**: Just a decorator
- ✅ **Fast**: ~0.001ms lookups
- ✅ **LRU built-in**: Automatic eviction
- ❌ **No TTL**: No time-based expiration (only size-based)
- ❌ **Function decorator**: Not ideal for async/class-based cache
- ❌ **No manual control**: Can't easily check/clear specific keys

**Implementation:**
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_cached_result(cache_key: str):
    # But this doesn't work well for async/class methods
    pass
```

**Best for:** Simple function-level caching, not ideal for our use case

---

#### Option 3: cachetools TTLCache (PROFESSIONAL ⭐⭐)
**Professional library - Industry standard**

- ✅ **Fastest**: ~0.001ms lookups
- ✅ **Professional**: Used by requests, pip
- ✅ **Built-in TTL**: Automatic expiration (no manual checking needed!)
- ✅ **Built-in LRU**: Automatic eviction
- ✅ **Thread-safe**: Designed for concurrent access
- ✅ **Automatic cleanup**: Expired entries removed automatically on access
- ❌ **External dependency**: Need to `pip install cachetools`
- ❌ **Slightly more complex**: More features than needed for small app

**Implementation:**
```python
from cachetools import TTLCache
cache = TTLCache(maxsize=10000, ttl=86400)  # 24 hours TTL

# That's it! TTL is handled automatically
cache['key'] = value  # Automatically expires after 86400 seconds
result = cache.get('key')  # Returns None if expired (no manual check needed!)
```

**Automatic TTL Handling Explained:**

**With cachetools (Automatic):**
```python
from cachetools import TTLCache
import time

cache = TTLCache(maxsize=100, ttl=60)  # 60 second TTL

# Add item
cache['topic1'] = {'spec': {...}, 'diagram_type': 'mindmap'}

# Wait 61 seconds...
time.sleep(61)

# Automatic expiration - no manual check needed!
result = cache.get('topic1')  # Returns None automatically (expired)
# Expired entry is automatically removed from cache
```

**Without cachetools (Manual - what you'd write):**
```python
import time
from datetime import datetime, timedelta

cache = {}
timestamps = {}

def get(key):
    if key not in cache:
        return None
    
    # Manual expiration check - YOU must write this
    if datetime.now() - timestamps[key] > timedelta(seconds=60):
        del cache[key]  # Manual cleanup
        del timestamps[key]
        return None
    
    return cache[key]

def set(key, value):
    cache[key] = value
    timestamps[key] = datetime.now()  # Manual timestamp tracking
```

**Key Difference:**

| Feature | cachetools (Automatic) | Manual Dict (Manual) |
|---------|------------------------|----------------------|
| **TTL Check** | Automatic on every access | You must check manually |
| **Expiration** | Automatic removal | You must delete manually |
| **Timestamp Tracking** | Built-in | You must track separately |
| **Code Complexity** | Simple: `cache.get(key)` | Complex: Check + delete logic |
| **Bug Risk** | Low (battle-tested) | Higher (your code) |

**Best for:** When you want professional features without reinventing the wheel

---

#### Option 4: Simple Dict + asyncio.Lock (MATCHES YOUR PATTERN ⭐⭐⭐)
**Exactly like your rate_limiter.py - Zero dependencies**

- ✅ **Zero dependencies**: Only stdlib
- ✅ **Matches existing code**: Same pattern as `rate_limiter.py`
- ✅ **Simple**: Dict + Lock + manual expiration check
- ✅ **Fast**: ~0.001ms lookups
- ✅ **Full control**: You control everything
- ❌ **More code**: Need to implement TTL checking yourself
- ❌ **Manual cleanup**: Need background task for expired entries

**Implementation (matches rate_limiter.py pattern):**
```python
from collections import deque
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, Optional

class AutocompleteCache:
    def __init__(self, ttl_hours: int = 24, maxsize: int = 10000):
        self.ttl_hours = ttl_hours
        self.maxsize = maxsize
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            
            # Check expiration (like rate_limiter checks old timestamps)
            now = datetime.now()
            expires_at = self._timestamps[key] + timedelta(hours=self.ttl_hours)
            if now > expires_at:
                del self._cache[key]
                del self._timestamps[key]
                return None
            
            return self._cache[key]
    
    async def set(self, key: str, value: Any):
        async with self._lock:
            # Simple eviction: remove oldest if at maxsize
            if len(self._cache) >= self.maxsize and key not in self._cache:
                oldest_key = min(self._timestamps.items(), key=lambda x: x[1])[0]
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
```

**Best for:** Small apps wanting consistency with existing code patterns

---

#### Option 5: diskcache (FILE-BASED ⭐)
**Persistent cache - File-based**

- ✅ **Persistent**: Survives restarts
- ✅ **Thread-safe**: Designed for concurrent access
- ✅ **No external server**: File-based like SQLite
- ❌ **Slower**: ~0.1-1ms (100x slower than in-memory)
- ❌ **External dependency**: Need to `pip install diskcache`
- ❌ **File I/O overhead**: Disk operations slower than RAM

**Best for:** When persistence is critical, but slower than in-memory

---

### 3.3 Quick Comparison Table

| Solution | Dependencies | Speed | Code Lines | Matches Your Code | Best For |
|----------|-------------|-------|------------|-------------------|----------|
| **Simple Dict + Lock** | None | ~0.001ms | ~50 | ✅ Yes | Small apps |
| **cachetools TTLCache** | cachetools | ~0.001ms | ~10 | ❌ No | Professional |
| **functools.lru_cache** | None | ~0.001ms | ~5 | ❌ No | Function caching |
| **diskcache** | diskcache | ~0.1ms | ~10 | ❌ No | Persistence needed |
| **Database Table** | SQLAlchemy | ~1-5ms | ~100 | ❌ No | Not recommended |

### 3.4 Recommendation for Small Application

**For MindGraph (Small Application):**

**🥇 BEST CHOICE: cachetools TTLCache (Option 3)** ⭐
- ✅ **Automatic TTL**: No manual expiration checking needed!
- ✅ **Less code**: ~10 lines vs ~50 lines
- ✅ **Professional**: Battle-tested library (used by requests, pip)
- ✅ **Thread-safe**: Built-in concurrency support
- ✅ **Automatic cleanup**: Expired entries removed automatically
- ✅ **Simple API**: Just `cache.get(key)` - handles expiration internally
- ⚠️ Requires `pip install cachetools` (but you said you don't mind!)

**🥈 SECOND CHOICE: Simple Dict + asyncio.Lock (Option 4)**
- ✅ Zero dependencies (stdlib only)
- ✅ Matches your existing patterns (rate_limiter.py style)
- ✅ Full control (you control expiration/eviction)
- ❌ More code (~50 lines vs ~10 lines)
- ❌ Manual TTL checking (you must write expiration logic)
- ❌ Manual cleanup (expired entries stay until checked)

**🥉 THIRD CHOICE: functools.lru_cache (Option 2)**
- ✅ Zero dependencies
- ❌ No TTL expiration (size-based only)
- ❌ Not ideal for async/class methods

**Decision Matrix:**

| If you want... | Choose... |
|---------------|-----------|
| **Automatic TTL handling** | **cachetools TTLCache** ⭐ |
| Less code to write | **cachetools TTLCache** ⭐ |
| Professional features | **cachetools TTLCache** ⭐ |
| Battle-tested library | **cachetools TTLCache** ⭐ |
| Zero dependencies | Simple Dict + Lock |
| Match existing code style | Simple Dict + Lock |
| Full control | Simple Dict + Lock |

**Updated Recommendation: cachetools TTLCache** ⭐

**Why cachetools is better when you don't mind dependencies:**

1. **Automatic TTL = Less Code = Fewer Bugs**
   - No manual expiration checking
   - No manual cleanup logic
   - No timestamp tracking code
   - Library handles edge cases

2. **Cleaner API:**
   ```python
   # cachetools - Simple!
   result = cache.get(key)  # Returns None if expired (automatic)
   
   # Manual - More code
   result = await cache.get(key)  # You must check expiration yourself
   ```

3. **Professional & Battle-Tested:**
   - Used by major projects (requests, pip)
   - Handles edge cases you might miss
   - Well-documented and maintained

4. **Same Performance:**
   - Both are ~0.001ms lookups
   - No performance difference

**Final Recommendation:** Use **cachetools TTLCache** - it's simpler, cleaner, and handles TTL automatically!

---

#### Option 6: cachetools TTLCache (PROFESSIONAL ⭐⭐)
**Professional Python caching library - Industry standard**

- ✅ **Fastest**: In-memory lookups (~0.001ms)
- ✅ **Professional**: Used by major Python projects (requests, pip)
- ✅ **Built-in features**: TTL expiration, LRU eviction, max size limits
- ✅ **Thread-safe**: Designed for concurrent access
- ✅ **No external dependencies**: Pure Python, lightweight
- ✅ **Memory efficient**: Automatic eviction of old entries
- ❌ Lost on server restart (but can add persistence layer)
- ❌ Not shared across multiple workers (but can add Redis layer later)

**Implementation:**
```python
from cachetools import TTLCache
cache = TTLCache(maxsize=10000, ttl=86400)  # 10k entries, 24h TTL
```

**Performance:** ~0.001ms lookup (1000x faster than database)

---

#### Option 2: Redis (Production-Grade)
**Industry standard distributed cache**

- ✅ **Fastest**: Sub-millisecond lookups
- ✅ **Distributed**: Shared across multiple workers/servers
- ✅ **Persistent**: Optional persistence to disk
- ✅ **Advanced features**: Pub/sub, clustering, replication
- ✅ **Production-ready**: Used by Twitter, GitHub, Stack Overflow
- ❌ **External dependency**: Requires Redis server
- ❌ **Infrastructure overhead**: Need to deploy/manage Redis
- ❌ **Overkill**: For single-server deployment

**When to use:** Multi-server deployment, need distributed cache

---

#### Option 3: Hybrid: cachetools + File Persistence
**Best of both worlds - Fast + Persistent**

- ✅ **Fast lookups**: In-memory cache (cachetools)
- ✅ **Persistence**: Periodic save to disk (JSON/Pickle)
- ✅ **Crash recovery**: Load cache from disk on startup
- ✅ **No external dependencies**: Pure Python
- ✅ **Matches existing patterns**: Similar to rate_limiter.py approach
- ⚠️ **More complex**: Need to handle persistence logic

**Architecture:**
```
In-Memory Cache (cachetools TTLCache)
  ↓ (periodic save)
File Storage (JSON/Pickle)
  ↓ (on startup)
Load into Memory
```

**Performance:** ~0.001ms lookup + background persistence

---

#### Option 4: Database Table (NOT RECOMMENDED ❌)
**Why NOT recommended:**

- ❌ **Too slow**: ~1-5ms per lookup (1000x slower than in-memory)
- ❌ **Database overhead**: Connection pooling, query parsing, serialization
- ❌ **Not designed for caching**: Databases optimized for ACID, not speed
- ❌ **Scaling issues**: Database becomes bottleneck under high load
- ✅ Persistent (but can add persistence to Option 1/3)

**When database caching makes sense:**
- Need complex queries across cache entries
- Need ACID guarantees
- Cache size > available RAM

**For our use case:** Database is overkill and too slow.

---

#### Option 5: diskcache (File-Based Cache Library)
**Professional file-based caching**

- ✅ **Persistent**: File-based, survives restarts
- ✅ **Thread-safe**: Designed for concurrent access
- ✅ **Professional**: Used by major projects
- ✅ **No external server**: File-based like SQLite
- ❌ **Slower than in-memory**: ~0.1-1ms (still fast, but slower than Option 1)
- ✅ **Good middle ground**: Between in-memory and database

**Implementation:**
```python
import diskcache as dc
cache = dc.Cache('./cache_dir', size_limit=1000000000)  # 1GB limit
```

**Performance:** ~0.1-1ms lookup (10-100x faster than database)

---

### 3.3 Recommendation: Hybrid Approach (Option 3)

**Primary Cache: cachetools TTLCache (In-Memory)**
- Fast lookups (~0.001ms)
- TTL expiration built-in
- LRU eviction for memory management
- Thread-safe

**Persistence Layer: File-Based (JSON/Pickle)**
- Periodic save to disk (every 5 minutes or on shutdown)
- Load on startup
- Crash recovery

**Why This Approach:**
1. **Performance**: In-memory cache gives fastest lookups
2. **Reliability**: File persistence ensures cache survives restarts
3. **Matches patterns**: Similar to existing rate_limiter.py (file-based)
4. **Scalability**: Can add Redis layer later if needed (multi-server)
5. **Professional**: Uses industry-standard cachetools library

**Migration Path:**
- Phase 1: cachetools only (fastest to implement)
- Phase 2: Add file persistence (if needed)
- Phase 3: Add Redis (if scaling to multiple servers)

### 3.3 Cache Key Normalization Strategy

**Challenge:** Prompts vary even for same topic:
```
"Continue the following mindmap diagram with 1 existing nodes. Main topic/center: \"光合作用\". Generate additional nodes..."
"Continue the following mindmap diagram with 2 existing nodes. Main topic/center: \"光合作用\". Generate additional nodes..."
```

**Solution:** Extract and normalize core components:

```python
def normalize_cache_key(prompt: str, diagram_type: str, language: str, llm_model: str) -> str:
    """
    Extract core topic from prompt and create normalized cache key.
    
    Example:
        Input: "Continue the following mindmap diagram with 1 existing nodes. Main topic/center: \"光合作用\"..."
        Output: "mindmap:zh:qwen:光合作用"
    """
    # Extract main topic using regex or LLM
    main_topic = extract_main_topic_from_prompt(prompt)
    
    # Normalize: lowercase, trim whitespace
    main_topic = main_topic.lower().strip()
    
    # Create key: diagram_type:language:llm_model:normalized_topic
    cache_key = f"{diagram_type}:{language}:{llm_model}:{main_topic}"
    
    return cache_key
```

**Topic Extraction Methods:**

1. **Regex Extraction (Fast, Recommended):**
   ```python
   import re
   
   def extract_main_topic_from_prompt(prompt: str) -> str:
       # Pattern: Main topic/center: "TOPIC"
       pattern = r'Main topic/center:\s*"([^"]+)"'
       match = re.search(pattern, prompt)
       if match:
           return match.group(1)
       
       # Fallback: Extract Chinese/English topic
       # ... additional patterns
   ```

2. **LLM Extraction (More Accurate, Slower):**
   - Use LLM to extract topic (adds latency, not recommended for cache key)

**Recommendation: Regex Extraction**
- Fast (no LLM call needed)
- Sufficient for cache key generation
- Can add LLM extraction as fallback if regex fails

---

## 4. Cache Implementation Design

### 4.1 cachetools TTLCache Structure

**Primary Cache (In-Memory):**
```python
from cachetools import TTLCache
from typing import Dict, Any, Optional
import asyncio
import json
from pathlib import Path

class AutocompleteCacheService:
    """
    Professional caching service using cachetools TTLCache.
    
    Features:
    - In-memory cache with TTL expiration
    - LRU eviction when max size reached
    - Thread-safe concurrent access
    - Optional file persistence
    """
    
    def __init__(
        self,
        maxsize: int = 10000,  # Max entries
        ttl: int = 86400,  # 24 hours in seconds
        persist_file: Optional[Path] = None  # Optional persistence
    ):
        # Primary in-memory cache
        self._cache: TTLCache[str, Dict[str, Any]] = TTLCache(
            maxsize=maxsize,
            ttl=ttl
        )
        
        # Statistics tracking
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0
        }
        
        # Lock for concurrent access
        self._lock = asyncio.Lock()
        
        # Persistence file (optional)
        self._persist_file = persist_file
        
        # Load from disk on startup (if persistence enabled)
        if self._persist_file and self._persist_file.exists():
            self._load_from_disk()
```

**Cache Entry Structure:**
```python
# Simple structure - just store the response dict directly
{
    'cache_key': 'mindmap:zh:qwen:光合作用',
    'response': {
        'success': True,
        'spec': {...},  # Dict[str, Any] - Full diagram spec (JSON-serializable)
        'diagram_type': 'mindmap',
        'topics': [],
        'style_preferences': {},
        'language': 'zh',
        'is_learning_sheet': False,
        'hidden_node_percentage': 0.0,
        'llm_model': 'qwen',  # Added by routers/api.py
        'request_id': 'gen_1234567890'  # Added by routers/api.py
    },
    'metadata': {
        'created_at': 1234567890.0,
        'access_count': 5,
        'last_accessed': 1234567890.0
    }
}

# Or even simpler - just store the response dict directly:
cache[key] = {
    'success': True,
    'spec': {...},
    'diagram_type': 'mindmap',
    # ... rest of response
}
# No need for nested structure - response is already JSON-serializable!
```

### 4.2 File Persistence Structure (Optional)

**Persistence File Format (JSON):**
```json
{
    "version": "1.0",
    "entries": [
        {
            "cache_key": "mindmap:zh:qwen:光合作用",
            "response": {
                "success": true,
                "spec": {...},
                "diagram_type": "mindmap",
                "language": "zh"
            },
            "created_at": 1234567890.0,
            "expires_at": 1234654290.0
        }
    ],
    "stats": {
        "total_entries": 150,
        "last_saved": 1234567890.0
    }
}
```

**Persistence Strategy:**
- Save to disk: Every 5 minutes (background task) + on graceful shutdown
- Load from disk: On service initialization
- Format: JSON (human-readable, debuggable)
- **Simple serialization**: Just use `json.dumps()` / `json.loads()` - response is already JSON-serializable!
- Compression: Optional gzip for large files (not needed for small app)

**Implementation Note:**
Since responses are already JSON-serializable dicts, persistence is trivial:
```python
import json

# Save
with open('cache.json', 'w') as f:
    json.dump(cache_data, f, ensure_ascii=False)

# Load
with open('cache.json', 'r') as f:
    cache_data = json.load(f)
```

### 4.3 Cache Service Interface

```python
class AutocompleteCacheService:
    """
    Professional caching service using cachetools TTLCache.
    
    Usage:
        cache_service = AutocompleteCacheService()
        
        # Check cache (with concurrent request handling)
        cached_result = await cache_service.get_or_compute(
            prompt="...",
            diagram_type="mindmap",
            language="zh",
            llm_model="qwen",
            compute_func=lambda: llm_service.chat(...)
        )
        
        # Manual get/set (if needed)
        cached = await cache_service.get(prompt, diagram_type, language, llm_model)
        if cached:
            return cached
        
        result = await llm_service.chat(...)
        await cache_service.set(prompt, diagram_type, language, llm_model, result)
    """
    
    async def get(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        Returns None if cache miss or expired.
        """
        cache_key = self._normalize_key(prompt, diagram_type, language, llm_model)
        
        async with self._lock:
            entry = self._cache.get(cache_key)
            if entry:
                self._stats['hits'] += 1
                entry['metadata']['access_count'] += 1
                entry['metadata']['last_accessed'] = time.time()
                return entry['response']
            
            self._stats['misses'] += 1
            return None
    
    async def set(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        response: Dict[str, Any]
    ) -> None:
        """Store result in cache."""
        cache_key = self._normalize_key(prompt, diagram_type, language, llm_model)
        
        entry = {
            'cache_key': cache_key,
            'response': response,
            'metadata': {
                'created_at': time.time(),
                'access_count': 0,
                'last_accessed': time.time()
            }
        }
        
        async with self._lock:
            # Check if eviction occurred
            old_size = len(self._cache)
            self._cache[cache_key] = entry
            if len(self._cache) < old_size:
                self._stats['evictions'] += 1
            
            self._stats['sets'] += 1
    
    async def get_or_compute(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        compute_func: Callable[[], Awaitable[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Get from cache, or compute and cache if miss.
        Handles concurrent requests for same key (only first computes).
        """
        cache_key = self._normalize_key(prompt, diagram_type, language, llm_model)
        
        # Check cache first
        cached = await self.get(prompt, diagram_type, language, llm_model)
        if cached:
            return cached
        
        # Cache miss - acquire lock for this specific key
        async with self._get_key_lock(cache_key):
            # Double-check cache (another request might have populated it)
            cached = await self.get(prompt, diagram_type, language, llm_model)
            if cached:
                return cached
            
            # Still miss - compute
            result = await compute_func()
            
            # Store in cache
            await self.set(prompt, diagram_type, language, llm_model, result)
            
            return result
    
    async def invalidate(
        self,
        cache_key: Optional[str] = None,
        diagram_type: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.
        Returns count of deleted entries.
        """
        count = 0
        async with self._lock:
            if cache_key:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    count = 1
            elif diagram_type:
                # Remove all entries for this diagram type
                keys_to_remove = [
                    key for key in self._cache.keys()
                    if key.startswith(f"{diagram_type}:")
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                count = len(keys_to_remove)
            else:
                # Clear all
                count = len(self._cache)
                self._cache.clear()
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (
            self._stats['hits'] / total_requests * 100
            if total_requests > 0 else 0
        )
        
        return {
            'enabled': True,
            'size': len(self._cache),
            'maxsize': self._cache.maxsize,
            'ttl_seconds': self._cache.ttl,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'sets': self._stats['sets'],
            'evictions': self._stats['evictions']
        }
    
    def _normalize_key(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str
    ) -> str:
        """Normalize cache key."""
        main_topic = extract_main_topic_from_prompt(prompt)
        if not main_topic:
            raise ValueError("Cannot extract topic from prompt")
        
        normalized_topic = main_topic.lower().strip()
        normalized_diagram_type = diagram_type.lower().strip()
        if normalized_diagram_type == 'mind_map':
            normalized_diagram_type = 'mindmap'
        
        return f"{normalized_diagram_type}:{language}:{llm_model}:{normalized_topic}"
```

---

## 5. Cache Workflow & Matching Logic

### 5.1 Complete Request Flow

**When 50 teachers use the same diagram with the same topic:**

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Frontend Request (50 teachers simultaneously)          │
└─────────────────────────────────────────────────────────────────┘
│
│ Teacher 1: POST /api/generate_graph
│   {
│     "prompt": "Continue the following mindmap diagram with 1 existing nodes. Main topic/center: \"光合作用\"...",
│     "diagram_type": "mindmap",
│     "language": "zh",
│     "llm": "qwen",
│     "request_type": "autocomplete"
│   }
│
│ Teacher 2: POST /api/generate_graph
│   {
│     "prompt": "Continue the following mindmap diagram with 2 existing nodes. Main topic/center: \"光合作用\"...",
│     "diagram_type": "mindmap",
│     "language": "zh",
│     "llm": "qwen",
│     "request_type": "autocomplete"
│   }
│
│ ... (Teachers 3-50 with same topic "光合作用" but different existingNodes.length)
│
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Backend API Endpoint (routers/api.py)                  │
└─────────────────────────────────────────────────────────────────┘
│
│ if request_type == 'autocomplete':
│   → Check cache FIRST (before calling LLM)
│
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Cache Key Generation (services/autocomplete_cache.py)   │
└─────────────────────────────────────────────────────────────────┘
│
│ Extract from prompt: "Main topic/center: \"光合作用\""
│   → main_topic = "光合作用"
│
│ Normalize:
│   → diagram_type: "mindmap" (normalized from "mind_map" if needed)
│   → language: "zh"
│   → llm_model: "qwen"
│   → normalized_topic: "光合作用" (lowercase, trimmed)
│
│ Create cache key:
│   → "mindmap:zh:qwen:光合作用"
│
│ ⚠️ IGNORED (not part of cache key):
│   ❌ existingNodes.length (1 vs 2 vs 3...) → Same cache key!
│   ❌ user_id → Same cache key!
│   ❌ session_id → Same cache key!
│   ❌ request_id → Same cache key!
│
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Cache Lookup                                            │
└─────────────────────────────────────────────────────────────────┘
│
│ Check cache: cache.get("mindmap:zh:qwen:光合作用")
│
│ Teacher 1 (first request):
│   → Cache MISS (key doesn't exist)
│   → Acquire lock for this key
│   → Call LLM (agent_graph_workflow_with_styles)
│   → Store result in cache
│   → Return result
│
│ Teachers 2-50 (concurrent requests):
│   → Cache MISS (key doesn't exist yet)
│   → Wait for lock (Teacher 1 is computing)
│   → Lock acquired
│   → Double-check cache → Cache HIT! (Teacher 1 already stored it)
│   → Return cached result (NO LLM call!)
│
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Response (Same for all 50 teachers)                     │
└─────────────────────────────────────────────────────────────────┘
│
│ {
│   "success": true,
│   "spec": {
│     "topic": "光合作用",
│     "children": [...]
│   },
│   "diagram_type": "mindmap",
│   "language": "zh",
│   "llm_model": "qwen"
│ }
│
│ ✅ All 50 teachers get the SAME response (from cache)
│ ✅ Only 1 LLM API call (from Teacher 1)
│ ✅ 49 cache hits (Teachers 2-50)
│
└─────────────────────────────────────────────────────────────────┘
```

---

### 5.2 What Gets Matched (Cache Key Components)

**Cache Key Format:** `diagram_type:language:llm_model:normalized_topic`

**Components that MUST match for cache hit:**

| Component | Example | Why It Matters |
|-----------|---------|----------------|
| **diagram_type** | `mindmap` | Different diagram types = different structures |
| **language** | `zh` | Chinese vs English = different content |
| **llm_model** | `qwen` | Different models = different outputs |
| **normalized_topic** | `光合作用` | Different topics = different content |

**Components that are IGNORED (same cache key):**

| Component | Example | Why Ignored |
|-----------|---------|-------------|
| **existingNodes.length** | `1` vs `2` vs `3` | Same topic should get same completion |
| **user_id** | `123` vs `456` | Cache shared across users |
| **session_id** | `abc123` vs `def456` | Cache shared across sessions |
| **request_id** | `gen_1234` vs `gen_5678` | Just a unique ID |

**Example: These 3 requests get the SAME cache key:**

```python
# Request 1
prompt = "Continue the following mindmap diagram with 1 existing nodes. Main topic/center: \"光合作用\"..."
diagram_type = "mindmap"
language = "zh"
llm_model = "qwen"
# Cache key: "mindmap:zh:qwen:光合作用"

# Request 2 (different user, different node count)
prompt = "Continue the following mindmap diagram with 2 existing nodes. Main topic/center: \"光合作用\"..."
diagram_type = "mindmap"
language = "zh"
llm_model = "qwen"
# Cache key: "mindmap:zh:qwen:光合作用" ✅ SAME!

# Request 3 (different user, different node count)
prompt = "Continue the following mindmap diagram with 5 existing nodes. Main topic/center: \"光合作用\"..."
diagram_type = "mindmap"
language = "zh"
llm_model = "qwen"
# Cache key: "mindmap:zh:qwen:光合作用" ✅ SAME!
```

**Result:** All 3 requests share the same cache entry → Only 1 LLM call!

---

### 5.3 What Gets Cached (Cache Value)

**Cache stores the FULL response dict:**

```python
{
    'success': True,
    'spec': {
        'topic': '光合作用',
        'children': [
            {'text': '叶绿体', ...},
            {'text': '光能', ...},
            # ... more nodes
        ]
    },
    'diagram_type': 'mindmap',
    'language': 'zh',
    'topics': [],
    'style_preferences': {},
    'is_learning_sheet': False,
    'hidden_node_percentage': 0.0,
    'llm_model': 'qwen',  # Added by API
    'request_id': 'gen_1234567890'  # Added by API (but ignored in cache key)
}
```

**Important:**
- ✅ **Full JSON structure** is cached (entire response dict)
- ✅ **Same response** returned to all matching requests
- ✅ **No modification** needed - return cached dict directly
- ❌ **NOT matching JSON structure** - matching on cache key (topic + diagram_type + language + model)

---

### 5.4 Cache Matching Logic Flowchart

```
Request arrives
    ↓
Is request_type == 'autocomplete'?
    ├─ NO → Skip cache, call LLM directly
    └─ YES → Continue
        ↓
Extract main topic from prompt
    ├─ Success → Continue
    └─ Fail → Skip cache, call LLM directly
        ↓
Generate cache key: "diagram_type:language:llm_model:topic"
    ↓
Check cache: cache.get(cache_key)
    ├─ HIT → Return cached response (NO LLM call)
    └─ MISS → Continue
        ↓
Acquire lock for this cache_key
    ↓
Double-check cache (another request might have stored it)
    ├─ HIT → Return cached response
    └─ MISS → Continue
        ↓
Call LLM (agent_graph_workflow_with_styles)
    ↓
Store result in cache: cache[cache_key] = response
    ↓
Return response
```

---

### 5.5 Example: 50 Teachers Scenario

**Scenario:** 50 teachers in workshop, all using:
- Same diagram type: `mindmap`
- Same topic: `光合作用` (Photosynthesis)
- Same language: `zh`
- Same LLM model: `qwen` (first request)

**What happens:**

| Request | User | existingNodes.length | Cache Key | Cache Status | Action |
|---------|------|---------------------|-----------|--------------|--------|
| 1 | Teacher 1 | 1 | `mindmap:zh:qwen:光合作用` | MISS | Call LLM, store |
| 2 | Teacher 2 | 2 | `mindmap:zh:qwen:光合作用` | MISS → HIT | Wait, get cached |
| 3 | Teacher 3 | 1 | `mindmap:zh:qwen:光合作用` | MISS → HIT | Wait, get cached |
| ... | ... | ... | `mindmap:zh:qwen:光合作用` | MISS → HIT | Wait, get cached |
| 50 | Teacher 50 | 3 | `mindmap:zh:qwen:光合作用` | MISS → HIT | Wait, get cached |

**Result:**
- ✅ **1 LLM API call** (Teacher 1)
- ✅ **49 cache hits** (Teachers 2-50)
- ✅ **98% reduction** in LLM calls
- ✅ **All teachers get same response** (from cache)

**Note:** If teachers use different LLM models (qwen, deepseek, kimi, hunyuan), each model gets its own cache entry:
- `mindmap:zh:qwen:光合作用` → 1 LLM call
- `mindmap:zh:deepseek:光合作用` → 1 LLM call
- `mindmap:zh:kimi:光合作用` → 1 LLM call
- `mindmap:zh:hunyuan:光合作用` → 1 LLM call

**Total:** 4 LLM calls (one per model) instead of 200 (50 teachers × 4 models)

---

### 5.6 Why We Don't Match JSON Structure

**Question:** Should we match on JSON structure of the request?

**Answer:** No, we match on semantic meaning (topic), not structure.

**Reason:**
1. **Prompts vary:** `existingNodes.length` differs per user (1, 2, 3...)
2. **Same intent:** All want completion for same topic
3. **Same result:** LLM generates same content regardless of node count
4. **Efficiency:** One cache entry serves all variations

**Example:**
```python
# These prompts are DIFFERENT in structure:
prompt1 = "Continue... with 1 existing nodes. Main topic/center: \"光合作用\"..."
prompt2 = "Continue... with 2 existing nodes. Main topic/center: \"光合作用\"..."

# But they have the SAME semantic meaning:
# → Both want to complete diagram about "光合作用"
# → Both should get the same cached result
```

**If we matched JSON structure:**
- ❌ Each `existingNodes.length` variation = different cache entry
- ❌ 50 teachers = 50 cache entries (no benefit!)
- ❌ No reduction in LLM calls

**By matching on topic:**
- ✅ All variations = same cache entry
- ✅ 50 teachers = 1 cache entry
- ✅ 98% reduction in LLM calls

---

## 6. Race Condition Handling & Thread Safety

### 6.1 The Race Condition Problem

**Scenario:** 50 teachers request auto-complete simultaneously for the same topic.

**Without proper locking (RACE CONDITION):**

```
Time    Teacher 1          Teacher 2          Teacher 3          ... Teacher 50
─────────────────────────────────────────────────────────────────────────────
T0      Check cache        Check cache        Check cache        ... Check cache
        → MISS             → MISS             → MISS             ... → MISS
T1      Call LLM           Call LLM           Call LLM           ... Call LLM
        (starts)           (starts)           (starts)           ... (starts)
T2      ...                ...                ...                ...
T3      Store result       Store result       Store result       ... Store result
        in cache           in cache           in cache           ... in cache

Result: ❌ 50 LLM API calls (no benefit!)
```

**Problem:**
- All 50 requests check cache at the same time
- All get cache MISS (key doesn't exist yet)
- All 50 proceed to call LLM simultaneously
- All 50 store result (last write wins, but we wasted 49 LLM calls)

---

### 6.2 Solution: Double-Check Locking Pattern

**With proper locking (NO RACE CONDITION):**

```
Time    Teacher 1          Teacher 2          Teacher 3          ... Teacher 50
─────────────────────────────────────────────────────────────────────────────
T0      Check cache        Check cache        Check cache        ... Check cache
        → MISS             → MISS             → MISS             ... → MISS
T1      Acquire lock       Try acquire lock   Try acquire lock   ... Try acquire lock
        ✓ Got lock         ✗ Waiting...       ✗ Waiting...       ... ✗ Waiting...
T2      Call LLM           (waiting)           (waiting)           ... (waiting)
        (starts)
T3      ...                (waiting)           (waiting)           ... (waiting)
T4      Store result       (waiting)           (waiting)           ... (waiting)
        in cache
T5      Release lock       ✓ Got lock          (waiting)           ... (waiting)
T6      Return result      Double-check cache  (waiting)           ... (waiting)
                           → HIT! ✓
                           Return cached
                           Release lock
T7                          ...                ✓ Got lock          ... (waiting)
                                              Double-check cache
                                              → HIT! ✓
                                              Return cached
                                              Release lock
...                         ...                ...                ... (all get cached)

Result: ✅ 1 LLM API call, 49 cache hits!
```

---

### 6.3 Implementation: Per-Key Locking

**Key Concept:** One lock per cache key, not one global lock.

**Why per-key locking?**
- Different topics can be computed in parallel
- Only same topic requests need to wait
- Better performance and throughput

**Code Implementation:**

```python
class AutocompleteCacheService:
    def __init__(self):
        # Locks for concurrent request handling (per cache key)
        self._key_locks: Dict[str, asyncio.Lock] = {}
        self._lock_lock = asyncio.Lock()  # Lock for managing key locks
    
    async def get_or_compute(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        compute_func: Callable[[], Awaitable[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Get from cache, or compute and cache if miss.
        
        Uses double-check locking pattern to prevent race conditions.
        """
        # STEP 1: First cache check (fast path - no lock)
        cached = await self.get(prompt, diagram_type, language, llm_model)
        if cached:
            return cached  # Cache hit - return immediately
        
        # STEP 2: Cache miss - get lock for this specific key
        cache_key = self._normalize_cache_key(prompt, diagram_type, language, llm_model)
        if not cache_key:
            # Cannot create cache key - compute directly
            return await compute_func()
        
        # STEP 3: Get or create lock for this cache key (thread-safe)
        async with self._lock_lock:  # Lock for managing locks dictionary
            if cache_key not in self._key_locks:
                self._key_locks[cache_key] = asyncio.Lock()
            key_lock = self._key_locks[cache_key]
        
        # STEP 4: Acquire lock and double-check cache
        async with key_lock:  # Lock for this specific cache key
            # STEP 5: Double-check cache (another request might have populated it)
            cached = await self.get(prompt, diagram_type, language, llm_model)
            if cached:
                return cached  # Cache hit - return cached result
            
            # STEP 6: Still miss - compute (only one request reaches here)
            logger.info(f"[AutocompleteCache] Computing for key: {cache_key}")
            result = await compute_func()
            
            # STEP 7: Store in cache
            await self.set(prompt, diagram_type, language, llm_model, result)
            
            return result
```

---

### 6.4 Step-by-Step Race Condition Prevention

**Detailed flow for 50 concurrent requests:**

```
Request 1 (Teacher 1):
  1. Check cache → MISS
  2. Generate cache_key: "mindmap:zh:qwen:光合作用"
  3. Get lock for cache_key → Acquired ✓
  4. Double-check cache → Still MISS
  5. Call LLM (takes 3-10 seconds)
  6. Store result in cache
  7. Release lock
  8. Return result

Request 2 (Teacher 2) - Arrives at same time as Request 1:
  1. Check cache → MISS (Request 1 hasn't stored yet)
  2. Generate cache_key: "mindmap:zh:qwen:光合作用" (SAME!)
  3. Get lock for cache_key → Waiting... (Request 1 has it)
  4. Wait for lock... (Request 1 is computing)
  5. Lock acquired (Request 1 released it)
  6. Double-check cache → HIT! (Request 1 stored it)
  7. Return cached result (NO LLM call!)
  8. Release lock

Request 3-50 (Teachers 3-50) - All arrive simultaneously:
  1. Check cache → MISS (Request 1 hasn't stored yet)
  2. Generate cache_key: "mindmap:zh:qwen:光合作用" (SAME!)
  3. Get lock → Waiting... (Request 1 or 2 has it)
  4. Wait in queue...
  5. Lock acquired (previous request released it)
  6. Double-check cache → HIT! (already stored)
  7. Return cached result (NO LLM call!)
  8. Release lock
```

**Result:**
- ✅ Only Request 1 calls LLM
- ✅ Requests 2-50 get cached result
- ✅ No race condition
- ✅ No duplicate LLM calls

---

### 6.5 Thread Safety Guarantees

**cachetools TTLCache Thread Safety:**
- ✅ **Thread-safe for reads**: Multiple threads can read simultaneously
- ✅ **Thread-safe for writes**: Internal locking prevents corruption
- ✅ **Atomic operations**: `get()` and `__setitem__()` are atomic

**Our Implementation Thread Safety:**
- ✅ **Per-key locks**: Different topics don't block each other
- ✅ **Double-check pattern**: Prevents duplicate LLM calls
- ✅ **asyncio.Lock**: Proper async/await support
- ✅ **Lock management**: Thread-safe lock dictionary access

**Guarantees:**
1. **No duplicate LLM calls**: Only first request for a key calls LLM
2. **No cache corruption**: TTLCache handles concurrent access safely
3. **No deadlocks**: Per-key locks prevent circular waiting
4. **Correct results**: All requests get same cached result

---

### 6.6 Edge Cases & Potential Issues

**Edge Case 1: Lock Dictionary Growth**

**Problem:** `_key_locks` dictionary grows unbounded (one lock per unique cache key)

**Solution:** Clean up unused locks periodically

```python
async def _cleanup_unused_locks(self):
    """Remove locks for keys that no longer exist in cache."""
    async with self._lock_lock:
        keys_to_remove = [
            key for key in self._key_locks.keys()
            if key not in self._cache
        ]
        for key in keys_to_remove:
            del self._key_locks[key]
```

**Edge Case 2: LLM Call Failure**

**Problem:** What if LLM call fails while holding lock?

**Solution:** Always release lock, don't cache failures

```python
async with key_lock:
    try:
        result = await compute_func()
        await self.set(...)  # Only cache successful results
        return result
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise  # Re-raise exception, lock released automatically
```

**Edge Case 3: Cache Key Collision**

**Problem:** Different topics generate same cache key (very rare)

**Solution:** Include hash of full prompt as fallback

```python
def _normalize_cache_key(self, ...):
    cache_key = f"{diagram_type}:{language}:{llm_model}:{normalized_topic}"
    
    # If topic extraction fails, use hash of prompt as fallback
    if not normalized_topic:
        import hashlib
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        cache_key = f"{diagram_type}:{language}:{llm_model}:hash_{prompt_hash}"
    
    return cache_key
```

**Edge Case 4: Concurrent Requests for Different Models**

**Problem:** Same topic, different LLM models (qwen, deepseek, etc.)

**Solution:** Different cache keys = different locks = parallel execution

```python
# Request 1: qwen
cache_key_1 = "mindmap:zh:qwen:光合作用"
lock_1 = get_lock(cache_key_1)  # Different lock

# Request 2: deepseek  
cache_key_2 = "mindmap:zh:deepseek:光合作用"
lock_2 = get_lock(cache_key_2)  # Different lock

# Both can execute in parallel! ✅
```

---

### 6.7 Performance Under Concurrent Load

**Test Scenario:** 100 concurrent requests for same topic

**Without locking:**
- 100 LLM API calls
- 100 × 3 seconds = 300 seconds total
- High cost, slow response

**With locking:**
- 1 LLM API call
- 99 cache hits
- Total time: ~3 seconds (first request) + ~0.001s × 99 (cache hits)
- Low cost, fast response

**Lock Overhead:**
- Lock acquisition: ~0.0001ms (negligible)
- Cache lookup: ~0.001ms (very fast)
- Total overhead per request: < 0.01ms

**Conclusion:** Lock overhead is negligible compared to LLM call time (3-10 seconds)

---

### 6.8 Verification: Testing Race Conditions

**Test Script:**

```python
import asyncio
from services.autocomplete_cache import get_autocomplete_cache_service

async def simulate_concurrent_request(request_id: int):
    """Simulate a concurrent request."""
    cache = get_autocomplete_cache_service()
    
    prompt = 'Continue the following mindmap diagram with 1 existing nodes. Main topic/center: "光合作用". Generate additional nodes.'
    diagram_type = 'mindmap'
    language = 'zh'
    llm_model = 'qwen'
    
    call_count = {'count': 0}  # Track LLM calls
    
    async def compute():
        call_count['count'] += 1
        print(f"Request {request_id}: LLM called (call #{call_count['count']})")
        await asyncio.sleep(0.1)  # Simulate LLM call
        return {'success': True, 'spec': {}, 'request_id': request_id}
    
    result = await cache.get_or_compute(
        prompt, diagram_type, language, llm_model, compute
    )
    print(f"Request {request_id}: Got result")

async def test_race_condition():
    """Test 50 concurrent requests."""
    print("Starting 50 concurrent requests...")
    
    tasks = [
        simulate_concurrent_request(i)
        for i in range(50)
    ]
    
    await asyncio.gather(*tasks)
    
    print("\n✅ Test complete!")
    print("Expected: Only 1 LLM call")
    print("If you see 'LLM called' more than once, there's a race condition!")

if __name__ == '__main__':
    asyncio.run(test_race_condition())
```

**Expected Output:**
```
Request 0: LLM called (call #1)
Request 1: Got result
Request 2: Got result
...
Request 49: Got result

✅ Test complete!
Expected: Only 1 LLM call
```

**If race condition exists, you'll see:**
```
Request 0: LLM called (call #1)
Request 1: LLM called (call #2)  ← BAD! Race condition!
Request 2: LLM called (call #3)  ← BAD! Race condition!
...
```

---

## 7. Step-by-Step Implementation Guide: cachetools Solution

This section provides a complete, step-by-step guide to implement the auto-complete cache using cachetools TTLCache.

---

### Step 1: Install cachetools

**Action:** Add cachetools to requirements.txt

```bash
# Add to requirements.txt
cachetools>=5.3.0
```

**Install:**
```bash
pip install cachetools>=5.3.0
```

**Verify installation:**
```python
python -c "from cachetools import TTLCache; print('OK')"
```

---

### Step 2: Create Cache Service File

**Action:** Create `services/autocomplete_cache.py`

**File:** `services/autocomplete_cache.py`

```python
"""
Auto-Complete Cache Service
============================

Server-side caching for auto-complete LLM responses using cachetools TTLCache.
Reduces duplicate LLM API calls when multiple users request same diagram topic.

Author: lycosa9527
Made by: MindSpring Team
"""

import asyncio
import logging
import re
from typing import Dict, Any, Optional, Callable, Awaitable
from cachetools import TTLCache

logger = logging.getLogger(__name__)


class AutocompleteCacheService:
    """
    Cache service for auto-complete requests using cachetools TTLCache.
    
    Features:
    - Automatic TTL expiration (24 hours default)
    - LRU eviction when max size reached
    - Thread-safe concurrent access
    - Concurrent request deduplication (only first request calls LLM)
    """
    
    def __init__(
        self,
        maxsize: int = 10000,
        ttl_seconds: int = 86400,  # 24 hours
        enabled: bool = True
    ):
        """
        Initialize cache service.
        
        Args:
            maxsize: Maximum number of cache entries (default: 10000)
            ttl_seconds: Time-to-live in seconds (default: 86400 = 24 hours)
            enabled: Whether caching is enabled (default: True)
        """
        self.enabled = enabled
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        
        # Primary cache using cachetools TTLCache
        self._cache: TTLCache[str, Dict[str, Any]] = TTLCache(
            maxsize=maxsize,
            ttl=ttl_seconds
        )
        
        # Statistics tracking
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0
        }
        
        # Locks for concurrent request handling (per cache key)
        self._key_locks: Dict[str, asyncio.Lock] = {}
        self._lock_lock = asyncio.Lock()  # Lock for managing key locks
        
        logger.info(
            f"[AutocompleteCache] Initialized: "
            f"enabled={enabled}, maxsize={maxsize}, ttl={ttl_seconds}s"
        )
    
    def _normalize_cache_key(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str
    ) -> Optional[str]:
        """
        Create normalized cache key from request parameters.
        
        Extracts main topic from prompt and creates key:
        format: "diagram_type:language:llm_model:normalized_topic"
        
        Returns None if topic cannot be extracted.
        """
        # Extract main topic from prompt
        main_topic = self._extract_main_topic_from_prompt(prompt)
        if not main_topic:
            logger.warning(f"[AutocompleteCache] Cannot extract topic from prompt")
            return None
        
        # Normalize topic: lowercase, trim whitespace
        normalized_topic = main_topic.lower().strip()
        
        # Normalize diagram type (handle aliases)
        normalized_diagram_type = diagram_type.lower().strip()
        if normalized_diagram_type == 'mind_map':
            normalized_diagram_type = 'mindmap'
        
        # Create key: diagram_type:language:llm_model:normalized_topic
        cache_key = f"{normalized_diagram_type}:{language}:{llm_model}:{normalized_topic}"
        
        return cache_key
    
    def _extract_main_topic_from_prompt(self, prompt: str) -> Optional[str]:
        """
        Extract main topic from auto-complete prompt.
        
        Pattern: "Main topic/center: \"TOPIC\""
        
        Returns None if topic cannot be extracted.
        """
        # Pattern 1: English prompt - "Main topic/center: "TOPIC""
        pattern_en = r'Main topic/center:\s*"([^"]+)"'
        match = re.search(pattern_en, prompt)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: Chinese prompt (if different format)
        pattern_zh = r'主主题/中心:\s*"([^"]+)"'
        match = re.search(pattern_zh, prompt)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: Fallback - extract quoted text (longest one is likely topic)
        quoted_pattern = r'"([^"]+)"'
        matches = re.findall(quoted_pattern, prompt)
        if matches:
            return max(matches, key=len).strip()
        
        # Pattern 4: Extract Chinese characters or English words (last resort)
        chinese_pattern = r'[\u4e00-\u9fa5]+'
        chinese_match = re.search(chinese_pattern, prompt)
        if chinese_match:
            return chinese_match.group(0).strip()
        
        return None
    
    async def get(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        
        Returns None if cache miss or expired.
        """
        if not self.enabled:
            return None
        
        cache_key = self._normalize_cache_key(prompt, diagram_type, language, llm_model)
        if not cache_key:
            return None
        
        # Get from cache (TTLCache handles expiration automatically)
        result = self._cache.get(cache_key)
        
        if result:
            self._stats['hits'] += 1
            logger.debug(f"[AutocompleteCache] Cache HIT: {cache_key}")
            return result
        
        self._stats['misses'] += 1
        logger.debug(f"[AutocompleteCache] Cache MISS: {cache_key}")
        return None
    
    async def set(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        response: Dict[str, Any]
    ) -> bool:
        """
        Store result in cache.
        
        Returns True if stored successfully, False otherwise.
        """
        if not self.enabled:
            return False
        
        cache_key = self._normalize_cache_key(prompt, diagram_type, language, llm_model)
        if not cache_key:
            return False
        
        # Store in cache (TTLCache handles TTL automatically)
        old_size = len(self._cache)
        self._cache[cache_key] = response
        
        # Check if eviction occurred (size decreased)
        if len(self._cache) < old_size:
            self._stats['evictions'] += 1
        
        self._stats['sets'] += 1
        logger.debug(f"[AutocompleteCache] Cache SET: {cache_key}")
        
        return True
    
    async def get_or_compute(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        compute_func: Callable[[], Awaitable[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Get from cache, or compute and cache if miss.
        
        Handles concurrent requests for same key:
        - First request: checks cache → miss → acquires lock → calls LLM → stores → returns
        - Concurrent requests: check cache → miss → wait for lock → check cache again → hit → return
        
        This ensures only 1 LLM call per cache key, even with 50+ concurrent requests.
        """
        # Check cache first
        cached = await self.get(prompt, diagram_type, language, llm_model)
        if cached:
            return cached
        
        # Cache miss - get lock for this specific key
        cache_key = self._normalize_cache_key(prompt, diagram_type, language, llm_model)
        if not cache_key:
            # Cannot create cache key - compute directly
            return await compute_func()
        
        # Get or create lock for this cache key
        async with self._lock_lock:
            if cache_key not in self._key_locks:
                self._key_locks[cache_key] = asyncio.Lock()
            key_lock = self._key_locks[cache_key]
        
        # Acquire lock and double-check cache
        async with key_lock:
            # Double-check cache (another request might have populated it)
            cached = await self.get(prompt, diagram_type, language, llm_model)
            if cached:
                return cached
            
            # Still miss - compute
            logger.info(f"[AutocompleteCache] Computing for key: {cache_key}")
            result = await compute_func()
            
            # Store in cache
            await self.set(prompt, diagram_type, language, llm_model, result)
            
            return result
    
    async def invalidate(
        self,
        cache_key: Optional[str] = None,
        diagram_type: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.
        
        Args:
            cache_key: Specific cache key to invalidate
            diagram_type: Invalidate all entries for this diagram type
        
        Returns:
            Number of entries deleted
        """
        count = 0
        
        if cache_key:
            if cache_key in self._cache:
                del self._cache[cache_key]
                count = 1
        elif diagram_type:
            # Remove all entries for this diagram type
            normalized_diagram_type = diagram_type.lower().strip()
            if normalized_diagram_type == 'mind_map':
                normalized_diagram_type = 'mindmap'
            
            keys_to_remove = [
                key for key in list(self._cache.keys())
                if key.startswith(f"{normalized_diagram_type}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
            count = len(keys_to_remove)
        else:
            # Clear all
            count = len(self._cache)
            self._cache.clear()
        
        logger.info(f"[AutocompleteCache] Invalidated {count} entries")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (
            self._stats['hits'] / total_requests * 100
            if total_requests > 0 else 0
        )
        
        return {
            'enabled': self.enabled,
            'size': len(self._cache),
            'maxsize': self.maxsize,
            'ttl_seconds': self.ttl_seconds,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'sets': self._stats['sets'],
            'evictions': self._stats['evictions']
        }


# Global singleton instance
_autocomplete_cache_service: Optional[AutocompleteCacheService] = None


def get_autocomplete_cache_service() -> AutocompleteCacheService:
    """Get the global autocomplete cache service instance."""
    global _autocomplete_cache_service
    
    if _autocomplete_cache_service is None:
        from config.settings import config
        
        _autocomplete_cache_service = AutocompleteCacheService(
            maxsize=getattr(config, 'AUTOCOMPLETE_CACHE_MAX_SIZE', 10000),
            ttl_seconds=getattr(config, 'AUTOCOMPLETE_CACHE_TTL_SECONDS', 86400),
            enabled=getattr(config, 'AUTOCOMPLETE_CACHE_ENABLED', True)
        )
    
    return _autocomplete_cache_service
```

**Checklist:**
- [ ] File created at `services/autocomplete_cache.py`
- [ ] Code copied correctly
- [ ] No syntax errors

---

### Step 3: Add Configuration Settings

**Action:** Add cache configuration to `config/settings.py`

**File:** `config/settings.py`

Add these properties to the `Config` class:

```python
@property
def AUTOCOMPLETE_CACHE_ENABLED(self) -> bool:
    """Whether auto-complete cache is enabled."""
    return self._get_cached_value('AUTOCOMPLETE_CACHE_ENABLED', 'true').lower() == 'true'

@property
def AUTOCOMPLETE_CACHE_MAX_SIZE(self) -> int:
    """Maximum number of cache entries."""
    return int(self._get_cached_value('AUTOCOMPLETE_CACHE_MAX_SIZE', '10000'))

@property
def AUTOCOMPLETE_CACHE_TTL_SECONDS(self) -> int:
    """Cache TTL in seconds (default: 86400 = 24 hours)."""
    return int(self._get_cached_value('AUTOCOMPLETE_CACHE_TTL_SECONDS', '86400'))
```

**Checklist:**
- [ ] Properties added to `Config` class
- [ ] Default values set correctly

---

### Step 4: Integrate Cache into API Endpoint

**Action:** Modify `routers/api.py` to check cache FIRST before calling LLM

**File:** `routers/api.py`

**Important:** Cache check happens BEFORE LLM call. This is the critical point!

**Request Flow:**
```
1. Request arrives → /api/generate_graph
2. Check: Is request_type == 'autocomplete'?
   ├─ NO → Skip cache, call LLM directly
   └─ YES → Continue to cache check
3. Generate cache key from prompt + diagram_type + language + llm_model
4. Check cache: cache.get(cache_key)
   ├─ HIT → Return cached response (NO LLM call!)
   └─ MISS → Continue to LLM call
5. Call LLM (only if cache miss)
6. Store result in cache
7. Return response
```

**Find this section (around line 185-214):**
```python
try:
    # Generate diagram specification - fully async
    # Pass model directly through call chain (no global state)
    # Pass user context for token tracking
    user_id = current_user.id if current_user else None
    organization_id = current_user.organization_id if current_user else None
    
    # Determine request type for token tracking (default to 'diagram_generation')
    request_type = req.request_type if req.request_type else 'diagram_generation'
    
    result = await agent.agent_graph_workflow_with_styles(
        prompt,
        language=language,
        forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
        dimension_preference=req.dimension_preference,
        model=llm_model,  # Pass model explicitly (fixes race condition)
        # Token tracking parameters
        user_id=user_id,
        organization_id=organization_id,
        request_type=request_type,
        endpoint_path='/api/generate_graph'
    )
    
    logger.debug(f"[{request_id}] Generated {result.get('diagram_type', 'unknown')} diagram with {llm_model}")
    
    # Add metadata
    result['llm_model'] = llm_model
    result['request_id'] = request_id
    
    return result
```

**Replace with:**
```python
try:
    # Generate diagram specification - fully async
    # Pass model directly through call chain (no global state)
    # Pass user context for token tracking
    user_id = current_user.id if current_user else None
    organization_id = current_user.organization_id if current_user else None
    
    # Determine request type for token tracking (default to 'diagram_generation')
    request_type = req.request_type if req.request_type else 'diagram_generation'
    
    # Only cache autocomplete requests
    if request_type == 'autocomplete':
        from services.autocomplete_cache import get_autocomplete_cache_service
        
        cache_service = get_autocomplete_cache_service()
        
        # Use get_or_compute for automatic cache handling
        result = await cache_service.get_or_compute(
            prompt=prompt,
            diagram_type=req.diagram_type.value if req.diagram_type else 'unknown',
            language=language,
            llm_model=llm_model,
            compute_func=lambda: agent.agent_graph_workflow_with_styles(
                prompt,
                language=language,
                forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
                dimension_preference=req.dimension_preference,
                model=llm_model,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path='/api/generate_graph'
            )
        )
    else:
        # Non-autocomplete request - no caching
        result = await agent.agent_graph_workflow_with_styles(
            prompt,
            language=language,
            forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
            dimension_preference=req.dimension_preference,
            model=llm_model,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path='/api/generate_graph'
        )
    
    logger.debug(f"[{request_id}] Generated {result.get('diagram_type', 'unknown')} diagram with {llm_model}")
    
    # Add metadata
    result['llm_model'] = llm_model
    result['request_id'] = request_id
    
    return result
```

**Checklist:**
- [ ] Import added: `from services.autocomplete_cache import get_autocomplete_cache_service`
- [ ] Cache check added for `request_type == 'autocomplete'`
- [ ] `get_or_compute` used for autocomplete requests
- [ ] Non-autocomplete requests unchanged

---

### Step 5: Test the Implementation

**Action:** Test cache functionality

**Test 1: Basic Cache Test**

```python
# Test script: test_cache.py
import asyncio
from services.autocomplete_cache import get_autocomplete_cache_service

async def test_cache():
    cache = get_autocomplete_cache_service()
    
    # Test data
    prompt = 'Continue the following mindmap diagram with 1 existing nodes. Main topic/center: "光合作用". Generate additional nodes to complete the diagram structure.'
    diagram_type = 'mindmap'
    language = 'zh'
    llm_model = 'qwen'
    
    # Test response
    test_response = {
        'success': True,
        'spec': {'topic': '光合作用', 'children': []},
        'diagram_type': 'mindmap'
    }
    
    # Test 1: Cache miss (first time)
    result1 = await cache.get(prompt, diagram_type, language, llm_model)
    print(f"Test 1 - Cache miss: {result1 is None}")  # Should be None
    
    # Test 2: Cache set
    await cache.set(prompt, diagram_type, language, llm_model, test_response)
    print("Test 2 - Cache set: OK")
    
    # Test 3: Cache hit (second time)
    result2 = await cache.get(prompt, diagram_type, language, llm_model)
    print(f"Test 3 - Cache hit: {result2 is not None}")  # Should be True
    print(f"Test 3 - Data matches: {result2 == test_response}")  # Should be True
    
    # Test 4: Stats
    stats = cache.get_stats()
    print(f"Test 4 - Stats: {stats}")

if __name__ == '__main__':
    asyncio.run(test_cache())
```

**Run test:**
```bash
python test_cache.py
```

**Expected output:**
```
Test 1 - Cache miss: True
Test 2 - Cache set: OK
Test 3 - Cache hit: True
Test 3 - Data matches: True
Test 4 - Stats: {'enabled': True, 'size': 1, 'hits': 1, 'misses': 1, ...}
```

**Test 2: Concurrent Request Test**

```python
# Test concurrent requests (simulate 50 teachers)
import asyncio
from services.autocomplete_cache import get_autocomplete_cache_service

async def simulate_request(request_id: int, cache, prompt, diagram_type, language, llm_model):
    """Simulate a single request."""
    async def compute():
        print(f"Request {request_id}: Calling LLM...")
        await asyncio.sleep(0.1)  # Simulate LLM call
        return {'success': True, 'spec': {}, 'request_id': request_id}
    
    result = await cache.get_or_compute(
        prompt, diagram_type, language, llm_model, compute
    )
    print(f"Request {request_id}: Got result (request_id={result.get('request_id')})")

async def test_concurrent():
    cache = get_autocomplete_cache_service()
    
    prompt = 'Continue the following mindmap diagram with 1 existing nodes. Main topic/center: "光合作用". Generate additional nodes.'
    diagram_type = 'mindmap'
    language = 'zh'
    llm_model = 'qwen'
    
    # Simulate 50 concurrent requests
    tasks = [
        simulate_request(i, cache, prompt, diagram_type, language, llm_model)
        for i in range(50)
    ]
    
    await asyncio.gather(*tasks)
    
    stats = cache.get_stats()
    print(f"\nFinal stats: {stats}")
    print(f"Expected: 1 LLM call, 49 cache hits")
    print(f"Actual: {stats['misses']} misses, {stats['hits']} hits")

if __name__ == '__main__':
    asyncio.run(test_concurrent())
```

**Expected:** Only 1 LLM call, 49 cache hits

**Checklist:**
- [ ] Basic cache test passes
- [ ] Concurrent request test shows only 1 LLM call
- [ ] Cache stats are correct

---

### Step 6: Add Logging

**Action:** Verify logging is working

**Check logs when testing:**
```bash
# Look for these log messages:
[AutocompleteCache] Cache HIT: mindmap:zh:qwen:光合作用
[AutocompleteCache] Cache MISS: mindmap:zh:qwen:光合作用
[AutocompleteCache] Cache SET: mindmap:zh:qwen:光合作用
```

**Checklist:**
- [ ] Cache hits logged
- [ ] Cache misses logged
- [ ] Cache sets logged

---

### Step 7: Add Admin Endpoints (Optional)

**Action:** Create admin endpoints for cache management

**File:** `routers/admin_cache.py` (NEW FILE)

```python
"""
Admin Cache Management Routes
=============================

Admin endpoints for managing auto-complete cache.

Author: lycosa9527
Made by: MindSpring Team
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from models.auth import User
from utils.auth import get_current_user
from services.autocomplete_cache import get_autocomplete_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/cache", tags=["Admin Cache"])


@router.get("/autocomplete/stats")
async def get_cache_stats(current_user: User = Depends(get_current_user)):
    """Get auto-complete cache statistics."""
    cache_service = get_autocomplete_cache_service()
    stats = cache_service.get_stats()
    return stats


@router.post("/autocomplete/invalidate")
async def invalidate_cache(
    cache_key: Optional[str] = None,
    diagram_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Invalidate cache entries.
    
    Args:
        cache_key: Specific cache key to invalidate
        diagram_type: Invalidate all entries for this diagram type
    """
    cache_service = get_autocomplete_cache_service()
    count = await cache_service.invalidate(cache_key, diagram_type)
    return {"deleted_count": count, "message": f"Invalidated {count} cache entries"}


@router.delete("/autocomplete/clear")
async def clear_cache(current_user: User = Depends(get_current_user)):
    """Clear all cache entries."""
    cache_service = get_autocomplete_cache_service()
    count = await cache_service.invalidate()
    return {"deleted_count": count, "message": f"Cleared {count} cache entries"}
```

**File:** `main.py` or `run_server.py`

**Add router:**
```python
from routers.admin_cache import router as admin_cache_router

app.include_router(admin_cache_router)
```

**Checklist:**
- [ ] Admin endpoints created
- [ ] Router included in main app
- [ ] Endpoints accessible at `/admin/cache/autocomplete/stats`

---

### Step 8: Environment Variables (Optional)

**Action:** Add environment variables for configuration

**File:** `.env` or `env.example`

```bash
# Auto-complete cache configuration
AUTOCOMPLETE_CACHE_ENABLED=true
AUTOCOMPLETE_CACHE_MAX_SIZE=10000
AUTOCOMPLETE_CACHE_TTL_SECONDS=86400  # 24 hours
```

**Checklist:**
- [ ] Environment variables documented
- [ ] Default values work if not set

---

### Step 9: Verify Integration

**Action:** Test end-to-end flow

1. **Start server:**
   ```bash
   python run_server.py
   ```

2. **Make autocomplete request:**
   ```bash
   curl -X POST http://localhost:9527/api/generate_graph \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Continue the following mindmap diagram with 1 existing nodes. Main topic/center: \"光合作用\". Generate additional nodes.",
       "diagram_type": "mindmap",
       "language": "zh",
       "llm": "qwen",
       "request_type": "autocomplete"
     }'
   ```

3. **Make same request again (should be cached):**
   ```bash
   # Same request - should return cached result
   ```

4. **Check cache stats:**
   ```bash
   curl http://localhost:9527/admin/cache/autocomplete/stats
   ```

**Checklist:**
- [ ] First request calls LLM
- [ ] Second request returns cached result
- [ ] Cache stats show 1 hit, 1 miss
- [ ] Response is identical

---

### Step 10: Monitor and Optimize

**Action:** Monitor cache performance

**Check cache stats regularly:**
- Hit rate should be high (>90% in workshop scenario)
- Cache size should stay within limits
- Evictions should be minimal

**Tune if needed:**
- Adjust `AUTOCOMPLETE_CACHE_TTL_SECONDS` if cache too stale
- Adjust `AUTOCOMPLETE_CACHE_MAX_SIZE` if evicting too often

---

## Quick Reference: File Changes Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `requirements.txt` | Add | 1 line (`cachetools>=5.3.0`) |
| `services/autocomplete_cache.py` | Create | ~300 lines |
| `config/settings.py` | Modify | ~15 lines (add 3 properties) |
| `routers/api.py` | Modify | ~20 lines (add cache check) |
| `routers/admin_cache.py` | Create | ~60 lines (optional) |
| `main.py` or `run_server.py` | Modify | 1 line (include router, optional) |

**Total:** ~400 lines of code

---

## Troubleshooting

**Issue: Cache not working**
- Check `AUTOCOMPLETE_CACHE_ENABLED=true` in config
- Check logs for cache HIT/MISS messages
- Verify `request_type == 'autocomplete'` in request

**Issue: Cache key not matching**
- Check topic extraction from prompt
- Verify prompt format matches expected pattern
- Check logs for cache key generation

**Issue: Concurrent requests still calling LLM multiple times**
- Verify `get_or_compute` is being used (not just `get` + `set`)
- Check lock implementation is correct

---

## 5.1 Phase 1: Core Cache Service (Week 1)

**Tasks:**
1. Install cachetools: `pip install cachetools`
2. Create cache service (`services/autocomplete_cache.py`)
3. Implement cache key normalization
4. Add concurrent request handling (locks)
5. Unit tests for cache service

**Files to Create:**
- `services/autocomplete_cache.py` - Cache service implementation (cachetools)
- `tests/services/test_autocomplete_cache.py` - Unit tests

**Files to Modify:**
- `requirements.txt` - Add `cachetools>=5.3.0`
- `routers/api.py` - Integrate cache check before LLM call

**Dependencies:**
```bash
pip install cachetools>=5.3.0  # Professional caching library
```

### 5.2 Phase 2: Integration (Week 1-2)

**Tasks:**
1. Integrate cache service into `/api/generate_graph` endpoint
2. Add cache check before LLM call
3. Handle concurrent requests (lock mechanism)
4. Add logging for cache hits/misses
5. Error handling (fallback if cache fails)

**Files to Modify:**
- `routers/api.py` - Add cache check in `generate_graph()`
- `services/autocomplete_cache.py` - Add concurrent request handling

### 5.3 Phase 3: Cache Management & Persistence (Week 2)

**Tasks:**
1. Add file persistence (optional - save/load cache from disk)
2. Background task for periodic persistence (every 5 minutes)
3. Admin API endpoint for cache statistics
4. Admin API endpoint for cache invalidation
5. Cache statistics tracking

**Files to Create:**
- `routers/admin_cache.py` - Admin cache management endpoints

**Files to Modify:**
- `main.py` or `run_server.py` - Add background persistence task
- `services/autocomplete_cache.py` - Add persistence methods (`_save_to_disk`, `_load_from_disk`)

**Note:** cachetools handles TTL expiration automatically, no cleanup task needed.

### 5.4 Phase 4: Optimization & Monitoring (Week 2-3)

**Tasks:**
1. Add cache hit/miss metrics
2. Performance testing with 50+ concurrent requests
3. Cache size monitoring
4. Documentation

**Files to Modify:**
- `services/autocomplete_cache.py` - Add metrics
- `docs/AUTO_COMPLETE_CACHE_FRAMEWORK.md` - Update with implementation details

---

## 6. Concurrent Request Handling

### 6.1 Problem

When 50 users request auto-complete simultaneously:
- All 50 requests check cache → all miss
- All 50 requests call LLM → 50 duplicate LLM calls

### 6.2 Solution: Request Deduplication

**Approach:** Use asyncio lock per cache key

```python
class AutocompleteCacheService:
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock_lock = asyncio.Lock()  # Lock for managing locks
    
    async def get_or_compute(
        self,
        prompt: str,
        diagram_type: str,
        language: str,
        llm_model: str,
        compute_func: Callable[[], Awaitable[Dict]]
    ) -> Dict[str, Any]:
        """
        Get from cache, or compute and cache if miss.
        Handles concurrent requests for same key.
        """
        cache_key = self._normalize_key(prompt, diagram_type, language, llm_model)
        
        # Check cache first
        cached = await self.get(prompt, diagram_type, language, llm_model)
        if cached:
            return cached
        
        # Cache miss - acquire lock for this key
        async with self._lock_lock:
            if cache_key not in self._locks:
                self._locks[cache_key] = asyncio.Lock()
            lock = self._locks[cache_key]
        
        async with lock:
            # Double-check cache (another request might have populated it)
            cached = await self.get(prompt, diagram_type, language, llm_model)
            if cached:
                return cached
            
            # Still miss - compute
            result = await compute_func()
            
            # Store in cache
            await self.set(prompt, diagram_type, language, llm_model, result)
            
            return result
```

**Flow:**
1. Request 1 checks cache → miss → acquires lock → calls LLM → stores → releases lock
2. Request 2-50 check cache → miss → wait for lock → lock acquired → check cache again → hit → return cached result

**Result:** Only 1 LLM call per cache key, even with 50 concurrent requests.

---

## 7. Cache Key Normalization Implementation

### 7.1 Prompt Pattern Analysis

From `llm-autocomplete-manager.js` line 183:
```javascript
const prompt = `Continue the following ${currentDiagramType} diagram with ${existingNodes.length} existing nodes. Main topic/center: "${mainTopic}". Generate additional nodes to complete the diagram structure.`;
```

**Pattern:**
- English: `"Continue the following {diagram_type} diagram with {N} existing nodes. Main topic/center: "{topic}". Generate additional nodes..."`
- Chinese: Similar pattern with Chinese text

### 7.2 Extraction Function

```python
import re
from typing import Optional

def extract_main_topic_from_prompt(prompt: str) -> Optional[str]:
    """
    Extract main topic from auto-complete prompt.
    
    Examples:
        Input: 'Continue the following mindmap diagram with 1 existing nodes. Main topic/center: "光合作用". Generate...'
        Output: '光合作用'
        
        Input: 'Continue the following bubble_map diagram with 2 existing nodes. Main topic/center: "Photosynthesis". Generate...'
        Output: 'Photosynthesis'
    """
    # Pattern 1: English prompt
    # "Main topic/center: "TOPIC""
    pattern_en = r'Main topic/center:\s*"([^"]+)"'
    match = re.search(pattern_en, prompt)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: Chinese prompt (if different format)
    # "主主题/中心: "TOPIC""
    pattern_zh = r'主主题/中心:\s*"([^"]+)"'
    match = re.search(pattern_zh, prompt)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: Fallback - extract quoted text
    quoted_pattern = r'"([^"]+)"'
    matches = re.findall(quoted_pattern, prompt)
    if matches:
        # Return the longest quoted string (likely the topic)
        return max(matches, key=len).strip()
    
    # Pattern 4: Extract Chinese characters or English words
    # This is a last resort
    chinese_pattern = r'[\u4e00-\u9fa5]+'
    chinese_match = re.search(chinese_pattern, prompt)
    if chinese_match:
        return chinese_match.group(0).strip()
    
    # If all patterns fail, return None (cache will not be used)
    return None

def normalize_cache_key(
    prompt: str,
    diagram_type: str,
    language: str,
    llm_model: str
) -> Optional[str]:
    """
    Create normalized cache key from request parameters.
    
    Returns None if topic cannot be extracted (cache disabled for this request).
    """
    main_topic = extract_main_topic_from_prompt(prompt)
    if not main_topic:
        return None
    
    # Normalize topic: lowercase, trim whitespace
    normalized_topic = main_topic.lower().strip()
    
    # Normalize diagram type (handle aliases)
    normalized_diagram_type = diagram_type.lower().strip()
    if normalized_diagram_type == 'mind_map':
        normalized_diagram_type = 'mindmap'
    
    # Create key: diagram_type:language:llm_model:normalized_topic
    cache_key = f"{normalized_diagram_type}:{language}:{llm_model}:{normalized_topic}"
    
    return cache_key
```

---

## 8. Configuration

### 8.1 Environment Variables

```bash
# Auto-complete cache configuration
AUTOCOMPLETE_CACHE_ENABLED=true
AUTOCOMPLETE_CACHE_TTL_HOURS=24
AUTOCOMPLETE_CACHE_MAX_SIZE=10000  # Max entries before LRU eviction
AUTOCOMPLETE_CACHE_CLEANUP_INTERVAL_HOURS=1  # Background cleanup interval
```

### 8.2 Settings Integration

Add to `config/settings.py`:

```python
@property
def AUTOCOMPLETE_CACHE_ENABLED(self) -> bool:
    return self._get_cached_value('AUTOCOMPLETE_CACHE_ENABLED', 'true').lower() == 'true'

@property
def AUTOCOMPLETE_CACHE_TTL_HOURS(self) -> int:
    return int(self._get_cached_value('AUTOCOMPLETE_CACHE_TTL_HOURS', '24'))

@property
def AUTOCOMPLETE_CACHE_MAX_SIZE(self) -> int:
    return int(self._get_cached_value('AUTOCOMPLETE_CACHE_MAX_SIZE', '10000'))
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

1. **Cache Key Normalization:**
   - Test topic extraction from various prompt formats
   - Test key normalization (case-insensitive, whitespace handling)
   - Test edge cases (missing topic, malformed prompts)

2. **Cache Service:**
   - Test cache get/set operations
   - Test TTL expiration
   - Test concurrent request handling
   - Test cache invalidation

### 9.2 Integration Tests

1. **API Endpoint:**
   - Test cache hit scenario (return cached result)
   - Test cache miss scenario (call LLM, store, return)
   - Test concurrent requests (50 simultaneous requests)

2. **Performance Tests:**
   - Measure cache lookup latency
   - Measure LLM call reduction (before/after cache)

### 9.3 Load Testing

**Scenario:** 50 teachers in workshop
- Before cache: 50 × 4 = 200 LLM calls
- After cache: 4 LLM calls (first request per model) + 196 cache hits
- Expected cache hit rate: 98%

---

## 10. Monitoring & Observability

### 10.1 Logging

```python
logger.info(
    f"[AutocompleteCache] Cache {'HIT' if cached else 'MISS'} - "
    f"key={cache_key}, model={llm_model}, diagram={diagram_type}"
)
```

### 10.2 Metrics

Track:
- Cache hit rate (hits / (hits + misses))
- Cache size (number of entries)
- Cache evictions (LRU removals)
- Average cache lookup time
- Cache invalidation count

### 10.3 Admin Endpoints

```python
@router.get("/admin/cache/autocomplete/stats")
async def get_cache_stats():
    """Get cache statistics."""
    return {
        "enabled": cache_service.is_enabled(),
        "hit_rate": cache_service.get_hit_rate(),
        "total_entries": cache_service.get_size(),
        "total_hits": cache_service.get_total_hits(),
        "total_misses": cache_service.get_total_misses(),
    }

@router.post("/admin/cache/autocomplete/invalidate")
async def invalidate_cache(
    cache_key: Optional[str] = None,
    diagram_type: Optional[str] = None
):
    """Invalidate cache entries."""
    count = await cache_service.invalidate(cache_key, diagram_type)
    return {"deleted_count": count}
```

---

## 11. Risk Assessment & Mitigation

### 11.1 Risks

1. **Cache Key Collision:**
   - Risk: Different topics generate same cache key
   - Mitigation: Use hash of full prompt as part of key (if topic extraction fails)

2. **Stale Cache:**
   - Risk: Cached result becomes outdated
   - Mitigation: TTL-based expiration (24 hours default)

3. **Cache Size Growth:**
   - Risk: Cache grows unbounded
   - Mitigation: LRU eviction when max size reached

4. **Cache Failures:**
   - Risk: Cache service fails, breaks auto-complete
   - Mitigation: Graceful fallback to direct LLM call

5. **Concurrent Write Issues:**
   - Risk: Race conditions when storing cache
   - Mitigation: Database-level locking, asyncio locks

### 11.2 Fallback Strategy

```python
async def get_cached_or_compute(...):
    try:
        # Try cache
        cached = await cache_service.get(...)
        if cached:
            return cached
        
        # Cache miss - compute
        result = await compute_func()
        
        # Try to store (non-blocking)
        try:
            await cache_service.set(...)
        except Exception as e:
            logger.warning(f"Cache store failed (non-critical): {e}")
        
        return result
    except Exception as e:
        # Cache service failed - fallback to direct compute
        logger.error(f"Cache service error: {e}, falling back to direct LLM call")
        return await compute_func()
```

---

## 12. Future Enhancements

1. **Cache Warming:**
   - Pre-populate cache with common topics
   - Background job to refresh popular cache entries

2. **Cache Analytics:**
   - Track most cached topics
   - Identify cache patterns
   - Optimize TTL based on access patterns

3. **Distributed Cache:**
   - If scaling to multiple servers, use Redis for shared cache
   - Current design (database) works for single server

4. **Cache Compression:**
   - Compress large responses before storing
   - Reduce database storage requirements

5. **Smart Cache Invalidation:**
   - Invalidate related cache entries when diagram type changes
   - Invalidate by topic similarity (fuzzy matching)

---

## 13. Success Metrics

**Before Cache:**
- 50 teachers × 4 models = 200 LLM API calls
- Average response time: 3-10 seconds per model
- Total cost: 200 × cost_per_call

**After Cache:**
- 4 LLM API calls (first request per model)
- 196 cache hits (< 10ms each)
- Average response time: < 50ms for cached requests
- Total cost: 4 × cost_per_call
- **Cost reduction: 98%**
- **Response time improvement: 99%** (for cached requests)

---

## 14. Implementation Checklist

- [ ] Install cachetools: `pip install cachetools>=5.3.0`
- [ ] Add cachetools to `requirements.txt`
- [ ] Create cache service (`services/autocomplete_cache.py`)
- [ ] Implement cache key normalization
- [ ] Add concurrent request handling (per-key locks)
- [ ] Integrate cache into `/api/generate_graph` endpoint
- [ ] Add logging for cache hits/misses
- [ ] Add error handling and fallback
- [ ] Add file persistence (optional - Phase 3)
- [ ] Add admin endpoints for cache management
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Performance testing with 50+ concurrent requests
- [ ] Documentation
- [ ] Deploy and monitor

**Note:** No database migration needed - using in-memory cachetools instead.

---

## Appendix A: Code Structure

```
MindGraph/
├── services/
│   └── autocomplete_cache.py          # NEW: Cache service (cachetools)
├── routers/
│   ├── api.py                         # MODIFY: Add cache check
│   └── admin_cache.py                 # NEW: Admin cache endpoints
├── config/
│   └── settings.py                    # MODIFY: Add cache configuration
├── requirements.txt                   # MODIFY: Add cachetools dependency
└── tests/
    └── services/
        └── test_autocomplete_cache.py  # NEW: Cache service tests
```

**Note:** No database model needed - using cachetools in-memory cache instead.

---

## Appendix B: Example Usage

### Backend (Python)

```python
from services.autocomplete_cache import autocomplete_cache_service

@router.post('/generate_graph')
async def generate_graph(req: GenerateRequest, ...):
    # Only cache autocomplete requests
    if req.request_type == 'autocomplete':
        # Use get_or_compute for automatic concurrent request handling
        result = await autocomplete_cache_service.get_or_compute(
            prompt=req.prompt,
            diagram_type=req.diagram_type,
            language=req.language,
            llm_model=req.llm,
            compute_func=lambda: agent.agent_graph_workflow_with_styles(
                req.prompt,
                language=req.language,
                forced_diagram_type=req.diagram_type,
                model=req.llm,
                ...
            )
        )
        return result
    
    # Non-autocomplete request - no caching
    result = await agent.agent_graph_workflow_with_styles(...)
    return result
```

**Benefits of `get_or_compute`:**
- Automatic cache check
- Handles concurrent requests (only first computes)
- Stores result automatically
- Cleaner code (no manual get/set)

### Frontend (No Changes Required)

Frontend code remains unchanged. Cache is transparent to frontend.

---

## Conclusion

This framework provides a comprehensive design for implementing server-side caching for auto-complete requests. The design prioritizes:

1. **Simplicity:** Database-based cache (no new dependencies)
2. **Reliability:** Graceful fallback if cache fails
3. **Performance:** Significant reduction in LLM calls (98% reduction)
4. **Scalability:** Handles concurrent requests efficiently
5. **Maintainability:** Clear separation of concerns, well-documented

The implementation can be done incrementally, with each phase adding value independently.

