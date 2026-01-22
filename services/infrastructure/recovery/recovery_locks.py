"""
Recovery Lock Management Module

Distributed lock management for multi-worker database integrity checks.
Ensures only one worker performs integrity checks to avoid conflicts.
"""

import logging
import os
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to run database integrity checks.
#
# Solution: Redis-based distributed lock ensures only ONE worker checks integrity.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: recovery:integrity_check:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 5 minutes (enough for integrity check, auto-release if worker crashes)
# ============================================================================

INTEGRITY_CHECK_LOCK_KEY = "recovery:integrity_check:lock"
INTEGRITY_CHECK_LOCK_TTL = 300  # 5 minutes
_integrity_check_lock_id: Optional[str] = None

# Note: No cache needed - lock mechanism ensures only one worker checks integrity
# Other workers skip via lock acquisition failure
_integrity_check_cache: Optional[Tuple[bool, float]] = None  # Unused, kept for API compatibility

# Import Redis client (optional dependency)
try:
    from services.redis.redis_client import get_redis, is_redis_available
except ImportError:
    get_redis = None  # type: ignore
    is_redis_available = None  # type: ignore


def _generate_integrity_check_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


def acquire_integrity_check_lock() -> bool:
    """
    Attempt to acquire the integrity check lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should check integrity)
        False if lock held by another worker
    """
    global _integrity_check_lock_id  # pylint: disable=global-statement

    # Redis not available, assume single worker mode
    if get_redis is None or is_redis_available is None:
        return True

    if not is_redis_available():
        logger.debug(
            "[Recovery] Redis unavailable, assuming single worker mode "
            "for integrity check"
        )
        return True

    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode

    try:
        # Generate unique ID for this worker
        if _integrity_check_lock_id is None:
            _integrity_check_lock_id = _generate_integrity_check_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        acquired = redis.set(
            INTEGRITY_CHECK_LOCK_KEY,
            _integrity_check_lock_id,
            nx=True,  # Only set if not exists
            ex=INTEGRITY_CHECK_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.debug(
                "[Recovery] Integrity check lock acquired by this worker (id=%s)",
                _integrity_check_lock_id
            )
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(INTEGRITY_CHECK_LOCK_KEY)
            logger.info(
                "[Recovery] Another worker holds the integrity check lock "
                "(holder=%s), skipping integrity check",
                holder
            )
            return False

    except (AttributeError, ConnectionError, RuntimeError) as e:
        logger.warning(
            "[Recovery] Lock acquisition failed: %s, proceeding anyway", e
        )
        return True  # On error, proceed


def release_integrity_check_lock() -> bool:
    """
    Release the integrity check lock if held by this worker.

    Uses Lua script to ensure we only release our own lock.

    Returns:
        True if lock released, False otherwise
    """
    # Redis not available
    if get_redis is None or is_redis_available is None:
        return False

    if not is_redis_available() or _integrity_check_lock_id is None:
        return False

    redis = get_redis()
    if not redis:
        return False

    try:
        # Lua script: Only delete if lock value matches our lock_id
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        result = redis.eval(
            lua_script, 1, INTEGRITY_CHECK_LOCK_KEY, _integrity_check_lock_id
        )

        if result:
            logger.debug(
                "[Recovery] Integrity check lock released (id=%s)",
                _integrity_check_lock_id
            )
            return True
        else:
            return False

    except (AttributeError, ConnectionError, RuntimeError) as e:
        logger.debug("[Recovery] Integrity check lock release failed: %s", e)
        return False


def get_integrity_check_cache() -> Optional[Tuple[bool, float]]:
    """
    Get cached integrity check result (no-op - cache disabled).
    
    Cache is disabled because lock mechanism already ensures only one worker
    checks integrity. Other workers skip via lock acquisition failure.
    """
    return None


def set_integrity_check_cache(_value: Tuple[bool, float]) -> None:
    """
    Set cached integrity check result (no-op - cache disabled).
    
    Cache is disabled because lock mechanism already ensures only one worker
    checks integrity. Other workers skip via lock acquisition failure.
    """
    # No-op: cache disabled
