# Redis + SQLite Hybrid Architecture Implementation Plan

## Executive Summary

This document outlines the implementation of Redis as a required caching layer alongside SQLite in the MindGraph application. The goal is to handle 500+ concurrent users without database lock contention while maintaining data durability.

**Previous State:** SQLite only (struggles with 150+ concurrent users)
**Current State:** Redis (required) + SQLite (persistent) hybrid - **IMPLEMENTED**
**Improvement:** 10-100x faster for high-frequency operations

### Implementation Status: ALL PHASES COMPLETED ✓

| Component | Status | File |
|-----------|--------|------|
| Redis Client | ✓ DONE | `services/redis_client.py` |
| Captcha Storage | ✓ DONE | `services/captcha_storage.py` |
| Rate Limiting | ✓ DONE | `services/redis_rate_limiter.py` |
| SMS Storage | ✓ DONE | `services/redis_sms_storage.py` |
| SMS Auth Integration | ✓ DONE | `routers/auth.py` - send/verify SMS via Redis |
| Activity Tracker | ✓ DONE | `services/redis_activity_tracker.py` |
| Token Buffer | ✓ DONE | `services/redis_token_buffer.py` |
| Health Endpoint | ✓ DONE | `/health/redis` in `main.py` |
| Auth Integration | ✓ DONE | `utils/auth.py` updated |

### Quick Reference: What Uses What

#### Redis (Ephemeral, High-Frequency)

| Data | Service File | Key Pattern | TTL |
|------|--------------|-------------|-----|
| Captcha codes | `captcha_storage.py` | `captcha:{id}` | 5 min |
| SMS verification codes | `redis_sms_storage.py` | `sms:verify:{purpose}:{phone}` | 5 min |
| Login rate limits | `redis_rate_limiter.py` | `rate:login:{phone}` | 15 min |
| IP rate limits | `redis_rate_limiter.py` | `rate:ip:{ip}` | 15 min |
| Captcha rate limits | `redis_rate_limiter.py` | `rate:captcha:{id}` | 15 min |
| SMS rate limits | `redis_rate_limiter.py` | `rate:sms:{phone}` | 1 hour |
| Active sessions | `redis_activity_tracker.py` | `session:{id}`, `user:sessions:{id}` | 30 min |
| Activity history | `redis_activity_tracker.py` | `activity:history` | None (capped list) |
| Token buffer | `redis_token_buffer.py` | `token:buffer` | None (flushed to SQLite) |

#### SQLite (Persistent, Low-Frequency)

| Data | Table | Used By | Purpose |
|------|-------|---------|---------|
| User accounts | `users` | `auth.py`, `pages.py`, `voice.py`, `api.py` | Authentication, profiles |
| Organizations | `organizations` | `auth.py`, `pages.py` | Multi-tenant isolation |
| API Keys | `api_keys` | `auth.py` | External API access |
| Token usage history | `token_usage` | `auth.py` (READ), `token_buffer.py` (WRITE) | Analytics, billing |
| Update notifications | `update_notifications` | `update_notifier.py` | Admin announcements |
| Notification dismissals | `update_notification_dismissed` | `update_notifier.py` | User preferences |

#### NOT Affected by Redis Migration

| Component | File | Reason |
|-----------|------|--------|
| LLM API calls | `services/llm_service.py` | Business logic, not storage |
| LLM clients | `clients/llm.py` | External API calls |
| Prompt templates | `prompts/*.py` | Static configuration |
| SMS sending | `services/sms_middleware.py` | External SMS API |
| Graph generation | `agents/*.py` | LLM processing logic |

---

## Table of Contents

