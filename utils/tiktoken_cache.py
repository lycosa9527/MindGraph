"""
Tiktoken encoding file caching utility.

Downloads and caches tiktoken encoding files locally to avoid repeated downloads
from Azure Blob Storage on every application startup. Checks for new versions
using HTTP headers (ETag/Last-Modified) and only downloads when needed.
"""

import os
import json
import logging
import uuid
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime
import httpx

logger = logging.getLogger(__name__)

# Lazy import for Redis services (may not be available)
try:
    from services.redis.redis_client import get_redis, is_redis_available
except ImportError:
    get_redis = None
    is_redis_available = None

# Tiktoken encoding files to cache
TIKTOKEN_ENCODINGS = {
    "cl100k_base": "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
}

# Default cache directory (relative to project root)
DEFAULT_CACHE_DIR = Path("storage/tiktoken_cache")

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Multiple Uvicorn workers all call ensure_tiktoken_cache() during startup,
# causing redundant network requests and potential race conditions.
#
# Solution: Redis-based distributed lock ensures only ONE worker checks/updates cache.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: tiktoken:cache:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 60 seconds (enough for cache check/download, auto-release if worker crashes)
# ============================================================================

TIKTOKEN_CACHE_LOCK_KEY = "tiktoken:cache:lock"
TIKTOKEN_CACHE_LOCK_TTL = 60  # 60 seconds - enough for cache check/download


class _LockIdManager:
    """Manages the worker lock ID to avoid global variables."""
    _lock_id = None

    @classmethod
    def get_lock_id(cls) -> str:
        """Get or generate the lock ID for this worker."""
        if cls._lock_id is None:
            cls._lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        return cls._lock_id


def _is_tiktoken_cache_check_in_progress() -> bool:
    """
    Check if tiktoken cache check is already in progress by another worker.

    Returns:
        True if lock exists (another worker is checking), False otherwise
    """
    try:
        if not is_redis_available or not callable(is_redis_available):
            return False
        if not is_redis_available():
            return False

        if not get_redis or not callable(get_redis):
            return False
        redis = get_redis()
        if not redis:
            return False

        return redis.exists(TIKTOKEN_CACHE_LOCK_KEY) > 0
    except Exception:  # pylint: disable=broad-except
        # If Redis is not available or not initialized yet, assume single worker mode
        return False


def _acquire_tiktoken_cache_lock() -> bool:
    """
    Attempt to acquire the tiktoken cache lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should check/update cache)
        False if lock held by another worker
    """
    try:
        if not is_redis_available or not callable(is_redis_available):
            # No Redis = single worker mode, proceed
            return True
        if not is_redis_available():
            # No Redis = single worker mode, proceed
            return True

        if not get_redis or not callable(get_redis):
            return True  # Fallback to single worker mode
        redis = get_redis()
        if not redis:
            return True  # Fallback to single worker mode

        # Generate unique ID for this worker
        worker_lock_id = _LockIdManager.get_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            TIKTOKEN_CACHE_LOCK_KEY,
            worker_lock_id,
            nx=True,  # Only set if not exists
            ex=TIKTOKEN_CACHE_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            try:
                logger.debug(
                    "[TiktokenCache] Lock acquired for cache check (id=%s)",
                    worker_lock_id
                )
            except Exception:  # pylint: disable=broad-except
                pass  # Logging not initialized yet
            return True
        else:
            # Lock held by another worker
            try:
                logger.debug("[TiktokenCache] Another worker is checking cache, skipping")
            except Exception:  # pylint: disable=broad-except
                pass  # Logging not initialized yet
            return False

    except Exception:  # pylint: disable=broad-except
        # If Redis is not available or not initialized yet, assume single worker mode
        return True


def _release_tiktoken_cache_lock() -> None:
    """Release the tiktoken cache lock if held by this worker."""
    try:
        if not is_redis_available or not callable(is_redis_available):
            return
        if not is_redis_available():
            return

        if not get_redis or not callable(get_redis):
            return
        redis = get_redis()
        if not redis:
            return

        worker_lock_id = _LockIdManager.get_lock_id()

        # Lua script: Only delete if lock value matches our lock_id
        # This ensures we only release our own lock
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        redis.eval(lua_script, 1, TIKTOKEN_CACHE_LOCK_KEY, worker_lock_id)
    except Exception:  # pylint: disable=broad-except
        # Ignore errors during lock release (non-critical)
        pass


