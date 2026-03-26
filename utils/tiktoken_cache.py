"""
Tiktoken encoding file caching utility.

If ``resources/tiktoken_encodings/cl100k_base.tiktoken`` is shipped with the app,
that directory is used and no network access is required.

Otherwise downloads and caches tiktoken encoding files locally to avoid repeated
downloads from Azure Blob Storage on application startup. Checks for new versions
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

# Bundled encodings (project root) — if present, used instead of any download
_BUNDLED_ENCODING_NAMES = ("cl100k_base",)


def _bundled_tiktoken_cache_dir() -> Path | None:
    """
    Return the directory containing bundled .tiktoken files if all required
    encodings are present and non-empty. Otherwise return None.
    """
    project_root = Path(__file__).resolve().parent.parent
    bundled_dir = project_root / "resources" / "tiktoken_encodings"
    try:
        for name in _BUNDLED_ENCODING_NAMES:
            path = bundled_dir / f"{name}.tiktoken"
            if not path.is_file() or path.stat().st_size == 0:
                return None
    except OSError:
        return None
    return bundled_dir


def _default_cache_dir_path() -> Path:
    """Project-root path for the runtime tiktoken cache directory."""
    return Path(__file__).resolve().parent.parent / DEFAULT_CACHE_DIR


def _set_tiktoken_cache_dir_env(cache_dir: Path) -> None:
    """Point tiktoken at the given cache directory."""
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache_dir.resolve())


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
        redis_unavailable = (
            not is_redis_available
            or not callable(is_redis_available)
            or not is_redis_available()
        )
        if redis_unavailable:
            return True

        if not get_redis or not callable(get_redis):
            return True
        redis = get_redis()
        if not redis:
            return True

        worker_lock_id = _LockIdManager.get_lock_id()
        acquired = redis.set(
            TIKTOKEN_CACHE_LOCK_KEY,
            worker_lock_id,
            nx=True,
            ex=TIKTOKEN_CACHE_LOCK_TTL
        )

        if acquired:
            try:
                logger.debug(
                    "[TiktokenCache] Lock acquired for cache check (id=%s)",
                    worker_lock_id
                )
            except Exception:  # pylint: disable=broad-except
                pass
            return True

        try:
            logger.debug("[TiktokenCache] Another worker is checking cache, skipping")
        except Exception:  # pylint: disable=broad-except
            pass
        return False

    except Exception:  # pylint: disable=broad-except
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


def _log_http_debug_cached_up_to_date(encoding_name: str, encoding_file: Path) -> None:
    """If HTTP_DEBUG is on, log that an encoding file is already current."""
    if os.getenv('HTTP_DEBUG', '').lower() not in ('1', 'true', 'yes'):
        return
    try:
        logger.debug(
            "Tiktoken encoding %s already cached and up-to-date at %s",
            encoding_name, encoding_file
        )
    except Exception:  # pylint: disable=broad-except
        pass


def _encoding_requires_download(
    cache_dir: Path,
    encoding_name: str,
    url: str,
) -> bool:
    """
    Decide whether to download or refresh the encoding file.

    Returns:
        True if a download should run, False if the existing file is enough.
    """
    encoding_file = cache_dir / f"{encoding_name}.tiktoken"
    metadata_file = cache_dir / f"{encoding_name}.metadata.json"

    if not encoding_file.exists() or encoding_file.stat().st_size == 0:
        logger.debug("[Startup] Downloading tiktoken encoding %s...", encoding_name)
        return True

    try:
        needs_update = _check_if_update_needed(url, metadata_file)
        if not needs_update:
            _log_http_debug_cached_up_to_date(encoding_name, encoding_file)
            return False

        logger.debug(
            "[Startup] New version of tiktoken encoding %s available, updating...",
            encoding_name
        )
        return True
    except Exception as network_error:  # pylint: disable=broad-except
        logger.debug(
            "[Startup] Network check failed for tiktoken encoding %s, "
            "using existing cache: %s",
            encoding_name, network_error
        )
        return False


def _sync_one_encoding_if_needed(
    cache_dir: Path,
    encoding_name: str,
    url: str,
) -> None:
    """Download or refresh one encoding file under cache_dir when required."""
    encoding_file = cache_dir / f"{encoding_name}.tiktoken"
    metadata_file = cache_dir / f"{encoding_name}.metadata.json"

    try:
        if not _encoding_requires_download(cache_dir, encoding_name, url):
            return

        _download_encoding_file(url, encoding_file, metadata_file)
        file_size_mb = encoding_file.stat().st_size / (1024 * 1024)
        logger.debug(
            "[Startup] OK Cached tiktoken encoding %s (%.2f MB) at %s",
            encoding_name, file_size_mb, encoding_file
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "[Startup] Failed to download tiktoken encoding %s: %s. "
            "Tiktoken will download it automatically on first use.",
            encoding_name, exc
        )


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
    bundled_dir = _bundled_tiktoken_cache_dir()
    if bundled_dir is not None:
        _set_tiktoken_cache_dir_env(bundled_dir)
        logger.debug(
            "[Startup] Using bundled tiktoken encodings at %s (no network)",
            bundled_dir,
        )
        return

    if _is_tiktoken_cache_check_in_progress():
        _set_tiktoken_cache_dir_env(_default_cache_dir_path())
        return

    if not _acquire_tiktoken_cache_lock():
        _set_tiktoken_cache_dir_env(_default_cache_dir_path())
        return

    try:
        cache_dir = _default_cache_dir_path()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("[Startup] Could not create tiktoken cache directory: %s", exc)
            return

        _set_tiktoken_cache_dir_env(cache_dir)

        for encoding_name, url in TIKTOKEN_ENCODINGS.items():
            _sync_one_encoding_if_needed(cache_dir, encoding_name, url)
    finally:
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