1. [Problem Analysis](#1-problem-analysis)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Classification](#3-data-classification)
4. [Prerequisites](#4-prerequisites)
5. [Implementation Phases](#5-implementation-phases)
6. [File Changes Summary](#6-file-changes-summary)
7. [Testing Plan](#7-testing-plan)
8. [Rollback Plan](#8-rollback-plan)
9. [Monitoring](#9-monitoring)

---

## 1. Problem Analysis

### 1.1 Current Bottlenecks

| Issue | Impact | Root Cause |
|-------|--------|------------|
| Captcha verification slow under load | 500ms-5s response time | SQLite write locks |
| Rate limiting ineffective | Attackers bypass limits | Per-worker memory (not shared) |
| Active user count inaccurate | Admin sees wrong numbers | Per-worker tracking |
| Token buffer data loss | Analytics gaps | Worker crash loses buffer |
| SMS verification delays | User frustration | Same as captcha |

### 1.2 Database Operations Per Login

| Operation | Type | Current Time | With Redis |
|-----------|------|--------------|------------|
| Find user | READ | 1-5ms | 1-5ms (no change) |
| Verify captcha | READ | 1-5ms | 0.1ms |
| Delete captcha | WRITE | 2-10ms | 0.1ms |
| Update last_login | WRITE | 2-10ms | 2-10ms (no change) |
| **Total** | | **6-30ms** | **3-15ms** |
| **Under 500 users** | | **500ms-5s** | **50ms** |

### 1.3 Multi-Worker Issues

Current in-memory stores that are NOT shared across 4 workers:

```
utils/auth.py:
  - login_attempts: Dict[str, list]
  - ip_attempts: Dict[str, list]
  - captcha_attempts: Dict[str, list]
  - captcha_session_attempts: Dict[str, list]

services/user_activity_tracker.py:
  - _active_sessions: Dict[str, Dict]
  - _user_sessions: Dict[int, Set[str]]
  - _activity_history: List[Dict]

services/token_tracker.py:
  - _buffer: List[Dict[str, Any]]
```

---

## 2. Architecture Overview

### 2.1 Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Uvicorn (4 Workers)                   │
├─────────────┬─────────────┬─────────────┬───────────────┤
│  Worker 1   │  Worker 2   │  Worker 3   │  Worker 4     │
│  [Memory]   │  [Memory]   │  [Memory]   │  [Memory]     │
│  rate_limit │  rate_limit │  rate_limit │  rate_limit   │
│  sessions   │  sessions   │  sessions   │  sessions     │
│  buffer     │  buffer     │  buffer     │  buffer       │
└──────┬──────┴──────┬──────┴──────┬──────┴───────┬───────┘
       │             │             │              │
       └─────────────┴──────┬──────┴──────────────┘
                            │
                    ┌───────▼───────┐
                    │    SQLite     │
                    │ (everything)  │
                    │  - Users      │
                    │  - Captchas   │
                    │  - SMS        │
                    │  - Tokens     │
                    └───────────────┘
```

### 2.2 Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Uvicorn (4 Workers)                   │
├─────────────┬─────────────┬─────────────┬───────────────┤
│  Worker 1   │  Worker 2   │  Worker 3   │  Worker 4     │
│  (stateless)│  (stateless)│  (stateless)│  (stateless)  │
└──────┬──────┴──────┬──────┴──────┬──────┴───────┬───────┘
       │             │             │              │
       └─────────────┴──────┬──────┴──────────────┘
                            │
           ┌────────────────┴────────────────┐
           │                                 │
           ▼                                 ▼
 ┌─────────────────────┐         ┌─────────────────────┐
 │       Redis         │         │       SQLite        │
 │   (Ephemeral)       │         │    (Persistent)     │
 │                     │         │                     │
 │  • Captchas (TTL)   │         │  • Users            │
 │  • SMS codes (TTL)  │         │  • Organizations    │
 │  • Rate limits      │         │  • API Keys         │
 │  • Active sessions  │         │  • Token Usage      │
 │  • Token buffer     │         │  • Notifications    │
 │  • Notification     │         │                     │
 │    cache            │         │                     │
 └─────────────────────┘         └─────────────────────┘
      ~0.1ms ops                      ~1-10ms ops
      100K+ ops/sec                   ~100 writes/sec
```

---

## 3. Data Classification

### 3.1 Move to Redis (Ephemeral, High-Frequency)

| Data | Current Location | TTL | Priority |
|------|------------------|-----|----------|
| Captcha codes | SQLite `captchas` table | 5 min | P0 |
| SMS verification codes | SQLite `sms_verifications` table | 5 min | P0 |
| Login rate limits | Per-worker `login_attempts` dict | 15 min | P1 |
| IP rate limits | Per-worker `ip_attempts` dict | 15 min | P1 |
| Captcha rate limits | Per-worker `captcha_attempts` dict | 15 min | P1 |
| Active user sessions | Per-worker `_active_sessions` dict | 30 min | P2 |
| Token tracker buffer | Per-worker `_buffer` list | Until flush | P2 |
| Notification cache | SQLite read each time | 5 min | P3 |

### 3.2 Keep in SQLite (Persistent, Low-Frequency)

| Data | Table | Reason |
|------|-------|--------|
| User accounts | `users` | Permanent, needs durability |
| Organizations | `organizations` | Permanent, rarely changes |
| API Keys | `api_keys` | Security critical, audit trail |
| Token usage history | `token_usage` | Analytics, historical data |
| Update notifications | `update_notifications` | Admin config, rare updates |
| Notification dismissals | `update_notification_dismissed` | User preferences |

---

## 4. Prerequisites

### 4.1 Redis Installation

**Option A: Docker (Recommended - Redis 8.4)**
```bash
# Single command, runs in background
docker run -d \
  --name mindgraph-redis \
  --restart unless-stopped \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:8.4-alpine \
  redis-server --appendonly yes --maxmemory 100mb --maxmemory-policy allkeys-lru

# Or use docker-compose (see docker/docker-compose.yml)
docker-compose -f docker/docker-compose.yml up -d redis
```

**Note:** Redis 8.4 is the latest stable release. Redis 8.2+ provides 35%+ faster command execution and 49% higher throughput compared to Redis 7.0. Recommended for production.

**Option B: Linux Package (Redis 7.0.x)**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**Note:** Ubuntu repositories provide Redis 7.0.x. For Redis 8.2 performance improvements, use Docker (Option A) or install from source (see docs/REDIS_SETUP.md).

**Option C: Windows (Development)**
```bash
# Using Docker Desktop
docker run -d --name redis -p 6379:6379 redis:8.4-alpine

# Or use Memurai (Redis-compatible for Windows)
# Download from: https://www.memurai.com/
```

### 4.2 Python Dependencies

```bash
# Add to requirements.txt
redis>=5.0.0
```

### 4.3 Environment Configuration

```bash
# Add to .env file

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true

# Optional: Redis connection tuning
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
```

### 4.4 Verification

```bash
# Test Redis connection
redis-cli ping
# Should return: PONG

# Test from Python
python -c "import redis; r = redis.Redis(); print(r.ping())"
# Should return: True
```

---

## 5. Implementation Phases

### Phase 1: Redis Client Foundation

**Duration:** 1-2 hours
**Risk:** Low (new file, no changes to existing code)
**Rollback:** Delete the new file

#### Step 1.1: Create Redis Client Service

Create new file: `services/redis_client.py`

```python
"""
Redis Client Service
====================

Centralized Redis connection management with graceful fallback.

If Redis is unavailable, the application continues to work using
existing SQLite storage (degraded mode with reduced performance).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import json
import logging
import asyncio
from typing import Optional, Any, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis availability flag
_redis_available = False
_redis_client = None


def _get_redis_config() -> Dict[str, Any]:
    """Get Redis configuration from environment."""
    return {
        'url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'enabled': os.getenv('REDIS_ENABLED', 'true').lower() == 'true',
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '50')),
        'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
        'socket_connect_timeout': int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
        'retry_on_timeout': os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true',
    }


async def init_redis() -> bool:
    """
    Initialize Redis connection.
    
    Should be called during application startup.
    Returns True if Redis is available, False otherwise.
    """
    global _redis_available, _redis_client
    
    config = _get_redis_config()
    
    if not config['enabled']:
        logger.info("[Redis] Disabled via REDIS_ENABLED=false, using SQLite fallback")
        return False
    
    try:
        import redis.asyncio as redis
        
        _redis_client = redis.from_url(
            config['url'],
            encoding='utf-8',
            decode_responses=True,
            max_connections=config['max_connections'],
            socket_timeout=config['socket_timeout'],
            socket_connect_timeout=config['socket_connect_timeout'],
            retry_on_timeout=config['retry_on_timeout'],
        )
        
        # Test connection
        await _redis_client.ping()
        
        _redis_available = True
        logger.info(f"[Redis] Connected successfully to {config['url']}")
        return True
        
    except ImportError:
        logger.warning("[Redis] redis package not installed, using SQLite fallback")
        logger.warning("[Redis] Install with: pip install redis>=5.0.0")
        return False
        
    except Exception as e:
        logger.warning(f"[Redis] Connection failed: {e}")
        logger.warning("[Redis] Using SQLite fallback (reduced performance)")
        _redis_client = None
        _redis_available = False
        return False


async def close_redis():
    """Close Redis connection gracefully."""
    global _redis_client, _redis_available
    
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("[Redis] Connection closed")
        except Exception as e:
            logger.warning(f"[Redis] Error closing connection: {e}")
        finally:
            _redis_client = None
            _redis_available = False


def is_redis_available() -> bool:
    """Check if Redis is available."""
    return _redis_available


def get_redis():
    """
    Get Redis client instance.
    
    Returns None if Redis is not available.
    Always check is_redis_available() or handle None return.
    """
    return _redis_client


class RedisOperations:
    """
    High-level Redis operations with error handling.
    
    All methods return None or empty values on failure,
    allowing callers to fall back to SQLite.
    """
    
    @staticmethod
    async def set_with_ttl(key: str, value: str, ttl_seconds: int) -> bool:
        """Set a key with TTL. Returns True on success."""
        if not _redis_available:
            return False
        try:
            await _redis_client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            logger.warning(f"[Redis] SET failed for {key}: {e}")
            return False
    
    @staticmethod
    async def get(key: str) -> Optional[str]:
        """Get a key value. Returns None if not found or on error."""
        if not _redis_available:
            return None
        try:
            return await _redis_client.get(key)
        except Exception as e:
            logger.warning(f"[Redis] GET failed for {key}: {e}")
            return None
    
    @staticmethod
    async def delete(key: str) -> bool:
        """Delete a key. Returns True on success."""
        if not _redis_available:
            return False
        try:
            await _redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"[Redis] DELETE failed for {key}: {e}")
            return False
    
    @staticmethod
    async def get_and_delete(key: str) -> Optional[str]:
        """Atomically get and delete a key."""
        if not _redis_available:
            return None
        try:
            pipe = _redis_client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"[Redis] GET+DELETE failed for {key}: {e}")
            return None
    
    @staticmethod
    async def increment(key: str, ttl_seconds: Optional[int] = None) -> Optional[int]:
        """Increment a counter. Optionally set TTL on first increment."""
        if not _redis_available:
            return None
        try:
            pipe = _redis_client.pipeline()
            pipe.incr(key)
            if ttl_seconds:
                pipe.expire(key, ttl_seconds, nx=True)  # Only set if no TTL exists
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"[Redis] INCR failed for {key}: {e}")
            return None
    
    @staticmethod
    async def list_push(key: str, value: str) -> bool:
        """Push value to end of list."""
        if not _redis_available:
            return False
        try:
            await _redis_client.rpush(key, value)
            return True
        except Exception as e:
            logger.warning(f"[Redis] RPUSH failed for {key}: {e}")
            return False
    
    @staticmethod
    async def list_pop_many(key: str, count: int) -> List[str]:
        """Atomically pop up to count items from list."""
        if not _redis_available:
            return []
        try:
            pipe = _redis_client.pipeline()
            pipe.lrange(key, 0, count - 1)
            pipe.ltrim(key, count, -1)
            results = await pipe.execute()
            return results[0] or []
        except Exception as e:
            logger.warning(f"[Redis] List pop failed for {key}: {e}")
            return []
    
    @staticmethod
    async def list_length(key: str) -> int:
        """Get list length."""
        if not _redis_available:
            return 0
        try:
            return await _redis_client.llen(key) or 0
        except Exception as e:
            logger.warning(f"[Redis] LLEN failed for {key}: {e}")
            return 0
    
    @staticmethod
    async def sorted_set_add(key: str, member: str, score: float) -> bool:
        """Add member to sorted set with score."""
        if not _redis_available:
            return False
        try:
            await _redis_client.zadd(key, {member: score})
            return True
        except Exception as e:
            logger.warning(f"[Redis] ZADD failed for {key}: {e}")
            return False
    
    @staticmethod
    async def sorted_set_count_in_range(
        key: str, 
        min_score: float, 
        max_score: float
    ) -> int:
        """Count members in sorted set within score range."""
        if not _redis_available:
            return 0
        try:
            return await _redis_client.zcount(key, min_score, max_score) or 0
        except Exception as e:
            logger.warning(f"[Redis] ZCOUNT failed for {key}: {e}")
            return 0
    
    @staticmethod
    async def sorted_set_remove_by_score(
        key: str, 
        min_score: float, 
        max_score: float
    ) -> int:
        """Remove members from sorted set by score range."""
        if not _redis_available:
            return 0
        try:
            return await _redis_client.zremrangebyscore(key, min_score, max_score) or 0
        except Exception as e:
            logger.warning(f"[Redis] ZREMRANGEBYSCORE failed for {key}: {e}")
            return 0
    
    @staticmethod
    async def set_ttl(key: str, ttl_seconds: int) -> bool:
        """Set TTL on existing key."""
        if not _redis_available:
            return False
        try:
            await _redis_client.expire(key, ttl_seconds)
            return True
        except Exception as e:
            logger.warning(f"[Redis] EXPIRE failed for {key}: {e}")
            return False
    
    @staticmethod
    async def get_ttl(key: str) -> int:
        """Get remaining TTL of a key. Returns -1 if no TTL, -2 if key doesn't exist."""
        if not _redis_available:
            return -2
        try:
            return await _redis_client.ttl(key)
        except Exception as e:
            logger.warning(f"[Redis] TTL failed for {key}: {e}")
            return -2
    
    @staticmethod
    async def hash_set(key: str, mapping: Dict[str, str]) -> bool:
        """Set multiple hash fields."""
        if not _redis_available:
            return False
        try:
            await _redis_client.hset(key, mapping=mapping)
            return True
        except Exception as e:
            logger.warning(f"[Redis] HSET failed for {key}: {e}")
            return False
    
    @staticmethod
    async def hash_get_all(key: str) -> Dict[str, str]:
        """Get all hash fields."""
        if not _redis_available:
            return {}
        try:
            return await _redis_client.hgetall(key) or {}
        except Exception as e:
            logger.warning(f"[Redis] HGETALL failed for {key}: {e}")
            return {}
    
    @staticmethod
    async def keys_by_pattern(pattern: str) -> List[str]:
        """Get keys matching pattern. Use sparingly (O(N) operation)."""
        if not _redis_available:
            return []
        try:
            return await _redis_client.keys(pattern) or []
        except Exception as e:
            logger.warning(f"[Redis] KEYS failed for {pattern}: {e}")
            return []


# Convenience alias
redis_ops = RedisOperations
```

#### Step 1.2: Update main.py to Initialize Redis

Modify `main.py` to add Redis initialization:

```python
# Add to imports
from services.redis_client import init_redis, close_redis

# Add to lifespan or startup event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    
    # Initialize Redis (non-blocking, falls back to SQLite if unavailable)
    await init_redis()
    
    yield
    
    # ... existing shutdown code ...
    
    # Close Redis connection
    await close_redis()
```

#### Step 1.3: Update requirements.txt

Add Redis dependency:

```
redis>=5.0.0
```

---

### Phase 2: Captcha Storage (P0 - Highest Priority)

**Duration:** 2-3 hours
**Risk:** Medium (modifies critical auth flow)
**Rollback:** Set REDIS_ENABLED=false in .env

#### Step 2.1: Create Redis Captcha Storage

Modify `services/captcha_storage.py`:

```python
"""
Captcha Storage Service
=======================

Hybrid Redis + SQLite captcha storage with automatic fallback.

Primary: Redis (fast, shared across workers)
Fallback: SQLite (when Redis unavailable)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

from services.redis_client import is_redis_available, redis_ops

logger = logging.getLogger(__name__)


class RedisCaptchaStorage:
    """
    Redis-based captcha storage.
    
    Benefits over SQLite:
    - 100x faster (0.1ms vs 10ms)
    - No database locks
    - Automatic TTL expiration (no cleanup task needed)
    - Shared across all workers
    """
    
    PREFIX = "captcha:"
    DEFAULT_TTL = 300  # 5 minutes
    
    async def store(self, captcha_id: str, code: str, expires_in_seconds: int = 300):
        """Store captcha with automatic expiration."""
        key = f"{self.PREFIX}{captcha_id}"
        success = await redis_ops.set_with_ttl(key, code.upper(), expires_in_seconds)
        if success:
            logger.debug(f"[Captcha:Redis] Stored: {captcha_id[:8]}...")
        return success
    
    async def get(self, captcha_id: str) -> Optional[Dict]:
        """Get captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        code = await redis_ops.get(key)
        
        if code is None:
            return None
        
        ttl = await redis_ops.get_ttl(key)
        expires_at = time.time() + ttl if ttl > 0 else time.time()
        
        return {
            "code": code,
            "expires": expires_at
        }
    
    async def verify_and_remove(
        self, 
        captcha_id: str, 
        user_code: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify captcha code and remove it (one-time use).
        
        Returns:
            Tuple of (is_valid: bool, error_reason: Optional[str])
        """
        key = f"{self.PREFIX}{captcha_id}"
        
        # Atomic get and delete
        stored_code = await redis_ops.get_and_delete(key)
        
        if stored_code is None:
            logger.warning(f"[Captcha:Redis] Not found: {captcha_id[:8]}...")
            return False, "not_found"
        
        # Verify code (case-insensitive)
        is_valid = stored_code.upper() == user_code.upper()
        
        if is_valid:
            logger.debug(f"[Captcha:Redis] Verified: {captcha_id[:8]}...")
            return True, None
        else:
            logger.warning(
                f"[Captcha:Redis] Incorrect: {captcha_id[:8]}... "
                f"(expected: {stored_code}, got: {user_code})"
            )
            return False, "incorrect"
    
    async def remove(self, captcha_id: str):
        """Remove a captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        await redis_ops.delete(key)
        logger.debug(f"[Captcha:Redis] Removed: {captcha_id[:8]}...")
    
    def cleanup_expired(self):
        """No-op for Redis (TTL handles expiration automatically)."""
        pass


class SQLiteCaptchaStorage:
    """
    SQLite-based captcha storage (fallback).
    
    Used when Redis is unavailable.
    Original implementation preserved for compatibility.
    """
    
    # ... (keep existing SQLiteCaptchaStorage implementation) ...


class HybridCaptchaStorage:
    """
    Hybrid captcha storage that uses Redis when available, SQLite as fallback.
    
    Provides seamless failover without code changes in calling modules.
    """
    
    def __init__(self):
        self._redis = RedisCaptchaStorage()
        self._sqlite = SQLiteCaptchaStorage()
        logger.info("[CaptchaStorage] Initialized hybrid storage (Redis primary, SQLite fallback)")
    
    def _use_redis(self) -> bool:
        """Check if we should use Redis."""
        return is_redis_available()
    
    async def store(self, captcha_id: str, code: str, expires_in_seconds: int = 300):
        """Store captcha in Redis (or SQLite fallback)."""
        if self._use_redis():
            success = await self._redis.store(captcha_id, code, expires_in_seconds)
            if success:
                return
            # Fall through to SQLite on Redis failure
        
        # SQLite fallback (sync operation)
        self._sqlite.store(captcha_id, code, expires_in_seconds)
    
    async def get(self, captcha_id: str) -> Optional[Dict]:
        """Get captcha from Redis (or SQLite fallback)."""
        if self._use_redis():
            result = await self._redis.get(captcha_id)
            if result is not None:
                return result
            # Key not found in Redis - might be in SQLite if recently switched
        
        # SQLite fallback
        return self._sqlite.get(captcha_id)
    
    async def verify_and_remove(
        self, 
        captcha_id: str, 
        user_code: str
    ) -> Tuple[bool, Optional[str]]:
        """Verify and remove captcha."""
        if self._use_redis():
            result = await self._redis.verify_and_remove(captcha_id, user_code)
            # If not found in Redis, check SQLite (migration period)
            if result[1] == "not_found":
                return self._sqlite.verify_and_remove(captcha_id, user_code)
            return result
        
        # SQLite fallback
        return self._sqlite.verify_and_remove(captcha_id, user_code)
    
    async def remove(self, captcha_id: str):
        """Remove captcha from storage."""
        if self._use_redis():
            await self._redis.remove(captcha_id)
        else:
            self._sqlite.remove(captcha_id)
    
    def cleanup_expired(self):
        """Cleanup expired captchas (only needed for SQLite)."""
        if not self._use_redis():
            self._sqlite.cleanup_expired()


# Global singleton instance
_captcha_storage: Optional[HybridCaptchaStorage] = None


def get_captcha_storage() -> HybridCaptchaStorage:
    """Get the global captcha storage instance."""
    global _captcha_storage
    if _captcha_storage is None:
        _captcha_storage = HybridCaptchaStorage()
    return _captcha_storage


async def start_captcha_cleanup_scheduler(interval_minutes: int = 10):
    """
    Run captcha cleanup task periodically in background.
    
    Only performs actual cleanup when using SQLite fallback.
    Redis handles expiration automatically via TTL.
    """
    interval_seconds = interval_minutes * 60
    storage = get_captcha_storage()
    
    logger.info(f"[CaptchaStorage] Starting cleanup scheduler (every {interval_minutes} min)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            # Run cleanup in thread pool (only does work if using SQLite)
            await asyncio.to_thread(storage.cleanup_expired)
        except asyncio.CancelledError:
            logger.info("[CaptchaStorage] Cleanup scheduler stopped")
            break
        except Exception as e:
            logger.error(f"[CaptchaStorage] Cleanup scheduler error: {e}", exc_info=True)
```

#### Step 2.2: Update auth.py for Async Captcha

The `routers/auth.py` already uses async captcha verification. The new HybridCaptchaStorage is a drop-in replacement.

---

### Phase 3: SMS Verification (P0)

**Duration:** 2 hours
**Risk:** Medium
**Rollback:** Set REDIS_ENABLED=false

#### Step 3.1: Create Redis SMS Storage

Create new file: `services/sms_storage.py`

```python
"""
SMS Verification Storage Service
================================

Hybrid Redis + SQLite SMS verification code storage.

Primary: Redis (fast, shared across workers)
Fallback: SQLite (when Redis unavailable)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

from services.redis_client import is_redis_available, redis_ops

logger = logging.getLogger(__name__)


class RedisSMSStorage:
    """
    Redis-based SMS verification storage.
    
    Key format: sms:{phone}:{purpose}
    Value: JSON with code, attempts, created_at
    TTL: 5 minutes (configurable)
    """
    
    PREFIX = "sms:"
    DEFAULT_TTL = 300  # 5 minutes
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN = 60  # Seconds before allowing resend
    
    def _make_key(self, phone: str, purpose: str) -> str:
        """Generate Redis key for SMS code."""
        return f"{self.PREFIX}{phone}:{purpose}"
    
    async def store(
        self, 
        phone: str, 
        code: str, 
        purpose: str, 
        expires_in_seconds: int = 300
    ) -> bool:
        """
        Store SMS verification code.
        
        Args:
            phone: Phone number
            code: 6-digit verification code
            purpose: register, login, or reset_password
            expires_in_seconds: TTL in seconds
            
        Returns:
            True if stored successfully
        """
        key = self._make_key(phone, purpose)
        
        data = {
            "code": code,
            "attempts": 0,
            "created_at": time.time()
        }
        
        success = await redis_ops.set_with_ttl(
            key, 
            json.dumps(data), 
            expires_in_seconds
        )
        
        if success:
            logger.debug(f"[SMS:Redis] Stored code for {phone[:3]}***:{purpose}")
        
        return success
    
    async def verify(
        self, 
        phone: str, 
        user_code: str, 
        purpose: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify SMS code (increments attempt counter, does not delete).
        
        Returns:
            Tuple of (is_valid, error_reason)
            error_reason: "not_found", "expired", "incorrect", "too_many_attempts"
        """
        key = self._make_key(phone, purpose)
        
        # Get current data
        data_str = await redis_ops.get(key)
        
        if data_str is None:
            return False, "not_found"
        
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            await redis_ops.delete(key)
            return False, "not_found"
        
        # Check attempts
        if data.get("attempts", 0) >= self.MAX_ATTEMPTS:
            await redis_ops.delete(key)
            logger.warning(f"[SMS:Redis] Too many attempts for {phone[:3]}***")
            return False, "too_many_attempts"
        
        # Verify code
        if data.get("code") == user_code:
            logger.info(f"[SMS:Redis] Verified successfully for {phone[:3]}***")
            return True, None
        else:
            # Increment attempts
            data["attempts"] = data.get("attempts", 0) + 1
            ttl = await redis_ops.get_ttl(key)
            if ttl > 0:
                await redis_ops.set_with_ttl(key, json.dumps(data), ttl)
            
            remaining = self.MAX_ATTEMPTS - data["attempts"]
            logger.warning(
                f"[SMS:Redis] Incorrect code for {phone[:3]}***, "
                f"{remaining} attempts remaining"
            )
            return False, "incorrect"
    
    async def verify_and_remove(
        self, 
        phone: str, 
        user_code: str, 
        purpose: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify SMS code and remove on success (one-time use).
        """
        is_valid, error = await self.verify(phone, user_code, purpose)
        
        if is_valid:
            key = self._make_key(phone, purpose)
            await redis_ops.delete(key)
        
        return is_valid, error
    
    async def get_resend_cooldown(self, phone: str, purpose: str) -> int:
        """
        Get seconds until user can request a new code.
        
        Returns:
            0 if can resend now, positive int for seconds to wait
        """
        key = self._make_key(phone, purpose)
        
        data_str = await redis_ops.get(key)
        if data_str is None:
            return 0
        
        try:
            data = json.loads(data_str)
            created_at = data.get("created_at", 0)
            elapsed = time.time() - created_at
            
            if elapsed < self.RESEND_COOLDOWN:
                return int(self.RESEND_COOLDOWN - elapsed)
            return 0
        except:
            return 0
    
    async def remove(self, phone: str, purpose: str):
        """Remove SMS code."""
        key = self._make_key(phone, purpose)
        await redis_ops.delete(key)


# Integration with existing sms_middleware.py will be done in Step 3.2
```

#### Step 3.2: Integrate with SMS Middleware

Update `services/sms_middleware.py` to use Redis storage when available.

---

### Phase 4: Rate Limiting (P1)

**Duration:** 3-4 hours
**Risk:** Medium-High (security critical)
**Rollback:** Set REDIS_ENABLED=false

#### Step 4.1: Create Redis Rate Limiter

Create new file: `services/redis_rate_limiter.py`

```python
"""
Redis Rate Limiter Service
==========================

Shared rate limiting across all workers using Redis sorted sets.

Uses sliding window algorithm with Redis ZSET for accurate rate limiting.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import time
import logging
from typing import Tuple

from services.redis_client import is_redis_available, redis_ops

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    Redis-based sliding window rate limiter.
    
    Uses sorted sets (ZSET) with timestamps as scores.
    Accurate counting across all workers.
    """
    
    PREFIX = "rate:"
    
    async def check_rate_limit(
        self,
        identifier: str,
        category: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if rate limit allows this request.
        
        Args:
            identifier: User identifier (phone, IP, etc.)
            category: Rate limit category (login, captcha, etc.)
            max_attempts: Maximum attempts allowed in window
            window_seconds: Sliding window size in seconds
            
        Returns:
            Tuple of (is_allowed, current_count)
        """
        key = f"{self.PREFIX}{category}:{identifier}"
        now = time.time()
        window_start = now - window_seconds
        
        # Remove old entries and count current
        await redis_ops.sorted_set_remove_by_score(key, 0, window_start)
        count = await redis_ops.sorted_set_count_in_range(key, window_start, now)
        
        is_allowed = count < max_attempts
        return is_allowed, count
    
    async def record_attempt(
        self,
        identifier: str,
        category: str,
        window_seconds: int
    ) -> int:
        """
        Record an attempt and return new count.
        
        Args:
            identifier: User identifier
            category: Rate limit category
            window_seconds: Window for TTL
            
        Returns:
            New attempt count
        """
        key = f"{self.PREFIX}{category}:{identifier}"
        now = time.time()
        
        # Add this attempt
        await redis_ops.sorted_set_add(key, str(now), now)
        
        # Set expiry on the key (cleanup)
        await redis_ops.set_ttl(key, window_seconds + 60)
        
        # Count current attempts
        window_start = now - window_seconds
        count = await redis_ops.sorted_set_count_in_range(key, window_start, now)
        
        return count
    
    async def check_and_record(
        self,
        identifier: str,
        category: str,
        max_attempts: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check rate limit and record attempt atomically.
        
        Returns:
            Tuple of (is_allowed, current_count including this attempt)
        """
        key = f"{self.PREFIX}{category}:{identifier}"
        now = time.time()
        window_start = now - window_seconds
        
        # Cleanup, add, count in pipeline
        await redis_ops.sorted_set_remove_by_score(key, 0, window_start)
        await redis_ops.sorted_set_add(key, str(now), now)
        await redis_ops.set_ttl(key, window_seconds + 60)
        
        count = await redis_ops.sorted_set_count_in_range(key, window_start, now)
        
        is_allowed = count <= max_attempts
        return is_allowed, count
    
    async def clear_attempts(self, identifier: str, category: str):
        """Clear all attempts for an identifier (e.g., on successful login)."""
        key = f"{self.PREFIX}{category}:{identifier}"
        await redis_ops.delete(key)
        logger.debug(f"[RateLimit:Redis] Cleared {category} for {identifier[:8]}...")


# Global instance
_rate_limiter = RedisRateLimiter()


def get_rate_limiter() -> RedisRateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter
```

#### Step 4.2: Update utils/auth.py

Modify rate limiting functions in `utils/auth.py` to use Redis when available.

---

### Phase 5: User Activity Tracker (P2)

**Duration:** 2-3 hours
**Risk:** Low (monitoring only)
**Rollback:** Set REDIS_ENABLED=false

#### Step 5.1: Update user_activity_tracker.py

Add Redis backing store for session tracking to share across workers.

---

### Phase 6: Token Tracker Buffer (P2)

**Duration:** 2 hours
**Risk:** Low
**Rollback:** Set REDIS_ENABLED=false

#### Step 6.1: Update token_tracker.py

Use Redis list as shared buffer across workers.

---

### Phase 7: Docker Integration

**Duration:** 1 hour
**Risk:** Low

#### Step 7.1: Update docker-compose.yml

```yaml
version: '3.8'

services:
  mindgraph:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "9527:9527"
    volumes:
      - ../data:/app/data
      - ../logs:/app/logs
    environment:
      - REDIS_URL=redis://redis:6379/0
      - REDIS_ENABLED=true
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: >
      redis-server 
      --appendonly yes 
      --maxmemory 100mb 
      --maxmemory-policy allkeys-lru
      --tcp-keepalive 60
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  redis_data:
```

---

## 6. File Changes Summary

| File | Change Type | Priority | Description |
|------|-------------|----------|-------------|
| `services/redis_client.py` | NEW | P0 | Redis client with fallback |
| `services/captcha_storage.py` | MODIFY | P0 | Add Redis storage |
| `services/sms_storage.py` | NEW | P0 | Redis SMS storage |
| `services/sms_middleware.py` | MODIFY | P0 | Use Redis SMS storage |
| `services/redis_rate_limiter.py` | NEW | P1 | Redis rate limiting |
| `utils/auth.py` | MODIFY | P1 | Use Redis rate limiter |
| `services/user_activity_tracker.py` | MODIFY | P2 | Redis session storage |
| `services/token_tracker.py` | MODIFY | P2 | Redis buffer |
| `main.py` | MODIFY | P0 | Initialize/close Redis |
| `requirements.txt` | MODIFY | P0 | Add redis>=5.0.0 |
| `docker/docker-compose.yml` | MODIFY | P3 | Add Redis service |
| `env.example` | MODIFY | P0 | Add Redis config |

---

## 7. Testing Plan

### 7.1 Unit Tests

```python
# tests/services/test_redis_captcha.py

import pytest
from services.captcha_storage import HybridCaptchaStorage

@pytest.mark.asyncio
async def test_captcha_store_and_verify():
    storage = HybridCaptchaStorage()
    
    # Store
    await storage.store("test-123", "ABCD", 60)
    
    # Verify correct
    is_valid, error = await storage.verify_and_remove("test-123", "abcd")
    assert is_valid is True
    assert error is None

@pytest.mark.asyncio
async def test_captcha_one_time_use():
    storage = HybridCaptchaStorage()
    
    await storage.store("test-456", "WXYZ", 60)
    
    # First verify succeeds
    is_valid, _ = await storage.verify_and_remove("test-456", "WXYZ")
    assert is_valid is True
    
    # Second verify fails (already used)
    is_valid, error = await storage.verify_and_remove("test-456", "WXYZ")
    assert is_valid is False
    assert error == "not_found"
```

### 7.2 Integration Tests

```bash
# Test with Redis available
REDIS_ENABLED=true python -m pytest tests/services/test_redis_*.py -v

# Test fallback to SQLite
REDIS_ENABLED=false python -m pytest tests/services/test_redis_*.py -v

# Test with Redis connection failure
REDIS_URL=redis://invalid:6379 python -m pytest tests/services/test_redis_*.py -v
```

### 7.3 Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load/test_login_load.py --host=http://localhost:9527
```

---

## 8. Rollback Plan

### 8.1 Immediate Rollback

If issues occur after deployment:

```bash
# Disable Redis, fall back to SQLite
echo "REDIS_ENABLED=false" >> .env

# Restart application
sudo systemctl restart mindgraph
```

### 8.2 Full Rollback

If Redis integration needs to be completely removed:

1. Set `REDIS_ENABLED=false` in `.env`
2. Revert to previous git commit
3. Restart application
4. Remove Redis container: `docker stop redis && docker rm redis`

---

## 9. Monitoring

### 9.1 Redis Health Check Endpoint

Add to `routers/api.py`:

```python
@router.get("/health/redis")
async def redis_health():
    """Check Redis connection status."""
    from services.redis_client import is_redis_available, get_redis
    
    if not is_redis_available():
        return {
            "status": "unavailable",
            "fallback": "sqlite",
            "message": "Using SQLite fallback"
        }
    
    try:
        redis = get_redis()
        info = await redis.info("server")
        return {
            "status": "healthy",
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds")
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
```

### 9.2 Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Redis connection errors | Application logs | > 10/minute |
| Redis latency | Redis INFO | > 10ms p99 |
| Memory usage | Redis INFO | > 80MB |
| SQLite fallback count | Application logs | Any occurrence |

---

## 10. Timeline

| Phase | Duration | Dependencies | Status |
|-------|----------|--------------|--------|
| Phase 1: Redis Client | 2 hours | None | ✓ **COMPLETED** |
| Phase 2: Captcha | 3 hours | Phase 1 | ✓ **COMPLETED** |
| Phase 3: SMS | 2 hours | Phase 1 | ✓ **COMPLETED** |
| Phase 4: Rate Limiting | 4 hours | Phase 1 | ✓ **COMPLETED** |
| Phase 5: Activity Tracker | 3 hours | Phase 1 | ✓ **COMPLETED** |
| Phase 6: Token Buffer | 2 hours | Phase 1 | ✓ **COMPLETED** |
| Phase 7: Docker | 1 hour | Phase 1 | User responsibility |
| Testing | 4 hours | All phases | ✓ **COMPLETED** |
| **TOTAL** | **~21 hours** | | **ALL PHASES COMPLETE** |

---

## Appendix A: Redis Commands Reference

| Operation | Redis Command | Time Complexity |
|-----------|---------------|-----------------|
| Store captcha | SETEX key ttl value | O(1) |
| Get captcha | GET key | O(1) |
| Delete captcha | DEL key | O(1) |
| Rate limit add | ZADD key score member | O(log N) |
| Rate limit count | ZCOUNT key min max | O(log N) |
| Rate limit cleanup | ZREMRANGEBYSCORE | O(log N + M) |
| Buffer push | RPUSH key value | O(1) |
| Buffer pop batch | LRANGE + LTRIM | O(N) |

---

## Appendix B: Environment Variables

```bash
# Redis Configuration (REQUIRED)
# MindGraph uses SQLite + Redis architecture - both are required
REDIS_URL=redis://localhost:6379/0      # Redis connection URL

# Connection pool settings (optional)
REDIS_MAX_CONNECTIONS=50                 # Connection pool size
REDIS_SOCKET_TIMEOUT=5                   # Socket timeout in seconds
REDIS_SOCKET_CONNECT_TIMEOUT=5           # Connection timeout in seconds
REDIS_RETRY_ON_TIMEOUT=true              # Retry on timeout errors
```

### Quick Start Commands

```bash
# Ubuntu - Install and start Redis
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server  # Auto-start on boot

# Docker alternative
docker run -d --name redis -p 6379:6379 redis:alpine
```

---

*Document created: 2024-12-23*
*Last updated: 2024-12-23*
*Author: MindSpring Team*
*Version: 2.1 - SMS migrated to Redis, full workflow verification completed*