def ensure_tiktoken_cache():
    """
    Ensure tiktoken encoding files are cached locally.

    Sets TIKTOKEN_CACHE_DIR environment variable and downloads encoding files
    if they don't exist locally or if a new version is available.

    Checks for new versions using HTTP HEAD requests with ETag/Last-Modified headers
    to avoid unnecessary downloads.

    Uses Redis distributed lock to ensure only ONE worker checks/updates cache
    across all workers in multi-worker setups.

    This should be called early in application startup, before any tiktoken imports.
    Network failures are handled gracefully - if the file exists locally, it will be used.
    """
    # Check if another worker is already checking/updating cache
    # This avoids unnecessary lock acquisition attempts
    if _is_tiktoken_cache_check_in_progress():
        # Another worker is checking - silently skip (no logging to reduce noise)
        # Still set TIKTOKEN_CACHE_DIR so this worker can use the cache
        project_root = Path(__file__).parent.parent
        cache_dir = project_root / DEFAULT_CACHE_DIR
        cache_dir_str = str(cache_dir.absolute())
        os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir_str
        return

    # Try to acquire lock - only one worker should check/update cache
    if not _acquire_tiktoken_cache_lock():
        # Another worker acquired the lock - silently skip (no logging to reduce noise)
        # Still set TIKTOKEN_CACHE_DIR so this worker can use the cache
        project_root = Path(__file__).parent.parent
        cache_dir = project_root / DEFAULT_CACHE_DIR
        cache_dir_str = str(cache_dir.absolute())
        os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir_str
        return

    # This worker acquired the lock - proceed with cache check/update
    try:
        # Get project root directory (parent of utils directory)
        project_root = Path(__file__).parent.parent
        cache_dir = project_root / DEFAULT_CACHE_DIR

        # Create cache directory if it doesn't exist
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:  # pylint: disable=broad-except
            logger.debug("[Startup] Could not create tiktoken cache directory: %s", e)
            return  # Lock will be released in finally block

        # Set environment variable for tiktoken to use this cache directory
        cache_dir_str = str(cache_dir.absolute())
        os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir_str

        # Check and download encoding files if needed
        for encoding_name, url in TIKTOKEN_ENCODINGS.items():
            encoding_file = cache_dir / f"{encoding_name}.tiktoken"
            metadata_file = cache_dir / f"{encoding_name}.metadata.json"

            try:
                if encoding_file.exists() and encoding_file.stat().st_size > 0:
                    # File exists - try to check for updates, but don't fail if network is unavailable
                    try:
                        needs_update = _check_if_update_needed(url, metadata_file)

                        if not needs_update:
                            # File is up-to-date - no logging needed to reduce startup noise
                            # Only log if HTTP_DEBUG is enabled
                            try:
                                if os.getenv('HTTP_DEBUG', '').lower() in ('1', 'true', 'yes'):
                                    logger.debug(
                                        "Tiktoken encoding %s already cached and up-to-date at %s",
                                        encoding_name, encoding_file
                                    )
                            except Exception:  # pylint: disable=broad-except
                                pass  # Logging not initialized yet, skip
                            continue

                        # New version available, download it
                        logger.debug(
                            "[Startup] New version of tiktoken encoding %s available, updating...",
                            encoding_name
                        )
                    except Exception as network_error:  # pylint: disable=broad-except
                        # Network check failed - use existing file (conservative approach)
                        logger.debug(
                            "[Startup] Network check failed for %s, using existing cache: %s",
                            encoding_name, network_error
                        )
                        try:
                            logger.debug(
                                "Network check failed for tiktoken encoding %s, "
                                "using existing cache: %s",
                                encoding_name, network_error
                            )
                        except Exception:  # pylint: disable=broad-except
                            pass
                        continue
                else:
                    # File doesn't exist, download it
                    logger.debug("[Startup] Downloading tiktoken encoding %s...", encoding_name)

                _download_encoding_file(url, encoding_file, metadata_file)
                file_size_mb = encoding_file.stat().st_size / (1024 * 1024)
                logger.debug(
                    "[Startup] OK Cached tiktoken encoding %s (%.2f MB) at %s",
                    encoding_name, file_size_mb, encoding_file
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "[Startup] Failed to download tiktoken encoding %s: %s. "
                    "Tiktoken will download it automatically on first use.",
                    encoding_name, e
                )
    finally:
        # Always release the lock when done
        _release_tiktoken_cache_lock()


def _check_if_update_needed(url: str, metadata_file: Path) -> bool:
    """
    Check if a cached file needs to be updated by comparing HTTP headers.

    Args:
        url: URL to check
        metadata_file: Path to metadata file storing ETag/Last-Modified

    Returns:
        True if update is needed, False otherwise

    Raises:
        Exception: If network request fails (caller should handle gracefully)
    """
    if not metadata_file.exists():
        return True

    # Load cached metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        cached_metadata = json.load(f)

    cached_etag = cached_metadata.get('etag')
    cached_last_modified = cached_metadata.get('last_modified')

    # Make HEAD request to check current version with shorter timeout
    # Use 5 seconds timeout to avoid hanging during startup
    timeout_config = httpx.Timeout(5.0, connect=5.0, read=5.0, write=5.0, pool=5.0)
    with httpx.Client(timeout=timeout_config) as client:
        response = client.head(url, follow_redirects=True)
        response.raise_for_status()

        server_etag = response.headers.get('ETag')
        server_last_modified = response.headers.get('Last-Modified')

        # If server provides ETag, use it for comparison (most reliable)
        if server_etag and cached_etag:
            return server_etag != cached_etag

        # Fall back to Last-Modified comparison
        if server_last_modified and cached_last_modified:
            try:
                server_time = parsedate_to_datetime(server_last_modified)
                cached_time = parsedate_to_datetime(cached_last_modified)
                if server_time and cached_time:
                    return server_time > cached_time
            except (ValueError, TypeError, AttributeError):
                # If parsing fails, assume update needed
                return True

        # If no headers available, assume no update needed (conservative)
        return False


def _download_encoding_file(url: str, output_path: Path, metadata_file: Path) -> None:
    """
    Download a tiktoken encoding file from URL to local path and save metadata.

    Args:
        url: URL to download from
        output_path: Local path to save the file
        metadata_file: Path to save metadata (ETag/Last-Modified)

    Raises:
        Exception: If download fails (caller should handle gracefully)
    """
    # Use sync httpx client for simple download with timeout
    # Use shorter timeout to avoid hanging during startup
    timeout_config = httpx.Timeout(15.0, connect=10.0, read=15.0, write=10.0, pool=10.0)
    with httpx.Client(timeout=timeout_config, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

        # Write to file
        output_path.write_bytes(response.content)

        # Verify file was written
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise IOError(f"Failed to write encoding file to {output_path}")

        # Save metadata for version checking
        metadata = {
            'etag': response.headers.get('ETag'),
            'last_modified': response.headers.get('Last-Modified'),
            'content_length': response.headers.get('Content-Length'),
            'downloaded_at': datetime.utcnow().isoformat() + 'Z'
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
