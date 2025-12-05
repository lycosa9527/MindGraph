# Sticky Sessions for Captcha Storage

## Current Request Routing (Uvicorn Default)

**Uvicorn uses round-robin load balancing:**

```
Request 1 → Master Process → Routes to Worker 1
Request 2 → Master Process → Routes to Worker 2
Request 3 → Master Process → Routes to Worker 3
Request 4 → Master Process → Routes to Worker 4
Request 5 → Master Process → Routes to Worker 1 (round-robin)
```

**Problem:**
- Captcha generation: Request goes to Worker 1
- Captcha verification: Request goes to Worker 3 (different worker!)
- Result: Captcha not found ❌

## Sticky Sessions Solution

**Route same user to same worker:**

```
User A (IP: 192.168.1.100):
  Request 1 (captcha) → Worker 1
  Request 2 (login)   → Worker 1 ✅ (same worker!)

User B (IP: 192.168.1.101):
  Request 1 (captcha) → Worker 2
  Request 2 (login)   → Worker 2 ✅ (same worker!)
```

**How it works:**
- Hash user's IP address (or session ID)
- Route to same worker based on hash
- Captcha stays in same worker's memory

## Implementation Options

### Option 1: IP-Based Sticky Sessions (Nginx)

**If you're using Nginx as reverse proxy:**

```nginx
upstream backend {
    ip_hash;  # Route by IP address
    server localhost:9527;
    server localhost:9528;
    server localhost:9529;
    server localhost:9530;
}

server {
    location / {
        proxy_pass http://backend;
    }
}
```

**Pros:**
- ✅ Simple configuration
- ✅ Works with existing setup
- ✅ Captcha stays on same worker

**Cons:**
- ❌ Uneven load balancing (some IPs get more traffic)
- ❌ If worker crashes, user loses session
- ❌ Doesn't work if users share IP (school network)

### Option 2: Session-Based Sticky Sessions (Application Level)

**Use session cookie to route:**

```python
# In FastAPI middleware
@app.middleware("http")
async def sticky_session_middleware(request: Request, call_next):
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Hash session ID to determine worker
    worker_id = hash(session_id) % num_workers
    
    # Add header to route to specific worker
    request.state.target_worker = worker_id
    
    response = await call_next(request)
    response.set_cookie("session_id", session_id)
    return response
```

**But wait...** Uvicorn doesn't support custom routing logic easily. You'd need:
- Custom load balancer
- Or use Nginx with session-based routing

### Option 3: Uvicorn Doesn't Support Sticky Sessions Natively

**Uvicorn's master process uses simple round-robin:**
- No built-in sticky session support
- No IP-based routing
- No session-based routing

**To implement sticky sessions, you need:**
- External load balancer (Nginx, HAProxy)
- Or custom routing logic (complex)

## Why Sticky Sessions Are Not Ideal

### Problems:

1. **Uneven Load Distribution**
   ```
   Worker 1: 100 users (busy!)
   Worker 2: 10 users (idle)
   Worker 3: 5 users (idle)
   Worker 4: 85 users (busy!)
   ```
   - Some workers overloaded
   - Others underutilized

2. **Worker Crash = Lost Session**
   ```
   User's session on Worker 2
   Worker 2 crashes
   User's captcha lost ❌
   User must refresh and start over
   ```

3. **Shared IP Problem**
   ```
   School network: 50 teachers share same IP
   All routed to Worker 1
   Worker 1 overloaded ❌
   ```

4. **Doesn't Solve the Real Problem**
   - Just avoids it, doesn't fix it
   - Still need shared storage for other features
   - Not scalable

## Better Solution: Shared Storage

Instead of sticky sessions, use shared storage:

### Current: Hybrid File-Based Storage
- ✅ Works across all workers
- ✅ No routing needed
- ⚠️ 5-second sync delay

### Better: Redis
- ✅ Works across all workers
- ✅ No routing needed
- ✅ Instant (no delay)
- ✅ Industry standard

### Even Better: Database Table
- ✅ Works across all workers
- ✅ No routing needed
- ✅ You already have database
- ✅ Simple to implement

## Verdict: Should You Use Sticky Sessions?

### ❌ **No, don't use sticky sessions**

**Reasons:**
1. Uvicorn doesn't support it natively (need Nginx/HAProxy)
2. Creates uneven load distribution
3. Worker crashes break user sessions
4. Doesn't scale well
5. Shared IPs cause problems

### ✅ **Better: Use Shared Storage**

**Options (ranked):**

1. **Redis** (Best)
   - Industry standard
   - Handles any load
   - Sub-millisecond performance

2. **Database Table** (Simplest)
   - Already have database
   - Works immediately
   - Good enough for captchas

3. **Hybrid File Storage** (Current)
   - Works but has 5-second delay
   - Can add file fallback to eliminate delay

## Recommendation

**Don't implement sticky sessions.** Instead:

1. **Short-term**: Add file fallback to current hybrid storage
   - Eliminates 5-second delay
   - Works across all workers
   - No routing complexity

2. **Long-term**: Migrate to Redis
   - Industry standard
   - Best performance
   - Handles any load

Sticky sessions are a workaround, not a solution. Shared storage is the proper fix.



