"""
Redis Client Service
====================

Centralized Redis connection management for MindGraph.

Redis is REQUIRED. MindGraph uses SQLite + Redis architecture:
- SQLite: Persistent data (users, organizations, token history)
- Redis: Ephemeral data (captcha, rate limiting, sessions, buffers)

Configuration via environment variables:
- REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)

If Redis connection fails, the application will NOT start.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import logging
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

# Global state
_redis_available = False
_redis_client = None

# Error message width
_ERROR_WIDTH = 70


def _log_redis_error(title: str, details: List[str]) -> None:
    """
    Log a Redis error with clean, professional formatting.
    
    Args:
        title: Error title (e.g., "REDIS CONNECTION FAILED")
        details: List of detail lines to display
    """
    separator = "=" * _ERROR_WIDTH
    
    lines = [
        "",
        separator,
        title.center(_ERROR_WIDTH),
        separator,
        "",
    ]
    lines.extend(details)
    lines.extend(["", separator, ""])
    
    error_msg = "\n".join(lines)
    logger.critical(error_msg)


class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""
    pass


def _get_redis_config() -> Dict[str, Any]:
    """Get Redis configuration from environment."""
    return {
        'url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '50')),
        'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
        'socket_connect_timeout': int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
        'retry_on_timeout': os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true',
    }


def init_redis_sync() -> bool:
    """
    Initialize Redis connection (synchronous version for startup).
    
    Redis is REQUIRED. Application will exit if connection fails.
    
    Returns:
        True if Redis is available.
    
    Raises:
        SystemExit: Application will exit if Redis is unavailable.
    """
    global _redis_available, _redis_client
    
    config = _get_redis_config()
    redis_url = config['url']
    
    logger.info(f"[Redis] Connecting to {redis_url}...")
    
    try:
        import redis
        
        _redis_client = redis.from_url(
            redis_url,
            encoding='utf-8',
            decode_responses=True,
            max_connections=config['max_connections'],
            socket_timeout=config['socket_timeout'],
            socket_connect_timeout=config['socket_connect_timeout'],
            retry_on_timeout=config['retry_on_timeout'],
        )
        
        # Test connection
        _redis_client.ping()
        
        # Get server info
        info = _redis_client.info("server")
        redis_version = info.get("redis_version", "unknown")
        
        _redis_available = True
        logger.info(f"[Redis] Connected successfully (version: {redis_version})")
        return True
        
    except ImportError:
        _log_redis_error(
            title="REDIS PACKAGE NOT INSTALLED",
            details=[
                "The 'redis' package is required but not installed.",
                "",
                "To fix, run:",
                "  pip install redis>=5.0.0",
            ]
        )
        raise SystemExit(1)
        
    except Exception as e:
        _log_redis_error(
            title="REDIS CONNECTION FAILED",
            details=[
                f"Failed to connect to Redis at: {redis_url}",
                f"Error: {e}",
                "",
                "MindGraph requires Redis. Please ensure Redis is running:",
                "",
                "  Ubuntu:  sudo apt install redis-server",
                "           sudo systemctl start redis-server",
                "",
                "  Docker:  docker run -d --name redis -p 6379:6379 redis:alpine",
                "",
                "Then set REDIS_URL in your .env file (default: redis://localhost:6379/0)",
            ]
        )
        raise SystemExit(1)


def close_redis_sync():
    """Close Redis connection gracefully (synchronous)."""
    global _redis_client, _redis_available
    
    if _redis_client:
        try:
            _redis_client.close()
            logger.info("[Redis] Connection closed")
        except Exception as e:
            logger.warning(f"[Redis] Error closing connection: {e}")
    
    _redis_client = None
    _redis_available = False


def is_redis_available() -> bool:
    """Check if Redis is available. Always True after successful init."""
    return _redis_available


def get_redis():
    """
    Get Redis client instance.
    
    Returns:
        Redis client (never None after init_redis_sync succeeds)
    """
    return _redis_client


def get_redis_mode() -> str:
    """Get current Redis mode. Always 'external' (Redis required)."""
    return 'external'


class RedisOperations:
    """
    High-level Redis operations with error handling.
    
    Thread-safe: Uses synchronous Redis client.
    """
    
    @staticmethod
    def set_with_ttl(key: str, value: str, ttl_seconds: int) -> bool:
        """Set a key with TTL. Returns True on success."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            logger.warning(f"[Redis] SET failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def get(key: str) -> Optional[str]:
        """Get a key value. Returns None if not found or on error."""
        if not _redis_available or not _redis_client:
            return None
        try:
            return _redis_client.get(key)
        except Exception as e:
            logger.warning(f"[Redis] GET failed for {key[:20]}: {e}")
            return None
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete a key. Returns True on success."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"[Redis] DELETE failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def get_and_delete(key: str) -> Optional[str]:
        """Atomically get and delete a key using pipeline."""
        if not _redis_available or not _redis_client:
            return None
        try:
            pipe = _redis_client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"[Redis] GET+DELETE failed for {key[:20]}: {e}")
            return None
    
    @staticmethod
    def increment(key: str, ttl_seconds: Optional[int] = None) -> Optional[int]:
        """Increment a counter. Optionally set TTL on first increment."""
        if not _redis_available or not _redis_client:
            return None
        try:
            pipe = _redis_client.pipeline()
            pipe.incr(key)
            if ttl_seconds:
                pipe.expire(key, ttl_seconds, nx=True)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"[Redis] INCR failed for {key[:20]}: {e}")
            return None
    
    @staticmethod
    def get_ttl(key: str) -> int:
        """Get remaining TTL of a key. Returns -1 if no TTL, -2 if key doesn't exist."""
        if not _redis_available or not _redis_client:
            return -2
        try:
            return _redis_client.ttl(key)
        except Exception as e:
            logger.warning(f"[Redis] TTL failed for {key[:20]}: {e}")
            return -2
    
    @staticmethod
    def set_ttl(key: str, ttl_seconds: int) -> bool:
        """Set TTL on existing key."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.expire(key, ttl_seconds)
            return True
        except Exception as e:
            logger.warning(f"[Redis] EXPIRE failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def exists(key: str) -> bool:
        """Check if key exists."""
        if not _redis_available or not _redis_client:
            return False
        try:
            return _redis_client.exists(key) > 0
        except Exception as e:
            logger.warning(f"[Redis] EXISTS failed for {key[:20]}: {e}")
            return False
    
    # ========================================================================
    # List Operations (for buffers, queues)
    # ========================================================================
    
    @staticmethod
    def list_push(key: str, value: str) -> bool:
        """Push value to end of list (RPUSH)."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.rpush(key, value)
            return True
        except Exception as e:
            logger.warning(f"[Redis] RPUSH failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def list_pop_many(key: str, count: int) -> List[str]:
        """Atomically pop up to count items from start of list."""
        if not _redis_available or not _redis_client:
            return []
        try:
            pipe = _redis_client.pipeline()
            pipe.lrange(key, 0, count - 1)
            pipe.ltrim(key, count, -1)
            results = pipe.execute()
            return results[0] or []
        except Exception as e:
            logger.warning(f"[Redis] List pop failed for {key[:20]}: {e}")
            return []
    
    @staticmethod
    def list_length(key: str) -> int:
        """Get list length."""
        if not _redis_available or not _redis_client:
            return 0
        try:
            return _redis_client.llen(key) or 0
        except Exception as e:
            logger.warning(f"[Redis] LLEN failed for {key[:20]}: {e}")
            return 0
    
    # ========================================================================
    # Sorted Set Operations (for rate limiting with sliding window)
    # ========================================================================
    
    @staticmethod
    def sorted_set_add(key: str, member: str, score: float) -> bool:
        """Add member to sorted set with score."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.zadd(key, {member: score})
            return True
        except Exception as e:
            logger.warning(f"[Redis] ZADD failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def sorted_set_count_in_range(
        key: str, 
        min_score: float, 
        max_score: float
    ) -> int:
        """Count members in sorted set within score range."""
        if not _redis_available or not _redis_client:
            return 0
        try:
            return _redis_client.zcount(key, min_score, max_score) or 0
        except Exception as e:
            logger.warning(f"[Redis] ZCOUNT failed for {key[:20]}: {e}")
            return 0
    
    @staticmethod
    def sorted_set_remove_by_score(
        key: str, 
        min_score: float, 
        max_score: float
    ) -> int:
        """Remove members from sorted set by score range."""
        if not _redis_available or not _redis_client:
            return 0
        try:
            return _redis_client.zremrangebyscore(key, min_score, max_score) or 0
        except Exception as e:
            logger.warning(f"[Redis] ZREMRANGEBYSCORE failed for {key[:20]}: {e}")
            return 0
    
    # ========================================================================
    # Hash Operations (for complex objects)
    # ========================================================================
    
    @staticmethod
    def hash_set(key: str, mapping: Dict[str, str]) -> bool:
        """Set multiple hash fields."""
        if not _redis_available or not _redis_client:
            return False
        try:
            _redis_client.hset(key, mapping=mapping)
            return True
        except Exception as e:
            logger.warning(f"[Redis] HSET failed for {key[:20]}: {e}")
            return False
    
    @staticmethod
    def hash_get_all(key: str) -> Dict[str, str]:
        """Get all hash fields."""
        if not _redis_available or not _redis_client:
            return {}
        try:
            return _redis_client.hgetall(key) or {}
        except Exception as e:
            logger.warning(f"[Redis] HGETALL failed for {key[:20]}: {e}")
            return {}
    
    @staticmethod
    def hash_delete(key: str, *fields: str) -> int:
        """Delete hash fields."""
        if not _redis_available or not _redis_client:
            return 0
        try:
            return _redis_client.hdel(key, *fields) or 0
        except Exception as e:
            logger.warning(f"[Redis] HDEL failed for {key[:20]}: {e}")
            return 0
    
    # ========================================================================
    # Utility Operations
    # ========================================================================
    
    @staticmethod
    def keys_by_pattern(pattern: str, count: int = 100) -> List[str]:
        """
        Get keys matching pattern using SCAN (safe for production).
        
        Uses SCAN instead of KEYS for O(1) per call instead of O(N).
        Limits results to prevent memory issues.
        """
        if not _redis_available or not _redis_client:
            return []
        try:
            keys = []
            cursor = 0
            while len(keys) < count:
                cursor, batch = _redis_client.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            return keys[:count]
        except Exception as e:
            logger.warning(f"[Redis] SCAN failed for {pattern[:20]}: {e}")
            return []
    
    @staticmethod
    def ping() -> bool:
        """Test Redis connection."""
        if not _redis_available or not _redis_client:
            return False
        try:
            return _redis_client.ping()
        except Exception:
            return False
    
    @staticmethod
    def info(section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis server info."""
        if not _redis_available or not _redis_client:
            return {}
        try:
            return _redis_client.info(section) if section else _redis_client.info()
        except Exception as e:
            logger.warning(f"[Redis] INFO failed: {e}")
            return {}


# Convenience alias
redis_ops = RedisOperations
