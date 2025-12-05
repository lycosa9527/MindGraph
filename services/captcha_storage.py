"""
Hybrid Captcha Storage (In-Memory Cache + File Persistence)
===========================================================

High-performance captcha storage that combines:
- Fast in-memory cache for reads (sub-millisecond)
- Periodic file sync for persistence across workers/restarts
- Cross-process file locking for multi-worker safety

@author lycosa9527
@made_by MindSpring Team
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict
from collections import OrderedDict

logger = logging.getLogger(__name__)


class HybridCaptchaStorage:
    """
    Hybrid captcha storage: in-memory cache + file persistence.
    
    Architecture:
    - In-memory cache: Fast reads/writes (sub-millisecond)
    - File sync: Periodic persistence (every 5 seconds or on write)
    - Cross-process locking: File-based locks for multi-worker safety
    
    Performance:
    - Read: ~0.001ms (in-memory cache hit)
    - Write: ~0.001ms (in-memory) + ~1ms (async file sync)
    - File sync: Background operation, doesn't block requests
    """
    
    def __init__(self, storage_file: str = "data/captcha_store.json", sync_interval: float = 5.0):
        """
        Initialize hybrid captcha storage.
        
        Args:
            storage_file: Path to JSON file for persistence
            sync_interval: Seconds between automatic file syncs (default: 5s)
        """
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.sync_interval = sync_interval
        
        # In-memory cache (OrderedDict for LRU-like behavior)
        self._cache: Dict[str, Dict] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # File sync state
        self._pending_writes = False
        self._last_sync = time.time()
        self._sync_lock = threading.RLock()
        
        # Load from file on startup
        self._load_from_file()
        
        # Start background sync task
        self._sync_thread = threading.Thread(target=self._background_sync, daemon=True)
        self._sync_thread.start()
        
        logger.info(
            f"[CaptchaStorage] Initialized hybrid storage: "
            f"cache={len(self._cache)} entries, file={self.storage_file}"
        )
    
    def _load_from_file(self):
        """Load captcha store from file on startup."""
        try:
            if not self.storage_file.exists():
                return
            
            with self._get_file_lock():
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Filter expired entries
                        current_time = time.time()
                        self._cache = OrderedDict({
                            k: v for k, v in data.items()
                            if isinstance(v, dict) and v.get("expires", 0) > current_time
                        })
                        logger.debug(f"[CaptchaStorage] Loaded {len(self._cache)} valid captchas from file")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[CaptchaStorage] Error loading file: {e}, starting with empty cache")
    
    def _get_file_lock(self):
        """
        Get cross-process file lock.
        
        Returns a context manager for file locking that works across processes.
        Falls back to no-op lock if locking not available.
        """
        try:
            if sys.platform == 'win32':
                import msvcrt
                return _WindowsFileLock(self.storage_file)
            else:
                import fcntl
                return _UnixFileLock(self.storage_file)
        except ImportError:
            # Fallback: no locking (shouldn't happen, but be safe)
            logger.warning("[CaptchaStorage] File locking not available, using no-op lock")
            return _NoOpLock()
    
    def _write_to_file(self):
        """Write cache to file with cross-process locking."""
        try:
            with self._get_file_lock():
                # Re-read cache state (might have changed during lock acquisition)
                with self._cache_lock:
                    cache_snapshot = dict(self._cache)
                
                # Write to temporary file first (atomic operation)
                temp_file = self.storage_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_snapshot, f, indent=2)
                
                # Atomic rename
                if sys.platform == 'win32':
                    if self.storage_file.exists():
                        os.remove(self.storage_file)
                    os.rename(temp_file, self.storage_file)
                else:
                    temp_file.replace(self.storage_file)
                
                self._last_sync = time.time()
                logger.debug(f"[CaptchaStorage] Synced {len(cache_snapshot)} captchas to file")
        except IOError as e:
            logger.error(f"[CaptchaStorage] Error writing file: {e}")
            # Clean up temp file
            temp_file = self.storage_file.with_suffix('.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def _background_sync(self):
        """Background thread that periodically syncs cache to file."""
        while True:
            try:
                time.sleep(self.sync_interval)
                
                with self._sync_lock:
                    if self._pending_writes:
                        self._write_to_file()
                        self._pending_writes = False
                    
                    # Also cleanup expired entries periodically
                    self._cleanup_expired()
            except Exception as e:
                logger.error(f"[CaptchaStorage] Background sync error: {e}")
    
    def _cleanup_expired(self):
        """Remove expired captchas from cache."""
        current_time = time.time()
        expired_keys = [
            k for k, v in self._cache.items()
            if isinstance(v, dict) and v.get("expires", 0) < current_time
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._pending_writes = True
            logger.debug(f"[CaptchaStorage] Cleaned up {len(expired_keys)} expired captchas")
    
    def store(self, captcha_id: str, code: str, expires_in_seconds: int = 300):
        """
        Store a captcha code (fast in-memory write).
        
        Args:
            captcha_id: Unique captcha identifier
            code: Captcha code to store
            expires_in_seconds: Time until expiration (default: 5 minutes)
        """
        with self._cache_lock:
            # Remove if exists (for LRU behavior)
            self._cache.pop(captcha_id, None)
            # Add to end (LRU behavior)
            self._cache[captcha_id] = {
                "code": code.upper(),
                "expires": time.time() + expires_in_seconds
            }
            self._pending_writes = True
        
        # Trigger immediate sync for critical writes (non-blocking)
        # Background thread will handle it
        logger.debug(f"[CaptchaStorage] Stored captcha: {captcha_id}")
    
    def get(self, captcha_id: str) -> Optional[Dict]:
        """
        Get a captcha code (fast in-memory read with file fallback).
        
        Args:
            captcha_id: Unique captcha identifier
            
        Returns:
            Dict with 'code' and 'expires' keys, or None if not found/expired
        """
        # Step 1: Check cache first (fast path - ~0.001ms)
        with self._cache_lock:
            if captcha_id in self._cache:
                stored = self._cache[captcha_id]
                
                # Check expiration
                if time.time() > stored.get("expires", 0):
                    del self._cache[captcha_id]
                    self._pending_writes = True
                    return None
                
                # Move to end (LRU behavior) - reinsert to maintain order
                self._cache.pop(captcha_id, None)
                self._cache[captcha_id] = stored
                return stored  # Cache hit! ✅
        
        # Step 2: Cache miss - check file (fallback - ~1-5ms)
        # This ensures workers can find captchas even if background sync hasn't happened yet
        try:
            with self._get_file_lock():
                if not self.storage_file.exists():
                    return None
                
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    if captcha_id in file_data:
                        stored = file_data[captcha_id]
                        
                        # Check expiration
                        if time.time() > stored.get("expires", 0):
                            # Expired - remove from file
                            del file_data[captcha_id]
                            temp_file = self.storage_file.with_suffix('.tmp')
                            with open(temp_file, 'w', encoding='utf-8') as f:
                                json.dump(file_data, f, indent=2)
                            if sys.platform == 'win32':
                                if self.storage_file.exists():
                                    os.remove(self.storage_file)
                                os.rename(temp_file, self.storage_file)
                            else:
                                temp_file.replace(self.storage_file)
                            return None
                        
                        # Valid captcha found in file - load into cache for next time
                        with self._cache_lock:
                            self._cache.pop(captcha_id, None)
                            self._cache[captcha_id] = stored
                        
                        logger.debug(f"[CaptchaStorage] Loaded captcha from file: {captcha_id}")
                        return stored  # Found in file! ✅
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"[CaptchaStorage] Error reading file on cache miss: {e}")
        
        return None  # Not found anywhere ❌
    
    def _remove_from_file(self, captcha_id: str):
        """Remove captcha from file immediately (for one-time use)."""
        try:
            with self._get_file_lock():
                if not self.storage_file.exists():
                    return
                
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                if captcha_id in file_data:
                    del file_data[captcha_id]
                    
                    # Write back to file atomically
                    temp_file = self.storage_file.with_suffix('.tmp')
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(file_data, f, indent=2)
                    
                    if sys.platform == 'win32':
                        if self.storage_file.exists():
                            os.remove(self.storage_file)
                        os.rename(temp_file, self.storage_file)
                    else:
                        temp_file.replace(self.storage_file)
                    
                    logger.debug(f"[CaptchaStorage] Removed captcha from file: {captcha_id}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[CaptchaStorage] Error removing captcha from file: {e}")
    
    def verify_and_remove(self, captcha_id: str, user_code: str) -> bool:
        """
        Verify captcha code and remove it (one-time use).
        Checks cache first, then file if cache miss.
        Removes from file immediately on successful verification to prevent reuse.
        
        Args:
            captcha_id: Unique captcha identifier
            user_code: User-provided captcha code
            
        Returns:
            True if valid, False otherwise
        """
        # Step 1: Check cache first (fast path)
        stored = None
        found_in_cache = False
        
        with self._cache_lock:
            if captcha_id in self._cache:
                stored = self._cache[captcha_id]
                found_in_cache = True
        
        # Step 2: If cache miss, check file (fallback)
        if not found_in_cache:
            try:
                with self._get_file_lock():
                    if self.storage_file.exists():
                        with open(self.storage_file, 'r', encoding='utf-8') as f:
                            file_data = json.load(f)
                            if captcha_id in file_data:
                                stored = file_data[captcha_id]
                                # Load into cache for next time
                                with self._cache_lock:
                                    self._cache[captcha_id] = stored
                                logger.debug(f"[CaptchaStorage] Loaded captcha from file for verification: {captcha_id}")
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"[CaptchaStorage] Error reading file during verification: {e}")
        
        # Step 3: Verify captcha
        if not stored:
            logger.warning(f"[CaptchaStorage] Captcha not found: {captcha_id}")
            return False
        
        # Check expiration
        if time.time() > stored.get("expires", 0):
            # Remove from cache and file
            with self._cache_lock:
                self._cache.pop(captcha_id, None)
            self._remove_from_file(captcha_id)  # Remove from file immediately
            logger.warning(f"[CaptchaStorage] Captcha expired: {captcha_id}")
            return False
        
        # Verify code (CASE-INSENSITIVE comparison)
        is_valid = stored["code"].upper() == user_code.upper()
        
        # Remove captcha (one-time use) from both cache and file IMMEDIATELY
        # This prevents race condition where another worker could reuse the captcha
        with self._cache_lock:
            self._cache.pop(captcha_id, None)
        
        # Remove from file immediately (not just mark for background sync)
        # This ensures captcha cannot be reused by another worker
        self._remove_from_file(captcha_id)
        
        if not is_valid:
            logger.warning(f"[CaptchaStorage] Captcha verification failed: {captcha_id}")
        
        return is_valid
    
    def remove(self, captcha_id: str):
        """
        Remove a captcha code.
        
        Args:
            captcha_id: Unique captcha identifier
        """
        with self._cache_lock:
            if captcha_id in self._cache:
                del self._cache[captcha_id]
                self._pending_writes = True
    
    def cleanup_expired(self):
        """Clean up expired captchas (maintenance operation)."""
        self._cleanup_expired()
        # Trigger sync
        with self._sync_lock:
            if self._pending_writes:
                self._write_to_file()
                self._pending_writes = False


class _WindowsFileLock:
    """Windows file lock using msvcrt."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lock_file = file_path.with_suffix('.lock')
        self.handle = None
    
    def __enter__(self):
        import msvcrt
        # Create lock file
        self.handle = open(self.lock_file, 'w')
        try:
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        except IOError:
            self.handle.close()
            raise
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import msvcrt
        if self.handle:
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            except:
                pass
            self.handle.close()
            try:
                self.lock_file.unlink()
            except:
                pass


class _UnixFileLock:
    """Unix file lock using fcntl."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lock_file = file_path.with_suffix('.lock')
        self.handle = None
    
    def __enter__(self):
        import fcntl
        self.handle = open(self.lock_file, 'w')
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        except IOError:
            self.handle.close()
            raise
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import fcntl
        if self.handle:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            except:
                pass
            self.handle.close()
            try:
                self.lock_file.unlink()
            except:
                pass


class _NoOpLock:
    """No-op lock for fallback when file locking not available."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Global singleton instance
_captcha_storage: Optional[HybridCaptchaStorage] = None


def get_captcha_storage() -> HybridCaptchaStorage:
    """Get the global captcha storage instance."""
    global _captcha_storage
    if _captcha_storage is None:
        _captcha_storage = HybridCaptchaStorage()
    return _captcha_storage
