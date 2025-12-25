# Concurrent Registration Analysis: 500 Teachers Simultaneous Registration

## Overview
This document analyzes how the caching system behaves when 500 teachers register simultaneously in a workshop scenario.

## Current Architecture

### 1. **Organization Lookup (Same Invitation Code for All 500)**

**Flow:**
```
Request 1:  Cache miss → SQLite query → Cache write (org:invite:XXXXX → org_id)
Requests 2-500: Cache hit → Redis lookup → Return org (FAST!)
```

**Performance:**
- ✅ **First request**: ~5-10ms (SQLite query + cache write)
- ✅ **Subsequent 499 requests**: ~0.1-1ms (Redis hash lookup)
- ✅ **Redis handles concurrent reads excellently** - no bottlenecks

**Cache Key Structure:**
- Index: `org:invite:XXXXX` → `org_id` (string)
- Data: `org:{id}` → Hash with org details

**Result:** Organization lookup scales perfectly - only 1 SQLite query for all 500 registrations.

---

### 2. **Phone Uniqueness Check (500 Different Phones)**

**Flow:**
```
Each request: user_cache.get_by_phone(phone)
  → Check Redis index: user:phone:13800138000 → user_id
  → If found: Load user from cache (user:{id})
  → If not found: SQLite query → Cache write
```

**Performance:**
- ✅ **Cache hits**: ~0.1-1ms (Redis lookup)
- ⚠️ **Cache misses**: ~5-10ms (SQLite query + cache write)
- ⚠️ **Race Condition Risk**: Two users with same phone registering simultaneously

**Race Condition Scenario:**
```
Time  T1 (User A)              T2 (User B)
----  --------------------     --------------------
0ms   Check cache: MISS        
1ms   SQLite query: NOT FOUND                    Check cache: MISS
2ms   Insert into SQLite                         SQLite query: NOT FOUND
3ms   Commit ✅                                   Insert into SQLite
4ms   Cache write                                 Commit ❌ UNIQUE CONSTRAINT VIOLATION
```

**Current Protection:**
- ✅ SQLite unique constraint on `phone` column catches duplicates
- ⚠️ **Issue**: Both requests pass cache check, but only one succeeds
- ⚠️ **Impact**: User B gets 500 error after wasting time/resources

**Cache Key Structure:**
- Index: `user:phone:13800138000` → `user_id` (string, permanent)
- Data: `user:{id}` → Hash with user details

**Result:** Phone checks are fast, but race condition exists (handled by SQLite constraint).

---

### 3. **User Creation (500 Concurrent SQLite Writes)**

**Flow:**
```
Each request:
  1. db.add(new_user)
  2. db.commit()  ← BOTTLENECK HERE
  3. db.refresh(new_user)
  4. user_cache.cache_user(new_user)  ← Redis write
```

**SQLite Configuration:**
- ✅ **WAL Mode**: Enabled (allows multiple readers + one writer)
- ⚠️ **Busy Timeout**: 150ms per connection
- ⚠️ **Connection Pool**: 15 base + 30 overflow = **45 max connections**
- ⚠️ **No Retry Logic**: Registration commit has no retry on lock errors

**Concurrency Behavior:**
```
With WAL Mode:
- Multiple readers can read simultaneously ✅
- Only ONE writer can write at a time ⚠️
- Other writers wait (up to 150ms) then fail if still locked
```

**500 Concurrent Writes Scenario:**
```
Time    Active Writes    Status
----    --------------   ------
0ms     500 queued       All requests arrive simultaneously
1ms     1 writing        Request 1 starts commit
2ms     1 writing        Request 1 commits ✅ (takes ~5-10ms)
10ms    1 writing        Request 2 starts commit
15ms    1 writing        Request 2 commits ✅
...     ...              Sequential writes (one at a time)
```

**Estimated Timeline:**
- **Best case**: 500 writes × 5ms = **2.5 seconds** (if perfectly sequential)
- **Realistic**: With lock contention = **5-10 seconds** for all 500
- **Worst case**: Some requests timeout after 150ms → **failures**

**Current Issues:**
1. ❌ **No retry logic** - if commit fails due to lock, request fails immediately
2. ⚠️ **Connection pool exhaustion** - 500 requests compete for 45 connections
3. ⚠️ **Sequential writes** - WAL mode still serializes writes

**Result:** SQLite write bottleneck - will take 5-10 seconds for all 500 registrations.

---

### 4. **Cache Writes (500 Concurrent Redis Writes)**

**Flow:**
```
Each request after SQLite commit:
  user_cache.cache_user(new_user)
    → Serialize user data
    → Redis HSET user:{id} {data}
    → Redis SET user:phone:{phone} {id}
```

**Performance:**
- ✅ **Redis handles concurrent writes excellently**
- ✅ **Each user cached independently** (different keys)
- ✅ **Non-blocking** - cache failures don't fail registration
- ✅ **Estimated time**: ~1-2ms per cache write

