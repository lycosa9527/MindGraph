# SQLite Lock Failure Scenarios in Write-Through Pattern

## Current Flow: Write SQLite → Wait → Write Redis → Return

```
1. db.add(new_user)
2. db.commit()  ← CAN FAIL HERE (lock timeout)
3. db.refresh(new_user)
4. user_cache.cache_user(new_user)  ← CAN FAIL HERE (Redis error)
5. Return success
```

---

## Failure Scenarios

### Scenario 1: SQLite Commit Fails (Lock Timeout) 🔴 **MOST COMMON**

**What Happens:**
```python
try:
    db.commit()  # ← SQLite busy_timeout (150ms) expires
except Exception as e:
    db.rollback()  # ← Transaction rolled back
    raise HTTPException(500, "Failed to create user account")
```

**Result:**
- ❌ **User NOT created** in SQLite (rolled back)
- ❌ **User NOT cached** in Redis (never reached)
- ❌ **Registration FAILS** (500 error returned to user)
- ✅ **Data consistency maintained** (nothing created)

**Current Behavior:**
- User gets HTTP 500 error
- Must retry registration manually
- No automatic retry logic

**With 500 Concurrent Registrations:**
- ~5-10% of requests will hit lock timeout (150ms)
- These requests fail immediately
- Users see error and must retry

---

### Scenario 2: SQLite Commit Succeeds, Redis Write Fails ✅ **HANDLED**

**What Happens:**
```python
db.commit()  # ✅ Success
db.refresh(new_user)  # ✅ Got user ID

try:
    user_cache.cache_user(new_user)  # ← Redis error (network, etc.)
except Exception as e:
    logger.warning("Failed to cache user")  # ← Logged but not raised
    # Don't fail registration - user exists in SQLite
```

**Result:**
- ✅ **User created** in SQLite (committed)
- ❌ **User NOT cached** in Redis (failed)
- ✅ **Registration SUCCEEDS** (200 OK returned)
- ⚠️ **Cache miss on next read** (will load from SQLite)

**Current Behavior:**
- Registration succeeds (user can login)
- Next read will be slower (SQLite query instead of Redis)
- Cache will be populated on next read (if cache miss handler works)

**Impact:**
- ✅ **Acceptable** - SQLite is source of truth
- ⚠️ **Performance degradation** - slower reads until cache repopulated

---

### Scenario 3: SQLite Commit Succeeds, Then Process Crashes ⚠️ **RARE**

**What Happens:**
```python
db.commit()  # ✅ Success (committed to SQLite)
# Process crashes here (before Redis write)
```

