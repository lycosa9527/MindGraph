"""
Aliyun Object Storage Service (OSS) client helpers.

Auth: OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET for a RAM user scoped to one bucket.
Bucket: OSS_BUCKET / OSS_REGION. OSS_ENDPOINT overrides the public endpoint.
App objects use OSS_KEY_PREFIX (local dev: ``dev_roy/backups``).

Used by the daily backup mirror. VibeFlow reads a different prefix in the same bucket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import oss2
    from oss2.exceptions import OssError
except ImportError:
    oss2 = None
    OssError = None


class _OssBucketHolder:
    """Process-wide Bucket cache."""

    __slots__ = ("bucket", "signature")

    def __init__(self) -> None:
        self.bucket: Optional[Any] = None
        self.signature: str = ""


_OSS_BUCKET_HOLDER = _OssBucketHolder()


def _oss_fetch_errors() -> tuple:
    errors: List[type] = [OSError, TimeoutError, RuntimeError, ValueError]
    if OssError is not None:
        errors.insert(0, OssError)
    return tuple(errors)


def oss_sdk_available() -> bool:
    """True when oss2 is importable."""
    return oss2 is not None


def oss_access_key_id() -> str:
    """RAM AccessKey ID."""
    return os.getenv("OSS_ACCESS_KEY_ID", "").strip()


def oss_access_key_secret() -> str:
    """RAM AccessKey secret."""
    return os.getenv("OSS_ACCESS_KEY_SECRET", "").strip()


def oss_bucket_name() -> str:
    """Configured bucket name."""
    return os.getenv("OSS_BUCKET", "").strip()


def oss_region() -> str:
    """Bucket region, for example cn-beijing."""
    return os.getenv("OSS_REGION", "cn-beijing").strip()


def oss_endpoint() -> str:
    """Public HTTPS endpoint for the bucket region."""
    configured = os.getenv("OSS_ENDPOINT", "").strip()
    if configured:
        return configured
    region = oss_region()
    if not region:
        return ""
    return f"https://oss-{region}.aliyuncs.com"


def normalized_oss_prefix(prefix: Optional[str] = None) -> str:
    """Normalize a key prefix without a trailing slash."""
    raw = os.getenv("OSS_KEY_PREFIX", "") if prefix is None else prefix
    return raw.strip().strip("/")


def oss_object_key(relative_key: str, prefix: Optional[str] = None) -> str:
    """Build a full object key under the configured prefix."""
    rel = relative_key.lstrip("/")
    base = normalized_oss_prefix(prefix)
    if not base:
        return rel
    return f"{base}/{rel}"


def oss_credentials_configured() -> bool:
    """True when the RAM key, bucket, and region are set."""
    return bool(oss_access_key_id() and oss_access_key_secret() and oss_bucket_name() and oss_region())


def get_oss_bucket() -> Optional[Any]:
    """Return a configured oss2 Bucket, or None when the SDK or credentials are missing."""
    if not oss_sdk_available() or oss2 is None:
        return None
    if not oss_credentials_configured():
        return None
    endpoint = oss_endpoint()
    if not endpoint:
        return None
    signature = "|".join((oss_access_key_id(), oss_bucket_name(), oss_region(), endpoint))
    if _OSS_BUCKET_HOLDER.bucket is not None and _OSS_BUCKET_HOLDER.signature == signature:
        return _OSS_BUCKET_HOLDER.bucket
    auth = oss2.Auth(oss_access_key_id(), oss_access_key_secret())
    bucket = oss2.Bucket(auth, endpoint, oss_bucket_name())
    _OSS_BUCKET_HOLDER.bucket = bucket
    _OSS_BUCKET_HOLDER.signature = signature
    return bucket


def _retry_oss_call(operation: str, func: Any, max_retries: int = 3) -> Any:
    last_exc: Optional[Exception] = None
    fetch_errors = _oss_fetch_errors()
    for attempt in range(max_retries):
        try:
            return func()
        except fetch_errors as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                raise
            delay = min(5.0 * (2**attempt), 30.0)
            logger.warning(
                "[OSS] %s attempt %s/%s failed: %s. Retrying in %.1fs...",
                operation,
                attempt + 1,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"OSS {operation} failed")


def upload_file(
    local_path: Path,
    object_key: str,
    *,
    max_retries: int = 3,
    log_prefix: str = "[OSS]",
) -> bool:
    """Upload a local file. Files over 10 MB use multipart upload."""
    bucket = get_oss_bucket()
    sdk = oss2
    if bucket is None or sdk is None:
        logger.error("%s SDK missing or credentials not configured", log_prefix)
        return False
    if not local_path.is_file():
        logger.error("%s Local file does not exist: %s", log_prefix, local_path)
        return False
    size_mb = local_path.stat().st_size / (1024 * 1024)
    store_dir = Path(tempfile.gettempdir()) / "mindgraph-oss-upload"
    store_dir.mkdir(parents=True, exist_ok=True)

    def _do_upload() -> Any:
        return sdk.resumable_upload(
            bucket,
            object_key,
            str(local_path),
            store=sdk.ResumableStore(root=str(store_dir)),
            multipart_threshold=10 * 1024 * 1024,
            part_size=10 * 1024 * 1024,
            num_threads=4,
        )

    try:
        logger.info(
            "%s Uploading bucket=%s key=%s size=%.2f MB",
            log_prefix,
            oss_bucket_name(),
            object_key,
            size_mb,
        )
        _retry_oss_call("upload", _do_upload, max_retries=max_retries)
        return True
    except _oss_fetch_errors() as exc:
        logger.error("%s Upload failed key=%s: %s", log_prefix, object_key, exc, exc_info=True)
        return False


def delete_object(object_key: str, *, log_prefix: str = "[OSS]") -> bool:
    """Delete one object. Missing keys count as success."""
    bucket = get_oss_bucket()
    if bucket is None:
        return False
    try:
        bucket.delete_object(object_key)
        return True
    except _oss_fetch_errors() as exc:
        logger.warning("%s delete_object failed key=%s: %s", log_prefix, object_key, exc)
        return False


def head_object(object_key: str) -> Optional[Dict[str, Any]]:
    """Return size and etag, or None when the object is missing or the client is down."""
    bucket = get_oss_bucket()
    if bucket is None:
        return None
    try:
        meta = bucket.head_object(object_key)
    except _oss_fetch_errors() as exc:
        status = getattr(exc, "status", None)
        if status == 404:
            return None
        logger.warning("[OSS] head_object failed key=%s: %s", object_key, exc)
        return None
    return {
        "key": object_key,
        "size": int(getattr(meta, "content_length", 0) or 0),
        "etag": getattr(meta, "etag", None),
    }


def list_prefix(
    prefix: str,
    *,
    suffix_filter: Optional[str] = None,
    contains_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List objects under prefix as {key, size, last_modified, filename}."""
    bucket = get_oss_bucket()
    if bucket is None or oss2 is None:
        return []
    normalized = prefix.strip().strip("/")
    list_prefix_value = f"{normalized}/" if normalized else ""
    results: List[Dict[str, Any]] = []
    try:
        for obj in oss2.ObjectIterator(bucket, prefix=list_prefix_value):
            obj_key = str(obj.key)
            filename = obj_key.rsplit("/", 1)[-1]
            if suffix_filter and not obj_key.endswith(suffix_filter):
                continue
            if contains_filter and contains_filter not in obj_key:
                continue
            modified = datetime.fromtimestamp(int(obj.last_modified), tz=timezone.utc).replace(tzinfo=None)
            results.append(
                {
                    "key": obj_key,
                    "size": int(obj.size),
                    "last_modified": modified,
                    "filename": filename,
                }
            )
    except _oss_fetch_errors() as exc:
        logger.error("[OSS] list_objects failed prefix=%s: %s", normalized, exc)
        return []
    return results
