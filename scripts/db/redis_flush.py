"""Flush Redis cache DB after RLS runtime URL switch (migration CLI)."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _mask_redis_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.password:
            return url
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or ""
        auth = f"{user}:" if user else ""
        netloc = f"{auth}****@{host}{port}"
        return parsed._replace(netloc=netloc).geturl()
    except (ValueError, TypeError, AttributeError):
        return url


def flush_redis_cache(redis_url: str | None = None) -> tuple[bool, str]:
    """
    ``FLUSHDB`` on the Redis logical database from ``REDIS_URL``.

    Returns (success, human-readable message).
    """
    url = (redis_url or os.getenv("REDIS_URL") or _DEFAULT_REDIS_URL).strip()
    try:
        import redis
    except ImportError:
        return False, "redis package not installed (pip install redis)"

    client = None
    try:
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        db_index = client.connection_pool.connection_kwargs.get("db", 0)
        client.flushdb()
        return True, f"Flushed Redis DB {db_index} ({_mask_redis_url(url)})"
    except Exception as exc:
        logger.debug("Redis flush failed: %s", exc)
        return False, str(exc)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def redis_db_index(redis_url: str | None = None) -> int:
    url = (redis_url or os.getenv("REDIS_URL") or _DEFAULT_REDIS_URL).strip()
    parsed = urlparse(url)
    if parsed.path and parsed.path.strip("/"):
        return int(parsed.path.strip("/").split("/")[0])
    return 0


def redis_flush_cli_hint(redis_url: str | None = None) -> str:
    return f"redis-cli -n {redis_db_index(redis_url)} FLUSHDB"


def redis_flush_summary_label(redis_url: str | None = None) -> str:
    """Short label for the yes/no prompt."""
    url = (redis_url or os.getenv("REDIS_URL") or _DEFAULT_REDIS_URL).strip()
    db_index = redis_db_index(url)
    return f"redis DB {db_index} ({_mask_redis_url(url)})"