**Cache Key Structure:**
- Data: `user:{id}` → Hash with user details
- Index: `user:phone:{phone}` → `user_id` (string, permanent)

**Result:** Redis cache writes are fast and parallel - no bottlenecks here.

---

## Summary: How Caching Works with 500 Concurrent Registrations

### ✅ **What Works Well:**

1. **Organization Lookup**
   - First request: SQLite query + cache write
   - Remaining 499: Redis cache hits (0.1-1ms each)
   - **Total SQLite queries: 1** (excellent!)

2. **Phone Uniqueness Checks**
   - Cache hits: Fast Redis lookups
   - Cache misses: SQLite queries (distributed across 500 phones)
   - **Most phones not in cache initially** → ~500 SQLite queries

3. **Redis Cache Writes**
   - Parallel writes (no contention)
   - Non-blocking (failures don't affect registration)
   - **Fast**: ~1-2ms per write

### ⚠️ **Bottlenecks & Issues:**

1. **SQLite Write Serialization** ⚠️ **MAJOR BOTTLENECK**
   - WAL mode allows only **one writer at a time**
   - 500 writes must happen **sequentially**
   - Estimated: **5-10 seconds** for all 500 registrations
   - Some requests may timeout (150ms busy timeout)

2. **Connection Pool Exhaustion** ⚠️
   - Max 45 connections
   - 500 requests compete for connections
   - Requests wait for available connection (up to 30s timeout)

3. **No Retry Logic for Registration** ❌
   - If commit fails due to lock, request fails immediately
   - Should retry with exponential backoff (like captcha verification)

4. **Race Condition on Phone Check** ⚠️ (Minor)
   - Two users with same phone can both pass cache check
   - SQLite unique constraint catches it, but one request wastes time

---

## Recommendations for 500 Concurrent Registrations

### 1. **Add Retry Logic for Registration Commits** 🔴 **HIGH PRIORITY**

```python
# In routers/auth.py register() function
max_retries = 3
for attempt in range(max_retries):
    try:
        db.commit()
        break
    except OperationalError as e:
        if "database is locked" in str(e).lower() and attempt < max_retries - 1:
            await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
            continue
        raise
```

### 2. **Increase Connection Pool Size** 🟡 **MEDIUM PRIORITY**

```python
# In config/database.py
SQLITE_POOL_SIZE = 50        # Increased from 15
SQLITE_MAX_OVERFLOW = 100     # Increased from 30
# Total: 150 connections (enough for 500 concurrent requests)
```

### 3. **Increase Busy Timeout** 🟡 **MEDIUM PRIORITY**

```python
# In config/database.py enable_wal_mode()
cursor.execute("PRAGMA busy_timeout=500")  # Increased from 150ms to 500ms
```

### 4. **Consider Distributed Lock for Phone Uniqueness** 🟢 **LOW PRIORITY**

Use Redis distributed lock to prevent race condition:
```python
# Before phone check, acquire lock
lock_key = f"register:phone:{phone}"
with redis_lock(lock_key, timeout=5):
    existing_user = user_cache.get_by_phone(phone)
    if existing_user:
        raise HTTPException(...)
    # Create user...
```

### 5. **Monitor and Log Registration Performance** 🟢 **MONITORING**

Add metrics:
- Registration queue time
- SQLite commit duration
- Cache hit/miss rates
- Failed registrations due to locks

---

## Expected Performance with 500 Concurrent Registrations

### **Current System (No Optimizations):**
- **Organization lookups**: ~1ms average (1 SQLite + 499 Redis)
- **Phone checks**: ~5-10ms average (mostly cache misses initially)
- **User creation**: **5-10 seconds** (sequential SQLite writes)
- **Cache writes**: ~1-2ms average (parallel Redis writes)
- **Total time**: **5-10 seconds** for all 500 registrations
- **Failures**: ~5-10% may fail due to timeouts/locks

### **With Optimizations:**
- **Retry logic**: Reduces failures from 5-10% to <1%
- **Larger connection pool**: Reduces connection wait time
- **Increased busy timeout**: Reduces timeout failures
- **Total time**: Still **5-10 seconds** (SQLite write serialization is fundamental limitation)

---

## Conclusion

**Caching works excellently** for reads (organization lookup, phone checks). The bottleneck is **SQLite write serialization**, which is a fundamental limitation of SQLite's WAL mode. 

**Key Insight:** With 500 concurrent registrations:
- ✅ **1 SQLite query** for organization (thanks to caching!)
- ⚠️ **~500 SQLite queries** for phone checks (expected - new phones)
- ❌ **500 sequential SQLite writes** (bottleneck - takes 5-10 seconds)
- ✅ **500 parallel Redis cache writes** (fast - ~1-2ms each)

**Recommendation:** Add retry logic and increase connection pool/busy timeout to handle the SQLite write bottleneck gracefully.

