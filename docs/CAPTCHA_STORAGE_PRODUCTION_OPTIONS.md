# Production Captcha Storage Solutions

## What Big Companies Actually Use

### 1. Redis (Most Common) ⭐⭐⭐⭐⭐

**Used by**: Twitter, GitHub, Stack Overflow, Instagram, Pinterest

**Why it's the industry standard:**
- ✅ **Sub-millisecond latency**: ~0.1-0.5ms (faster than file I/O)
- ✅ **Distributed**: Works across multiple servers/workers
- ✅ **Built-in TTL**: Automatic expiration (perfect for captchas)
- ✅ **High concurrency**: Handles millions of operations/second
- ✅ **Persistent**: Optional persistence to disk
- ✅ **Battle-tested**: Used by every major tech company

**Implementation:**
```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def store_captcha(captcha_id: str, code: str, expires_in: int = 300):
    redis_client.setex(
        f"captcha:{captcha_id}",
        expires_in,
        json.dumps({"code": code})
    )

def verify_captcha(captcha_id: str, user_code: str) -> bool:
    data = redis_client.get(f"captcha:{captcha_id}")
    if not data:
        return False
    
    stored = json.loads(data)
    is_valid = stored["code"].upper() == user_code.upper()
    
    # Delete after verification (one-time use)
    if is_valid:
        redis_client.delete(f"captcha:{captcha_id}")
    
    return is_valid
```

**Performance:**
- Read: ~0.1-0.5ms
- Write: ~0.1-0.5ms
- Concurrency: Millions of ops/sec

**Setup:**
```bash
# Docker (easiest)
docker run -d -p 6379:6379 redis:7-alpine

# Or install locally
# Ubuntu: apt-get install redis-server
# Mac: brew install redis
```

**Cost:**
- Free (self-hosted)
- Cloud: $5-20/month (AWS ElastiCache, Redis Cloud)

---

### 2. Database Table (Simple & Already Available) ⭐⭐⭐⭐

**Used by**: Many companies for simple use cases

**Why it works:**
- ✅ **You already have a database** (SQLite/PostgreSQL)
- ✅ **No new infrastructure** needed
- ✅ **ACID guarantees** (data integrity)
- ✅ **Simple to implement**
- ⚠️ **Slower**: ~1-5ms per operation (but acceptable for captchas)

**Implementation:**
```python
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.sql import func
from models.common import Base

class Captcha(Base):
    __tablename__ = "captchas"
    
    captcha_id = Column(String(36), primary_key=True)
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # Index on expires_at for fast cleanup queries
    __table_args__ = (
        Index('idx_expires_at', 'expires_at'),
    )

# Usage
def store_captcha(captcha_id: str, code: str, expires_in: int = 300):
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    captcha = Captcha(
        captcha_id=captcha_id,
        code=code.upper(),
        expires_at=expires_at
    )
    db.add(captcha)
    db.commit()

def verify_captcha(captcha_id: str, user_code: str, db: Session) -> bool:
    captcha = db.query(Captcha).filter(
        Captcha.captcha_id == captcha_id,
        Captcha.expires_at > datetime.utcnow()
    ).first()
    
    if not captcha:
        return False
    
    is_valid = captcha.code.upper() == user_code.upper()
    
    # Delete after verification
    if is_valid:
        db.delete(captcha)
        db.commit()
    
    return is_valid

# Background cleanup job (run every hour)
def cleanup_expired_captchas(db: Session):
    db.query(Captcha).filter(
        Captcha.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
```

**Performance:**
- Read: ~1-5ms (with index)
- Write: ~1-5ms
- Concurrency: Good (database handles it)

**Pros:**
- ✅ No new dependencies
- ✅ Works immediately
- ✅ Persistent by default
- ✅ Easy to query/debug

**Cons:**
- ⚠️ Slower than Redis (but acceptable for captchas)
- ⚠️ Database load (but captchas are low-frequency)

---

### 3. Memcached (Alternative to Redis) ⭐⭐⭐

**Used by**: Facebook (historically), many large sites

**Similar to Redis but:**
- ✅ Faster for simple key-value (no persistence overhead)
- ❌ No persistence (data lost on restart)
- ❌ Fewer features than Redis

**When to use:** If you need absolute maximum speed and don't care about persistence.

---

### 4. Sticky Sessions (Not Recommended) ⭐

**How it works:** Route same user to same worker

**Implementation:**
```python
# Nginx config
upstream backend {
    ip_hash;  # Route by IP
    server worker1:8000;
    server worker2:8000;
    server worker3:8000;
}
```

**Why NOT recommended:**
- ❌ Load balancing becomes uneven
- ❌ If worker crashes, user loses session
- ❌ Doesn't solve the problem (just avoids it)
- ❌ Not scalable

---

## Comparison Table

| Solution | Speed | Multi-Worker | Setup | Cost | Used By |
|----------|-------|--------------|-------|------|---------|
| **Redis** | ⭐⭐⭐⭐⭐ | ✅ | Medium | Free-$20/mo | Twitter, GitHub |
| **Database** | ⭐⭐⭐ | ✅ | Easy | Free | Many companies |
| **Memcached** | ⭐⭐⭐⭐⭐ | ✅ | Medium | Free | Facebook |
| **File-based** | ⭐⭐ | ✅ | Easy | Free | Small projects |
| **In-memory** | ⭐⭐⭐⭐⭐ | ❌ | Easy | Free | Single worker only |

---

## Recommendation for Your Project

### Option A: Redis (Best for Production) ⭐⭐⭐⭐⭐

**Why:**
- Industry standard
- Fastest solution
- Handles high concurrency
- Built-in TTL (perfect for captchas)

**Setup:**
```bash
# Add to docker-compose.yml (already commented out!)
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  restart: unless-stopped

# Add to requirements.txt
redis>=5.0.0

# Usage
import redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
```

**Implementation time:** 30 minutes

---

### Option B: Database Table (Simplest) ⭐⭐⭐⭐

**Why:**
- You already have a database
- No new infrastructure
- Simple to implement
- Good enough for captchas (low frequency)

**Implementation time:** 15 minutes

---

### Option C: Keep File-Based (Current) ⭐⭐

**Why:**
- Already implemented
- Works for now
- No dependencies

**When to upgrade:**
- When you scale to multiple servers
- When you need better performance
- When you have Redis available

---

## Real-World Examples

### GitHub
- Uses Redis for session storage, captchas, rate limiting
- Handles millions of requests/day
- Redis cluster for high availability

### Stack Overflow
- Redis for caching, sessions, captchas
- Multiple Redis instances for redundancy
- Sub-millisecond response times

### Small Startups
- Many start with database tables
- Upgrade to Redis when scaling
- Database is "good enough" for low traffic

---

## My Recommendation

**For your project right now:**

1. **Short-term**: Use **Database Table** (simplest, already have DB)
2. **Long-term**: Add **Redis** when you scale or need better performance

**Why Database Table first:**
- ✅ Already have SQLite/PostgreSQL
- ✅ No new infrastructure
- ✅ 15 minutes to implement
- ✅ Good enough for captchas (they're low-frequency)

**Why Redis later:**
- ✅ Industry standard
- ✅ Better performance
- ✅ More features (pub/sub, clustering)
- ✅ Easy migration path

---

## Implementation: Database Table (Recommended)

Want me to implement the database table solution? It's:
- Simple (one model, two functions)
- Fast enough (~1-5ms)
- Works across all workers
- No new dependencies