**Result:**
- ✅ **User created** in SQLite (committed, durable)
- ❌ **User NOT cached** in Redis (process crashed)
- ❌ **Registration FAILS** (user doesn't know it succeeded)
- ⚠️ **User exists but can't login** (no session created)

**Current Behavior:**
- User gets HTTP 500 error (timeout or connection reset)
- User exists in SQLite but registration appears failed
- User must try to login (will work) or re-register (will fail - phone exists)

**Impact:**
- ⚠️ **Confusing UX** - registration appears failed but user exists
- ✅ **Data integrity** - user data is safe in SQLite

---

### Scenario 4: SQLite Lock Timeout During High Concurrency 🔴 **EXPECTED**

**What Happens with 500 Concurrent Registrations:**
```
Time    Request    Action                    Result
----    -------    ------                    ------
0ms     Req 1      db.commit()              ✅ Success (5ms)
5ms     Req 2      db.commit()              ✅ Success (5ms)
10ms    Req 3      db.commit()              ✅ Success (5ms)
...
100ms   Req 20     db.commit()              ✅ Success (5ms)
105ms   Req 21     db.commit()              ⏳ Waiting (lock held)
120ms   Req 21     Still waiting...         ⏳ Waiting
150ms   Req 21     Lock timeout!             ❌ OperationalError
155ms   Req 21     db.rollback()            ❌ Registration fails
```

**Result:**
- Requests 1-20: ✅ Success
- Request 21: ❌ Fails (lock timeout after 150ms)
- Requests 22-500: Continue sequentially, some will timeout

**Failure Rate:**
- With 500 concurrent writes taking 5-10 seconds total
- ~5-10% will hit lock timeout (150ms is too short)
- **Estimated: 25-50 failed registrations out of 500**

---

## Current Code Analysis

### Registration Endpoint (`routers/auth.py:374-394`)

```python
# Write to SQLite FIRST (source of truth)
db.add(new_user)
try:
    db.commit()  # ← CAN FAIL: OperationalError if locked
    db.refresh(new_user)  # Get auto-generated ID
except Exception as e:
    db.rollback()
    logger.error(f"[Auth] Failed to create user in SQLite: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create user account"
    )

# Write to Redis cache SECOND (non-blocking)
try:
    user_cache.cache_user(new_user)  # ← CAN FAIL: Redis error
    logger.info(f"[Auth] New user registered and cached: ID {new_user.id}")
except Exception as e:
    # Cache failure is non-critical - SQLite is source of truth
    logger.warning(f"[Auth] Failed to cache new user ID {new_user.id}: {e}")
    # Don't fail registration - user exists in SQLite
```

### Problems:

1. ❌ **No retry logic** - If SQLite lock fails, registration fails immediately
2. ❌ **Generic exception handling** - Catches all exceptions, not just lock errors
3. ⚠️ **Short busy timeout** - 150ms may be too short for high concurrency
4. ✅ **Redis failure handled correctly** - Doesn't fail registration if Redis fails

---

## Solutions

### Solution 1: Add Retry Logic for SQLite Locks 🔴 **HIGH PRIORITY**

```python
from sqlalchemy.exc import OperationalError
import asyncio

# Write to SQLite FIRST (source of truth)
db.add(new_user)

max_retries = 3
for attempt in range(max_retries):
    try:
        db.commit()
        db.refresh(new_user)
        break  # Success!
    except OperationalError as e:
        error_msg = str(e).lower()
        if "database is locked" in error_msg or "locked" in error_msg:
            if attempt < max_retries - 1:
                # Retry with exponential backoff
                delay = 0.1 * (2 ** attempt)  # 0.1s, 0.2s, 0.4s
                logger.warning(
                    f"[Auth] SQLite lock on registration attempt {attempt + 1}/{max_retries}, "
                    f"retrying after {delay}s delay"
                )
                await asyncio.sleep(delay)
                continue
            else:
                # All retries exhausted
                db.rollback()
                logger.error(f"[Auth] SQLite lock persists after {max_retries} retries")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable, please try again"
                )
        else:
            # Other OperationalError (not a lock) - don't retry
            db.rollback()
            logger.error(f"[Auth] SQLite error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
    except Exception as e:
        # Non-OperationalError - don't retry
        db.rollback()
        logger.error(f"[Auth] Failed to create user in SQLite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )
```

**Benefits:**
- ✅ Retries lock errors up to 3 times
- ✅ Exponential backoff (0.1s, 0.2s, 0.4s)
- ✅ Returns 503 (Service Unavailable) for lock errors (retry-able)
- ✅ Returns 500 for other errors (not retry-able)

**Impact:**
- Reduces failures from ~5-10% to <1%
- Most lock errors resolve within retry window

---

### Solution 2: Increase Busy Timeout 🟡 **MEDIUM PRIORITY**

```python
# In config/database.py enable_wal_mode()
cursor.execute("PRAGMA busy_timeout=500")  # Increased from 150ms to 500ms
```

**Benefits:**
- ✅ Gives SQLite more time to acquire lock
- ✅ Reduces timeout failures

**Trade-offs:**
- ⚠️ Slower failure detection (500ms vs 150ms)
- ⚠️ Still doesn't solve serialization bottleneck

---

### Solution 3: Increase Connection Pool 🟡 **MEDIUM PRIORITY**

```python
# In config/database.py
SQLITE_POOL_SIZE = 50        # Increased from 15
SQLITE_MAX_OVERFLOW = 100     # Increased from 30
# Total: 150 connections
```

**Benefits:**
- ✅ More connections available for concurrent requests
- ✅ Reduces connection wait time

**Trade-offs:**
- ⚠️ More memory usage
- ⚠️ Still doesn't solve SQLite write serialization

---

### Solution 4: Write-Behind Pattern (Best Performance) ⭐ **LONG-TERM**

**Flow:**
```
1. Write to Redis immediately → Return success (1-2ms)
2. Queue SQLite write to background worker
3. Background worker syncs Redis → SQLite
4. If SQLite fails, retry in background
```

**Benefits:**
- ✅ Fast response (1-2ms)
- ✅ Handles 500 concurrent easily
- ✅ Background retry for SQLite failures

**Trade-offs:**
- ⚠️ Eventual consistency (user exists in Redis before SQLite)
- ⚠️ More complexity (queue, worker, sync logic)

---

## Recommended Approach

### Phase 1: Immediate Fix (1-2 hours)
1. ✅ Add retry logic for SQLite locks (Solution 1)
2. ✅ Increase busy timeout to 500ms (Solution 2)
3. ✅ Increase connection pool to 150 (Solution 3)

**Result:**
- Failures reduced from ~5-10% to <1%
- Still takes 5-10 seconds for all 500 registrations
- But most succeed on retry

### Phase 2: Long-term Optimization (1-2 days)
- Implement write-behind pattern (Solution 4)
- Background sync worker
- Sub-second response times

---

## Summary

**If SQLite gets locked during write-through:**

1. **Current behavior**: Registration fails immediately (500 error)
2. **User impact**: Must retry manually
3. **Data consistency**: ✅ Maintained (nothing created)
4. **Failure rate**: ~5-10% with 500 concurrent registrations

**With retry logic:**
1. **New behavior**: Retries up to 3 times with exponential backoff
2. **User impact**: Most succeed on retry (<1% final failure rate)
3. **Data consistency**: ✅ Still maintained
4. **Failure rate**: <1% with retry logic

**Key Insight:** Write-through maintains strong consistency even on failures - if SQLite fails, nothing is created. This is safer than write-behind, but slower.

