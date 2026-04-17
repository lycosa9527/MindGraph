"""
JWT Secret Management for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Secure JWT secret generation, storage, and retrieval using Redis.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import secrets
from typing import Optional

from .config import JWT_SECRET_REDIS_KEY, JWT_SECRET_BACKUP_FILE

logger = logging.getLogger(__name__)

# Cached JWT secret (to avoid Redis lookup on every request).
# After startup warmup via warmup_jwt_secret_async(), all callers (sync or async)
# read from this cache and never hit Redis on the hot path.
_jwt_secret_cache: Optional[str] = None

_redis_available = False
_get_redis = None
_is_redis_available = None
_get_async_redis = None

try:
    from services.redis.redis_client import get_redis as redis_get_redis
    from services.redis.redis_client import is_redis_available as redis_is_available

    _redis_available = True
    _get_redis = redis_get_redis
    _is_redis_available = redis_is_available
except ImportError:
    pass

try:
    from services.redis.redis_async_client import get_async_redis as redis_get_async

    _get_async_redis = redis_get_async
except ImportError:
    pass


def _save_jwt_secret_backup(secret: str) -> bool:
    """
    Save JWT secret to a file for backup/recovery.

    This allows recovery after Redis flush without invalidating all user tokens.
    The file is stored in the data directory with restricted permissions.

    Args:
        secret: JWT secret to backup

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Ensure data directory exists
        data_dir = os.path.dirname(JWT_SECRET_BACKUP_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        # Write secret to file with restricted permissions
        with open(JWT_SECRET_BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(secret)

        # Set file permissions to owner-only (Unix)
        try:
            os.chmod(JWT_SECRET_BACKUP_FILE, 0o600)
        except (OSError, AttributeError):
            # Windows doesn't support chmod, skip
            pass

        logger.info("[Auth] JWT secret backed up to file")
        return True
    except Exception as e:
        logger.warning("[Auth] Failed to backup JWT secret to file: %s", e)
        return False


def _load_jwt_secret_backup() -> Optional[str]:
    """
    Load JWT secret from backup file.

    Returns:
        JWT secret if found and valid, None otherwise
    """
    try:
        if not os.path.exists(JWT_SECRET_BACKUP_FILE):
            return None

        with open(JWT_SECRET_BACKUP_FILE, "r", encoding="utf-8") as f:
            secret = f.read().strip()

        # Validate secret format (should be URL-safe base64)
        if secret and len(secret) >= 32:
            logger.info("[Auth] Restored JWT secret from backup file")
            return secret

        return None
    except Exception as e:
        logger.warning("[Auth] Failed to load JWT secret backup: %s", e)
        return None


def get_jwt_secret() -> str:
    """
    Get or generate JWT secret from Redis (shared across all workers).

    Security benefits:
    - Auto-generated cryptographically secure 64-char secret
    - Shared across all workers via Redis (multi-worker safe)
    - No manual configuration required (removed from .env)
    - Persistent backup to file for recovery after Redis flush
    - Users only re-login if both Redis AND backup file are lost (very rare)

    Uses SET NX (set if not exists) to ensure only one worker generates
    the secret, preventing race conditions.

    Returns:
        JWT secret string (64 chars, cryptographically secure)

    Raises:
        RuntimeError: If Redis is not available or JWT secret retrieval fails
    """
    global _jwt_secret_cache

    # Return cached value if available (avoids Redis lookup on every JWT operation)
    if _jwt_secret_cache:
        return _jwt_secret_cache

    if not _redis_available:
        raise RuntimeError("Redis client not available. Redis is required for JWT secret storage.")

    if _is_redis_available is None:
        raise RuntimeError("is_redis_available function not available")
    if _get_redis is None:
        raise RuntimeError("get_redis function not available")

    try:
        if not _is_redis_available():
            raise RuntimeError(
                "Redis is required for JWT secret storage. Please ensure Redis is running and REDIS_URL is configured."
            )

        redis = _get_redis()
        if not redis:
            raise RuntimeError("Failed to connect to Redis for JWT secret retrieval")

        # Try to get existing secret from Redis
        secret = redis.get(JWT_SECRET_REDIS_KEY)
        if secret:
            secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
            _jwt_secret_cache = secret_str
            logger.debug("[Auth] Retrieved JWT secret from Redis")
            return secret_str

        # Redis doesn't have the secret - try to restore from backup
        backup_secret = _load_jwt_secret_backup()
        if backup_secret:
            if redis.set(JWT_SECRET_REDIS_KEY, backup_secret, nx=True):
                logger.info("[Auth] Restored JWT secret from backup to Redis")
                _jwt_secret_cache = backup_secret
                return backup_secret

            # Another worker restored it first, fetch theirs
            secret = redis.get(JWT_SECRET_REDIS_KEY)
            if secret:
                secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
                _jwt_secret_cache = secret_str
                return secret_str

        # Generate new secret (SET NX ensures only one worker creates it)
        new_secret = secrets.token_urlsafe(48)  # 64 chars, cryptographically secure

        if redis.set(JWT_SECRET_REDIS_KEY, new_secret, nx=True):
            logger.info("[Auth] Generated new JWT secret (stored in Redis)")
            _jwt_secret_cache = new_secret
            _save_jwt_secret_backup(new_secret)
            return new_secret

        # Another worker created it first, fetch theirs
        secret = redis.get(JWT_SECRET_REDIS_KEY)
        if secret:
            secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
            _jwt_secret_cache = secret_str
            _save_jwt_secret_backup(secret_str)
            return secret_str

        raise RuntimeError("Failed to retrieve or generate JWT secret from Redis")

    except ImportError as exc:
        raise RuntimeError("Redis client not available. Redis is required for JWT secret storage.") from exc
    except Exception as e:
        logger.error("[Auth] JWT secret retrieval failed: %s", e)
        raise


async def warmup_jwt_secret_async() -> str:
    """
    Warm the JWT secret cache using the shared async Redis client.

    Intended to be awaited once during the FastAPI lifespan startup so that
    every subsequent ``get_jwt_secret()`` call (from sync or async paths) is a
    pure in-memory cache hit. If the cache is already populated this is a no-op.

    Behaviour mirrors :func:`get_jwt_secret` (existing key wins, backup file is
    consulted, otherwise a new secret is generated under SET NX) but performs
    every Redis round-trip via the asyncio client to avoid blocking the event
    loop on application startup.

    Returns:
        The active JWT secret string.

    Raises:
        RuntimeError: If neither Redis nor a backup file is available.
    """
    global _jwt_secret_cache

    if _jwt_secret_cache:
        return _jwt_secret_cache

    if _get_async_redis is None:
        raise RuntimeError("Async Redis client not available. Cannot warm JWT secret cache.")

    redis = _get_async_redis()
    if not redis:
        raise RuntimeError("Failed to connect to async Redis for JWT secret warmup")

    try:
        secret = await redis.get(JWT_SECRET_REDIS_KEY)
        if secret:
            secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
            _jwt_secret_cache = secret_str
            logger.debug("[Auth] Warmed JWT secret cache from Redis")
            return secret_str

        backup_secret = _load_jwt_secret_backup()
        if backup_secret:
            if await redis.set(JWT_SECRET_REDIS_KEY, backup_secret, nx=True):
                logger.info("[Auth] Restored JWT secret from backup to Redis (warmup)")
                _jwt_secret_cache = backup_secret
                return backup_secret

            secret = await redis.get(JWT_SECRET_REDIS_KEY)
            if secret:
                secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
                _jwt_secret_cache = secret_str
                return secret_str

        new_secret = secrets.token_urlsafe(48)
        if await redis.set(JWT_SECRET_REDIS_KEY, new_secret, nx=True):
            logger.info("[Auth] Generated new JWT secret during async warmup")
            _jwt_secret_cache = new_secret
            _save_jwt_secret_backup(new_secret)
            return new_secret

        secret = await redis.get(JWT_SECRET_REDIS_KEY)
        if secret:
            secret_str = secret.decode("utf-8") if isinstance(secret, bytes) else secret
            _jwt_secret_cache = secret_str
            _save_jwt_secret_backup(secret_str)
            return secret_str

        raise RuntimeError("Failed to retrieve or generate JWT secret during async warmup")
    except Exception as exc:
        logger.error("[Auth] JWT secret async warmup failed: %s", exc)
        raise
