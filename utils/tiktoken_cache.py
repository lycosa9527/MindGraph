"""
Tiktoken encoding file caching utility.

Downloads and caches tiktoken encoding files locally to avoid repeated downloads
from Azure Blob Storage on every application startup. Checks for new versions
using HTTP headers (ETag/Last-Modified) and only downloads when needed.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime
import httpx

logger = logging.getLogger(__name__)

# Tiktoken encoding files to cache
TIKTOKEN_ENCODINGS = {
    "cl100k_base": "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
}

# Default cache directory (relative to project root)
DEFAULT_CACHE_DIR = Path("storage/tiktoken_cache")


def ensure_tiktoken_cache():
    """
    Ensure tiktoken encoding files are cached locally.
    
    Sets TIKTOKEN_CACHE_DIR environment variable and downloads encoding files
    if they don't exist locally or if a new version is available.
    
    Checks for new versions using HTTP HEAD requests with ETag/Last-Modified headers
    to avoid unnecessary downloads.
    
    This should be called early in application startup, before any tiktoken imports.
    """
    # Get project root directory (parent of utils directory)
    project_root = Path(__file__).parent.parent
    cache_dir = project_root / DEFAULT_CACHE_DIR
    
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Set environment variable for tiktoken to use this cache directory
    cache_dir_str = str(cache_dir.absolute())
    os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir_str
    
    # Check and download encoding files if needed
    for encoding_name, url in TIKTOKEN_ENCODINGS.items():
        encoding_file = cache_dir / f"{encoding_name}.tiktoken"
        metadata_file = cache_dir / f"{encoding_name}.metadata.json"
        
        try:
            if encoding_file.exists():
                # Check if new version is available
                needs_update = _check_if_update_needed(url, metadata_file)
                
                if not needs_update:
                    # Use print for early startup (logging may not be initialized)
                    try:
                        logger.debug(
                            "Tiktoken encoding %s already cached and up-to-date at %s",
                            encoding_name, encoding_file
                        )
                    except Exception:  # pylint: disable=broad-except
                        pass  # Logging not initialized yet, skip
                    continue
                
                # New version available, download it
                print(f"[Startup] New version of tiktoken encoding {encoding_name} available, updating...")
            else:
                # File doesn't exist, download it
                print(f"[Startup] Downloading tiktoken encoding {encoding_name}...")
            
            _download_encoding_file(url, encoding_file, metadata_file)
            file_size_mb = encoding_file.stat().st_size / (1024 * 1024)
            print(f"[Startup] OK Cached tiktoken encoding {encoding_name} ({file_size_mb:.2f} MB) at {encoding_file}")
            try:
                logger.info("Successfully cached tiktoken encoding %s at %s", encoding_name, encoding_file)
            except Exception:  # pylint: disable=broad-except
                pass  # Logging not initialized yet, skip
        except Exception as e:  # pylint: disable=broad-except
            # Use print for early startup warnings
            print(f"[Startup] Warning: Failed to download tiktoken encoding {encoding_name}: {e}")
            print(f"[Startup] Tiktoken will download it automatically on first use.")
            try:
                logger.warning(
                    "Failed to download tiktoken encoding %s: %s. "
                    "Tiktoken will download it automatically on first use.",
                    encoding_name, e
                )
            except Exception:  # pylint: disable=broad-except
                pass  # Logging not initialized yet, skip


def _check_if_update_needed(url: str, metadata_file: Path) -> bool:
    """
    Check if a cached file needs to be updated by comparing HTTP headers.
    
    Args:
        url: URL to check
        metadata_file: Path to metadata file storing ETag/Last-Modified
        
    Returns:
        True if update is needed, False otherwise
    """
    if not metadata_file.exists():
        return True
    
    try:
        # Load cached metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            cached_metadata = json.load(f)
        
        cached_etag = cached_metadata.get('etag')
        cached_last_modified = cached_metadata.get('last_modified')
        
        # Make HEAD request to check current version
        with httpx.Client(timeout=10.0) as client:
            response = client.head(url)
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
    except Exception:  # pylint: disable=broad-except
        # If check fails, assume update needed to be safe
        return True


def _download_encoding_file(url: str, output_path: Path, metadata_file: Path) -> None:
    """
    Download a tiktoken encoding file from URL to local path and save metadata.
    
    Args:
        url: URL to download from
        output_path: Local path to save the file
        metadata_file: Path to save metadata (ETag/Last-Modified)
    """
    # Use sync httpx client for simple download
    with httpx.Client(timeout=30.0) as client:
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
