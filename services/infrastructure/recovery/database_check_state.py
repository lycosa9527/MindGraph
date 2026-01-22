"""
Database Check State Manager for MindGraph

Manages the state of database integrity checks to prevent false alerts
when checks take a long time to complete.

Features:
- Tracks in-progress database checks
- Prevents SMS alerts for timeouts during legitimate long-running checks
- Uses Redis for distributed state management (if available)
- Falls back to in-memory state if Redis is unavailable

Author: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import os
import time
from typing import Optional, Tuple

try:
    from services.redis.redis_client import get_redis, is_redis_available
    _REDIS_AVAILABLE = True
except ImportError:
    get_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Redis key for database check state
DB_CHECK_STATE_KEY = "database_check:state"
DB_CHECK_START_TIME_KEY = "database_check:start_time"
DB_CHECK_TIMEOUT_SECONDS = int(os.getenv("DB_CHECK_TIMEOUT_SECONDS", "300"))  # 5 minutes default


class DatabaseCheckStateManager:
    """
    Manages database check state to prevent false alerts during long-running checks.
    """

    def __init__(self):
        """Initialize DatabaseCheckStateManager"""
        self._in_memory_state: Optional[Tuple[str, float]] = None
        self._in_memory_start_time: Optional[float] = None

    def _get_redis_client(self):
        """Get Redis client if available"""
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return None

        try:
            if get_redis is None:
                return None
            return get_redis()
        except Exception as e:
            logger.debug("[DatabaseCheckState] Redis not available: %s", e)
            return None

    async def start_check(self) -> bool:
        """
        Mark that a database check has started.

        Returns:
            True if check state was set, False if a check is already in progress
        """
        redis_client = self._get_redis_client()

        if redis_client:
            try:
                # Try to set state atomically (only if not exists)
                result = await asyncio.to_thread(
                    redis_client.set,
                    DB_CHECK_STATE_KEY,
                    "in_progress",
                    ex=DB_CHECK_TIMEOUT_SECONDS,
                    nx=True
                )
                if result:
                    await asyncio.to_thread(
                        redis_client.set,
                        DB_CHECK_START_TIME_KEY,
                        str(time.time()),
                        ex=DB_CHECK_TIMEOUT_SECONDS
                    )
                    logger.debug("[DatabaseCheckState] Database check started (Redis)")
                    return True
                logger.debug("[DatabaseCheckState] Database check already in progress (Redis)")
                return False
            except Exception as e:
                logger.debug("[DatabaseCheckState] Failed to set Redis state: %s", e)
                # Fall through to in-memory state

        # Fallback to in-memory state
        if self._in_memory_state is None:
            self._in_memory_state = ("in_progress", time.time())
            self._in_memory_start_time = time.time()
            logger.debug("[DatabaseCheckState] Database check started (in-memory)")
            return True

        # Check if in-memory state has expired
        if self._in_memory_start_time:
            elapsed = time.time() - self._in_memory_start_time
            if elapsed > DB_CHECK_TIMEOUT_SECONDS:
                logger.debug("[DatabaseCheckState] In-memory state expired, resetting")
                self._in_memory_state = ("in_progress", time.time())
                self._in_memory_start_time = time.time()
                return True

        logger.debug("[DatabaseCheckState] Database check already in progress (in-memory)")
        return False

    async def complete_check(self, success: bool = True) -> None:
        """
        Mark that a database check has completed.

        Args:
            success: True if check succeeded, False if it failed
        """
        redis_client = self._get_redis_client()

        if redis_client:
            try:
                state = "completed_success" if success else "completed_failure"
                await asyncio.to_thread(
                    redis_client.set,
                    DB_CHECK_STATE_KEY,
                    state,
                    ex=60  # Keep state for 1 minute after completion
                )
                logger.debug("[DatabaseCheckState] Database check completed: %s (Redis)", state)
                return
            except Exception as e:
                logger.debug("[DatabaseCheckState] Failed to update Redis state: %s", e)
                # Fall through to in-memory state

        # Fallback to in-memory state
        state = "completed_success" if success else "completed_failure"
        self._in_memory_state = (state, time.time())
        logger.debug("[DatabaseCheckState] Database check completed: %s (in-memory)", state)

    async def is_check_in_progress(self) -> bool:
        """
        Check if a database check is currently in progress.

        Returns:
            True if check is in progress, False otherwise
        """
        redis_client = self._get_redis_client()

        if redis_client:
            try:
                state = await asyncio.to_thread(redis_client.get, DB_CHECK_STATE_KEY)
                if state:
                    if isinstance(state, bytes):
                        state = state.decode('utf-8')
                    if state == "in_progress":
                        # Check if it's been too long (stale state)
                        start_time_str = await asyncio.to_thread(
                            redis_client.get, DB_CHECK_START_TIME_KEY
                        )
                        if start_time_str:
                            if isinstance(start_time_str, bytes):
                                start_time_str = start_time_str.decode('utf-8')
                            try:
                                start_time = float(start_time_str)
                                elapsed = time.time() - start_time
                                if elapsed > DB_CHECK_TIMEOUT_SECONDS:
                                    logger.warning(
                                        "[DatabaseCheckState] Stale check state detected "
                                        "(%.1fs old), clearing",
                                        elapsed
                                    )
                                    await asyncio.to_thread(
                                        redis_client.delete, DB_CHECK_STATE_KEY
                                    )
                                    return False
                            except (ValueError, TypeError):
                                pass
                        return True
                return False
            except Exception as e:
                logger.debug("[DatabaseCheckState] Failed to check Redis state: %s", e)
                # Fall through to in-memory state

        # Fallback to in-memory state
        if self._in_memory_state:
            state, start_time = self._in_memory_state
            if state == "in_progress":
                elapsed = time.time() - start_time
                if elapsed > DB_CHECK_TIMEOUT_SECONDS:
                    logger.warning(
                        "[DatabaseCheckState] Stale in-memory state detected "
                        "(%.1fs old), clearing",
                        elapsed
                    )
                    self._in_memory_state = None
                    self._in_memory_start_time = None
                    return False
                return True

        return False

    async def get_check_state(self) -> Optional[str]:
        """
        Get current database check state.

        Returns:
            "in_progress", "completed_success", "completed_failure", or None
        """
        redis_client = self._get_redis_client()

        if redis_client:
            try:
                state = await asyncio.to_thread(redis_client.get, DB_CHECK_STATE_KEY)
                if state:
                    if isinstance(state, bytes):
                        return state.decode('utf-8')
                    return str(state)
                return None
            except Exception as e:
                logger.debug("[DatabaseCheckState] Failed to get Redis state: %s", e)
                # Fall through to in-memory state

        # Fallback to in-memory state
        if self._in_memory_state:
            return self._in_memory_state[0]

        return None


# Global singleton instance
_db_check_state_manager: Optional[DatabaseCheckStateManager] = None


def get_database_check_state_manager() -> DatabaseCheckStateManager:
    """Get global DatabaseCheckStateManager instance"""
    global _db_check_state_manager
    if _db_check_state_manager is None:
        _db_check_state_manager = DatabaseCheckStateManager()
    return _db_check_state_manager
