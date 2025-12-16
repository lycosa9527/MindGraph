"""
SQLite Captcha Storage
======================

High-performance captcha storage using SQLite with WAL mode.
Provides immediate cross-worker visibility for multi-worker deployments.

Features:
- Uses existing mindgraph.db database
- WAL mode for concurrent reads
- Immediate visibility across all workers
- Automatic expiration cleanup (scheduled every 10 minutes)
- Thread-safe operations

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Callable

from sqlalchemy.orm import Session
from config.database import SessionLocal
from models.auth import Captcha

logger = logging.getLogger(__name__)


class SQLiteCaptchaStorage:
    """
    SQLite-based captcha storage for multi-worker compatibility.
    
    Uses the existing mindgraph.db database with WAL mode enabled.
    All operations are immediately visible to all workers.
    """
    
    def __init__(self):
        """Initialize SQLite captcha storage."""
        logger.info("[CaptchaStorage] Initialized SQLite-based storage (multi-worker safe)")
    
    def _get_db(self) -> Session:
        """Get a database session."""
        return SessionLocal()
    
    def _retry_on_lock(self, operation_func: Callable, max_retries: int = 8, base_delay: float = 0.02):
        """
        Retry database operations on lock errors with exponential backoff.
        
        Optimized for multi-worker deployments (4 workers):
        - SQLite busy_timeout: 150ms (handles queued writes from multiple workers)
        - App retries: 8 attempts with exponential backoff (increased from 4 for better contention handling)
        - Delays: 0.02s, 0.04s, 0.08s, 0.16s, 0.32s, 0.64s, 1.28s, 2.56s
        - Jitter: 30% (spreads retries across workers to avoid thundering herd)
        
        Worst-case total wait: ~1.5s (8 SQLite attempts × 150ms + 8 app delays ~300ms)
        Typical wait: 10-150ms (most locks clear quickly)
        Old approach: up to 5 seconds → ~3x faster, but more reliable for 4-worker contention
        
        Database locks are transient and usually resolve quickly. This retry logic
        handles transient locks gracefully while still failing fast on other errors.
        
        Args:
            operation_func: Function to execute (should be a callable that returns a value)
            max_retries: Maximum number of retry attempts (default: 8 for multi-worker)
            base_delay: Base delay in seconds for exponential backoff (default: 0.02s)
        
        Returns:
            Result from operation_func if successful
        
        Raises:
            Exception: If all retries fail or error is not a database lock
        """
        for attempt in range(max_retries):
            try:
                result = operation_func()
                # Log success if this was a retry (operation succeeded after initial failure)
                if attempt > 0:
                    logger.info(
                        f"[CaptchaStorage] Operation succeeded after {attempt} retry attempt(s). "
                        f"Total attempts: {attempt + 1}"
                    )
                return result
            except Exception as e:
                error_msg = str(e).lower()
                is_db_lock = "database is locked" in error_msg or "database locked" in error_msg
                
                if is_db_lock and attempt < max_retries - 1:
                    # Exponential backoff: 0.02s, 0.04s, 0.08s, 0.16s
                    delay = base_delay * (2 ** attempt)
                    # Increased jitter (30%) to spread retries across multiple workers
                    # Prevents thundering herd when all workers retry simultaneously
                    jitter = random.uniform(0, delay * 0.3)
                    total_delay = delay + jitter
                    
                    # Log every retry attempt with details
                    logger.warning(
                        f"[CaptchaStorage] Database lock detected (attempt {attempt + 1}/{max_retries}), "
                        f"retrying after {total_delay:.3f}s delay. Error: {str(e)[:150]}"
                    )
                    time.sleep(total_delay)
                    continue
                
                # All retries exhausted or non-lock error
                if is_db_lock:
                    logger.error(
                        f"[CaptchaStorage] All {max_retries} retry attempts exhausted for database lock. "
                        f"Final error: {str(e)[:200]}"
                    )
                else:
                    # Non-lock error - log at warning level (will be re-raised)
                    logger.warning(
                        f"[CaptchaStorage] Non-lock database error (not retrying): {str(e)[:200]}"
                    )
                raise
    
    def store(self, captcha_id: str, code: str, expires_in_seconds: int = 300):
        """
        Store a captcha code.
        
        Automatically retries on database lock errors (transient locks).
        
        Args:
            captcha_id: Unique captcha identifier (UUID)
            code: Captcha code to store
            expires_in_seconds: Time until expiration (default: 5 minutes)
        """
        def _store_operation():
            db = self._get_db()
            try:
                # Calculate expiration time
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
                
                # Check if exists and update, or insert new
                existing = db.query(Captcha).filter(Captcha.id == captcha_id).first()
                if existing:
                    existing.code = code.upper()
                    existing.expires_at = expires_at
                else:
                    captcha = Captcha(
                        id=captcha_id,
                        code=code.upper(),
                        expires_at=expires_at
                    )
                    db.add(captcha)
                
                db.commit()
                logger.debug(f"[CaptchaStorage] [STORE] Stored captcha: {captcha_id}")
                return True
                
            except Exception as e:
                db.rollback()
                raise
            finally:
                db.close()
        
        try:
            return self._retry_on_lock(_store_operation)
        except Exception as e:
            logger.error(
                f"[CaptchaStorage] [STORE] Failed to store captcha {captcha_id} after all retries: {e}"
            )
            raise
    
    def get(self, captcha_id: str) -> Optional[Dict]:
        """
        Get a captcha code.
        
        Automatically retries on database lock errors (transient locks).
        
        Args:
            captcha_id: Unique captcha identifier
            
        Returns:
            Dict with 'code' and 'expires' keys, or None if not found/expired
        """
        def _get_operation():
            db = self._get_db()
            try:
                captcha = db.query(Captcha).filter(Captcha.id == captcha_id).first()
                
                if not captcha:
                    return None
                
                # Check expiration
                if datetime.utcnow() > captcha.expires_at:
                    # Expired - delete it
                    db.delete(captcha)
                    db.commit()
                    return None
                
                return {
                    "code": captcha.code,
                    "expires": captcha.expires_at.timestamp()
                }
                
            except Exception as e:
                raise
            finally:
                db.close()
        
        try:
            return self._retry_on_lock(_get_operation)
        except Exception as e:
            logger.error(f"[CaptchaStorage] [GET] Failed to get captcha after retries: {e}")
            return None
    
    def verify_and_remove(self, captcha_id: str, user_code: str) -> Tuple[bool, Optional[str]]:
        """
        Verify captcha code and remove it (one-time use).
        
        Automatically retries on database lock errors (transient locks).
        
        Args:
            captcha_id: Unique captcha identifier
            user_code: User-provided captcha code
            
        Returns:
            Tuple of (is_valid: bool, error_reason: Optional[str])
            error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
        """
        def _verify_operation():
            db = self._get_db()
            try:
                captcha = db.query(Captcha).filter(Captcha.id == captcha_id).first()
                
                if not captcha:
                    logger.warning(f"[CaptchaStorage] [VERIFY] Captcha not found: {captcha_id}")
                    return False, "not_found"
                
                # Check expiration
                if datetime.utcnow() > captcha.expires_at:
                    db.delete(captcha)
                    db.commit()
                    logger.warning(f"[CaptchaStorage] [VERIFY] Captcha expired: {captcha_id}")
                    return False, "expired"
                
                # Verify code (case-insensitive)
                is_valid = captcha.code.upper() == user_code.upper()
                
                # Delete captcha (one-time use) regardless of result
                db.delete(captcha)
                db.commit()
                
                if not is_valid:
                    logger.warning(
                        f"[CaptchaStorage] [VERIFY] Captcha verification failed: {captcha_id} "
                        f"(expected: {captcha.code}, got: {user_code})"
                    )
                    return False, "incorrect"
                else:
                    logger.debug(f"[CaptchaStorage] [VERIFY] Captcha verified successfully: {captcha_id}")
                    return True, None
                
            except Exception as e:
                db.rollback()
                raise
            finally:
                db.close()
        
        try:
            return self._retry_on_lock(_verify_operation)
        except Exception as e:
            error_msg = str(e).lower()
            is_db_lock = "database is locked" in error_msg or "database locked" in error_msg
            
            if is_db_lock:
                logger.error(
                    f"[CaptchaStorage] [VERIFY] Database lock after all retries: {captcha_id}. Error: {str(e)[:200]}"
                )
                return False, "database_locked"
            else:
                logger.error(
                    f"[CaptchaStorage] [VERIFY] Failed to verify captcha {captcha_id} after all retries: {e}"
                )
                return False, "error"
    
    def remove(self, captcha_id: str):
        """
        Remove a captcha code.
        
        Args:
            captcha_id: Unique captcha identifier
        """
        db = self._get_db()
        try:
            captcha = db.query(Captcha).filter(Captcha.id == captcha_id).first()
            if captcha:
                db.delete(captcha)
                db.commit()
                logger.debug(f"[CaptchaStorage] Removed captcha: {captcha_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"[CaptchaStorage] Failed to remove captcha: {e}")
        finally:
            db.close()
    
    def cleanup_expired(self):
        """
        Clean up expired captchas (maintenance operation).
        
        Called periodically to remove old entries.
        """
        db = self._get_db()
        try:
            now = datetime.utcnow()
            deleted = db.query(Captcha).filter(Captcha.expires_at < now).delete()
            db.commit()
            
            if deleted > 0:
                logger.debug(f"[CaptchaStorage] Cleaned up {deleted} expired captchas")
                
        except Exception as e:
            db.rollback()
            logger.error(f"[CaptchaStorage] Failed to cleanup expired captchas: {e}")
        finally:
            db.close()


# Global singleton instance
_captcha_storage: Optional[SQLiteCaptchaStorage] = None


def get_captcha_storage() -> SQLiteCaptchaStorage:
    """Get the global captcha storage instance."""
    global _captcha_storage
    if _captcha_storage is None:
        _captcha_storage = SQLiteCaptchaStorage()
    return _captcha_storage


async def start_captcha_cleanup_scheduler(interval_minutes: int = 10):
    """
    Run captcha cleanup task periodically in background.
    
    Removes expired captchas from the database to prevent table bloat.
    Default interval: every 10 minutes.
    
    Args:
        interval_minutes: How often to run cleanup (default: 10 minutes)
    """
    interval_seconds = interval_minutes * 60
    storage = get_captcha_storage()
    
    logger.info(f"[CaptchaStorage] Starting cleanup scheduler (every {interval_minutes} min)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            # Run cleanup in thread pool to avoid blocking
            await asyncio.to_thread(storage.cleanup_expired)
        except asyncio.CancelledError:
            logger.info("[CaptchaStorage] Cleanup scheduler stopped")
            break
        except Exception as e:
            logger.error(f"[CaptchaStorage] Cleanup scheduler error: {e}", exc_info=True)
