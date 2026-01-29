"""
Automatic Library Import Scheduler

Periodically checks for new PDFs in storage/library/ and imports them automatically.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import logging
import os
import uuid
from typing import Optional

from config.database import SessionLocal
from services.library.pdf_importer import auto_import_new_pdfs
from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

# Configuration
AUTO_IMPORT_ENABLED = os.getenv("LIBRARY_AUTO_IMPORT_ENABLED", "true").lower() == "true"
AUTO_IMPORT_INTERVAL = int(os.getenv("LIBRARY_AUTO_IMPORT_INTERVAL", "5"))  # minutes

# Distributed lock configuration
AUTO_IMPORT_LOCK_KEY = "library:auto_import:lock"
AUTO_IMPORT_LOCK_TTL = 300  # 5 minutes - enough time for import, auto-release on crash


class _LockState:
    """Manages worker lock ID state to avoid global variables."""
    _lock_id: Optional[str] = None

    @classmethod
    def set_lock_id(cls, lock_id: str) -> None:
        """Set the worker lock ID."""
        cls._lock_id = lock_id

    @classmethod
    def get_lock_id(cls) -> Optional[str]:
        """Get the worker lock ID."""
        return cls._lock_id

    @classmethod
    def clear_lock_id(cls) -> None:
        """Clear the worker lock ID."""
        cls._lock_id = None


def _generate_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


def acquire_auto_import_lock() -> bool:
    """
    Attempt to acquire the auto-import scheduler lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should run scheduler)
        False if lock held by another worker or Redis unavailable
    """
    if not is_redis_available():
        logger.debug("[Library Auto-Import] Redis unavailable, skipping lock acquisition")
        return False

    try:
        redis_client = get_redis()
        if redis_client is None:
            logger.debug("[Library Auto-Import] Redis client unavailable, skipping lock acquisition")
            return False

        lock_id = _generate_lock_id()
        _LockState.set_lock_id(lock_id)

        # Try to acquire lock: SETNX with TTL
        acquired = redis_client.set(
            AUTO_IMPORT_LOCK_KEY,
            lock_id,
            nx=True,
            ex=AUTO_IMPORT_LOCK_TTL
        )

        if acquired:
            logger.info(
                "[Library Auto-Import] Lock acquired (worker: %s)",
                lock_id
            )
            return True

        logger.debug(
            "[Library Auto-Import] Lock held by another worker, skipping"
        )
        return False

    except Exception as e:
        logger.warning(
            "[Library Auto-Import] Error acquiring lock: %s",
            e
        )
        return False


def refresh_auto_import_lock() -> bool:
    """
    Refresh the auto-import lock TTL if this worker holds it.

    Returns:
        True if lock refreshed, False otherwise
    """
    lock_id = _LockState.get_lock_id()
    if not lock_id or not is_redis_available():
        return False

    try:
        redis_client = get_redis()
        if redis_client is None:
            return False

        current_value = redis_client.get(AUTO_IMPORT_LOCK_KEY)

        if current_value and current_value.decode() == lock_id:
            redis_client.expire(AUTO_IMPORT_LOCK_KEY, AUTO_IMPORT_LOCK_TTL)
            return True

        return False

    except Exception as e:
        logger.warning(
            "[Library Auto-Import] Error refreshing lock: %s",
            e
        )
        return False


async def start_library_auto_import_scheduler():
    """
    Start the automatic library import scheduler.

    Uses Redis distributed lock to ensure only ONE worker runs the scheduler
    across all uvicorn workers. This prevents duplicate imports.

    Runs every N minutes (configurable via LIBRARY_AUTO_IMPORT_INTERVAL).
    This function runs forever until cancelled.
    """
    if not AUTO_IMPORT_ENABLED:
        logger.info("[Library Auto-Import] Automatic import is disabled (LIBRARY_AUTO_IMPORT_ENABLED=false)")
        return

    # Attempt to acquire distributed lock
    # Only ONE worker across all processes will succeed
    if not acquire_auto_import_lock():
        # Lock acquisition already logged the skip message
        # Keep running but don't do anything - just monitor
        # If the lock holder dies, this worker can try to acquire on next check
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                if acquire_auto_import_lock():
                    logger.info("[Library Auto-Import] Lock acquired, this worker will now run auto-import")
                    break
            except asyncio.CancelledError:
                logger.info("[Library Auto-Import] Scheduler monitor stopped")
                return
            except Exception:
                pass

    # This worker holds the lock - run the scheduler
    interval_seconds = AUTO_IMPORT_INTERVAL * 60
    logger.info(
        "[Library Auto-Import] Scheduler started (this worker is the lock holder)"
    )
    logger.info(
        "[Library Auto-Import] Configuration: check every %s minutes",
        AUTO_IMPORT_INTERVAL
    )

    while True:
        try:
            # Refresh lock to prevent expiration during long waits
            refresh_auto_import_lock()

            # Run auto-import
            db = SessionLocal()
            try:
                imported, skipped = auto_import_new_pdfs(db, extract_covers=True)
                if imported > 0:
                    logger.info(
                        "[Library Auto-Import] Imported %s new PDF(s), skipped %s",
                        imported,
                        skipped
                    )
            except Exception as e:
                logger.error(
                    "[Library Auto-Import] Error during auto-import: %s",
                    e,
                    exc_info=True
                )
            finally:
                db.close()

            # Wait for next interval
            await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logger.info("[Library Auto-Import] Scheduler stopped")
            break
        except Exception as e:
            logger.error(
                "[Library Auto-Import] Unexpected error in scheduler: %s",
                e,
                exc_info=True
            )
            # Wait a bit before retrying
            await asyncio.sleep(60)
