"""
Kitty control-plane shared secret management.

Auto-generated and stored in Redis (multi-worker safe), with optional file backup
for recovery after Redis flush. Explicit ``KITTY_CONTROL_SHARED_SECRET`` in the
environment still overrides Redis when set.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

KITTY_CONTROL_SECRET_REDIS_KEY = "kitty:control:shared_secret"
KITTY_CONTROL_SECRET_BACKUP_FILE = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(__file__)),
            ),
        ),
    ),
    "data",
    ".kitty_control_secret",
)


class _KittyControlSecretCache:
    """In-memory Kitty control secret holder (no global keyword)."""

    value: Optional[str] = None


_get_redis = None
_is_redis_available = None
_get_async_redis = None

try:
    from services.redis.redis_client import get_redis as redis_get_redis
    from services.redis.redis_client import is_redis_available as redis_is_available

    _get_redis = redis_get_redis
    _is_redis_available = redis_is_available
except ImportError:
    pass

try:
    from services.redis.redis_async_client import get_async_redis as redis_get_async

    _get_async_redis = redis_get_async
except ImportError:
    pass


def _env_override_secret() -> str:
    """Env override secret."""
    return os.getenv("KITTY_CONTROL_SHARED_SECRET", "").strip()


def _decode_redis_secret(raw: object) -> str:
    """Decode redis secret."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _save_kitty_control_secret_backup(secret: str) -> bool:
    """Save kitty control secret backup."""
    try:
        data_dir = os.path.dirname(KITTY_CONTROL_SECRET_BACKUP_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        with open(KITTY_CONTROL_SECRET_BACKUP_FILE, "w", encoding="utf-8") as handle:
            handle.write(secret)

        try:
            os.chmod(KITTY_CONTROL_SECRET_BACKUP_FILE, 0o600)
        except (OSError, AttributeError):
            pass

        logger.info("[Kitty] Control shared secret backed up to file")
        return True
    except OSError as exc:
        logger.warning("[Kitty] Failed to backup control shared secret: %s", exc)
        return False


def _load_kitty_control_secret_backup() -> Optional[str]:
    """Load kitty control secret backup."""
    try:
        if not os.path.exists(KITTY_CONTROL_SECRET_BACKUP_FILE):
            return None

        with open(KITTY_CONTROL_SECRET_BACKUP_FILE, "r", encoding="utf-8") as handle:
            secret = handle.read().strip()

        if secret and len(secret) >= 32:
            logger.info("[Kitty] Restored control shared secret from backup file")
            return secret
        return None
    except OSError as exc:
        logger.warning("[Kitty] Failed to load control shared secret backup: %s", exc)
        return None


def _cache_secret(secret: str) -> str:
    """Cache secret."""
    _KittyControlSecretCache.value = secret
    return secret


def get_kitty_control_shared_secret() -> str:
    """
    Return the Kitty control-plane HMAC secret.

    Resolution order:
    1. In-memory cache (after warmup)
    2. ``KITTY_CONTROL_SHARED_SECRET`` env override
    3. Redis key ``kitty:control:shared_secret``
    4. Backup file under ``data/.kitty_control_secret``
    5. Generate under SET NX (sync Redis path only)
    """
    if _KittyControlSecretCache.value:
        return _KittyControlSecretCache.value

    env_secret = _env_override_secret()
    if env_secret:
        return _cache_secret(env_secret)

    if _get_redis is None or _is_redis_available is None:
        return ""

    if not _is_redis_available():
        return ""

    redis = _get_redis()
    if not redis:
        return ""

    secret = redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
    if secret:
        return _cache_secret(_decode_redis_secret(secret))

    backup_secret = _load_kitty_control_secret_backup()
    if backup_secret:
        if redis.set(KITTY_CONTROL_SECRET_REDIS_KEY, backup_secret, nx=True):
            logger.info("[Kitty] Restored control shared secret from backup to Redis")
            return _cache_secret(backup_secret)

        secret = redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
        if secret:
            return _cache_secret(_decode_redis_secret(secret))

    new_secret = secrets.token_urlsafe(48)
    if redis.set(KITTY_CONTROL_SECRET_REDIS_KEY, new_secret, nx=True):
        logger.info("[Kitty] Generated new control shared secret (stored in Redis)")
        _save_kitty_control_secret_backup(new_secret)
        return _cache_secret(new_secret)

    secret = redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
    if secret:
        secret_str = _decode_redis_secret(secret)
        _save_kitty_control_secret_backup(secret_str)
        return _cache_secret(secret_str)

    return ""


async def warmup_kitty_control_secret_async() -> str:
    """
    Warm the Kitty control secret cache during lifespan startup.

    Mirrors :func:`get_kitty_control_shared_secret` but uses the async Redis client.
    """
    if _KittyControlSecretCache.value:
        return _KittyControlSecretCache.value

    env_secret = _env_override_secret()
    if env_secret:
        return _cache_secret(env_secret)

    if _get_async_redis is None:
        raise RuntimeError("Async Redis client not available for Kitty control secret warmup.")

    redis = _get_async_redis()
    if not redis:
        raise RuntimeError("Failed to connect to async Redis for Kitty control secret warmup.")

    secret = await redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
    if secret:
        return _cache_secret(_decode_redis_secret(secret))

    backup_secret = _load_kitty_control_secret_backup()
    if backup_secret:
        if await redis.set(KITTY_CONTROL_SECRET_REDIS_KEY, backup_secret, nx=True):
            logger.info("[Kitty] Restored control shared secret from backup to Redis (warmup)")
            return _cache_secret(backup_secret)

        secret = await redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
        if secret:
            return _cache_secret(_decode_redis_secret(secret))

    new_secret = secrets.token_urlsafe(48)
    if await redis.set(KITTY_CONTROL_SECRET_REDIS_KEY, new_secret, nx=True):
        logger.info("[Kitty] Generated new control shared secret during async warmup")
        _save_kitty_control_secret_backup(new_secret)
        return _cache_secret(new_secret)

    secret = await redis.get(KITTY_CONTROL_SECRET_REDIS_KEY)
    if secret:
        secret_str = _decode_redis_secret(secret)
        _save_kitty_control_secret_backup(secret_str)
        return _cache_secret(secret_str)

    raise RuntimeError("Failed to retrieve or generate Kitty control shared secret during warmup.")
