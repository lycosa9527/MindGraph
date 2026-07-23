"""
Tencent Cloud Object Storage (COS) client helpers.

Auth: reuses TENCENT_SMS_SECRET_ID / TENCENT_SMS_SECRET_KEY (same CAM key as SMS/SES).
Bucket/region: COS_BUCKET / COS_REGION. Feature prefixes: COS_KEY_PREFIX, COS_DOCUMENTS_*,
COS_SHOWCASE_*.

Used by backup scheduler, document summary, Showcase media, and COS mirror sync.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from services.utils.error_types import BACKGROUND_INFRA_ERRORS

try:
    from qcloud_cos import CosConfig, CosS3Client
    from qcloud_cos.cos_exception import CosClientError, CosServiceError
except ImportError:
    CosConfig = None
    CosS3Client = None
    CosClientError = None
    CosServiceError = None

logger = logging.getLogger(__name__)

COS_SECRET_ID = os.getenv("TENCENT_SMS_SECRET_ID", "").strip()
COS_SECRET_KEY = os.getenv("TENCENT_SMS_SECRET_KEY", "").strip()
COS_BUCKET = os.getenv("COS_BUCKET", "").strip()
COS_REGION = os.getenv("COS_REGION", "ap-beijing").strip()
COS_KEY_PREFIX = os.getenv("COS_KEY_PREFIX", "backups/mindgraph").strip()


def cos_exc_call(exc: Exception, method: str, default: str) -> str:
    """Call optional qcloud COS exception method; getattr avoids incomplete stubs."""
    bound = getattr(exc, method, None)
    if not callable(bound):
        return default
    try:
        val = bound()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return default
    return str(val) if val is not None else default


def cos_sdk_available() -> bool:
    """True when cos-python-sdk-v5 is importable."""
    return CosConfig is not None and CosS3Client is not None


def cos_credentials_configured() -> bool:
    """True when secret id/key and bucket are set."""
    return bool(COS_SECRET_ID and COS_SECRET_KEY and COS_BUCKET and COS_REGION)


def cos_browser_csp_sources() -> str:
    """
    CSP host-sources for browser→COS (connect-src / media-src).

    Prefer the exact virtual-hosted-style endpoints for the configured bucket
    and region. Fall back to suffix wildcards when bucket/region are unset
    (local Vite meta / incomplete env).
    """
    bucket = COS_BUCKET.strip()
    region = COS_REGION.strip()
    if bucket and region:
        return f"https://{bucket}.cos.{region}.myqcloud.com https://{bucket}.cos.{region}.tencentcos.cn"
    return "https://*.myqcloud.com https://*.tencentcos.cn"


def normalized_cos_prefix(prefix: Optional[str] = None) -> str:
    """Normalize key prefix without trailing slash."""
    raw = (prefix if prefix is not None else COS_KEY_PREFIX).strip().rstrip("/")
    return raw


def cos_object_key(relative_key: str, prefix: Optional[str] = None) -> str:
    """Build full object key under prefix."""
    rel = relative_key.lstrip("/")
    base = normalized_cos_prefix(prefix)
    if not base:
        return rel
    return f"{base}/{rel}"


def get_cos_client() -> Optional[Any]:
    """Return configured CosS3Client or None if unavailable."""
    if not cos_sdk_available():
        return None
    if not cos_credentials_configured():
        return None
    if CosConfig is None or CosS3Client is None:
        return None
    config = CosConfig(
        Region=COS_REGION,
        SecretId=COS_SECRET_ID,
        SecretKey=COS_SECRET_KEY,
        Scheme="https",
    )
    return CosS3Client(config)


def _is_retryable_cos_error(exc: Exception) -> bool:
    if CosClientError is None or CosServiceError is None:
        return False
    if isinstance(exc, CosServiceError):
        status_code = cos_exc_call(exc, "get_status_code", "")
        error_code = cos_exc_call(exc, "get_error_code", "")
        if status_code and str(status_code).startswith("5"):
            return True
        return error_code in ("SlowDown", "RequestLimitExceeded")
    if isinstance(exc, CosClientError):
        return True
    return False


def _retry_cos_call(operation: str, func: Any, max_retries: int = 3) -> Any:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return func()
        except BACKGROUND_INFRA_ERRORS as exc:
            last_exc = exc
            if not _is_retryable_cos_error(exc) or attempt == max_retries - 1:
                raise
            delay = min(5.0 * (2**attempt), 30.0)
            logger.warning(
                "[COS] %s attempt %s/%s failed: %s. Retrying in %.1fs...",
                operation,
                attempt + 1,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"COS {operation} failed")


def upload_file(
    local_path: Path,
    object_key: str,
    *,
    max_retries: int = 3,
    log_prefix: str = "[COS]",
) -> bool:
    """Upload a local file to COS."""
    client = get_cos_client()
    if client is None:
        logger.error("%s SDK missing or credentials not configured", log_prefix)
        return False
    if not local_path.is_file():
        logger.error("%s Local file does not exist: %s", log_prefix, local_path)
        return False
    size_mb = local_path.stat().st_size / (1024 * 1024)

    def _do_upload() -> dict:
        return client.upload_file(
            Bucket=COS_BUCKET,
            LocalFilePath=str(local_path),
            Key=object_key,
            PartSize=1,
            MAXThread=10,
            EnableMD5=False,
        )

    try:
        logger.info(
            "%s Uploading bucket=%s key=%s size=%.2f MB",
            log_prefix,
            COS_BUCKET,
            object_key,
            size_mb,
        )
        _retry_cos_call("upload", _do_upload, max_retries=max_retries)
        return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("%s Upload failed key=%s: %s", log_prefix, object_key, exc, exc_info=True)
        return False


def upload_bytes(
    data: bytes,
    object_key: str,
    *,
    max_retries: int = 3,
    log_prefix: str = "[COS]",
) -> bool:
    """Upload raw bytes to COS."""
    client = get_cos_client()
    if client is None:
        return False

    def _do_put() -> dict:
        return client.put_object(Bucket=COS_BUCKET, Body=data, Key=object_key)

    try:
        _retry_cos_call("put_object", _do_put, max_retries=max_retries)
        return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("%s put_object failed key=%s: %s", log_prefix, object_key, exc)
        return False


def download_file(
    object_key: str,
    local_path: Path,
    *,
    max_retries: int = 3,
    log_prefix: str = "[COS]",
) -> bool:
    """Download COS object to a local file."""
    client = get_cos_client()
    if client is None:
        return False
    local_path.parent.mkdir(parents=True, exist_ok=True)

    def _do_download() -> None:
        client.download_file(
            Bucket=COS_BUCKET,
            Key=object_key,
            DestFilePath=str(local_path),
        )

    try:
        _retry_cos_call("download", _do_download, max_retries=max_retries)
        return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("%s Download failed key=%s: %s", log_prefix, object_key, exc)
        return False


def _cos_fetch_errors() -> tuple[type[Exception], ...]:
    errors: list[type[Exception]] = list(BACKGROUND_INFRA_ERRORS)
    if CosServiceError is not None:
        errors.append(CosServiceError)
    if CosClientError is not None:
        errors.append(CosClientError)
    return tuple(errors)


def get_object_bytes(
    object_key: str,
    *,
    max_retries: int = 3,
    log_prefix: str = "[COS]",
    max_bytes: Optional[int] = None,
) -> Optional[bytes]:
    """
    Fetch object body as bytes.

    When ``max_bytes`` is set, only the first N bytes are read (Range request)
    so large Showcase objects are not pulled through the API process.
    """
    client = get_cos_client()
    if client is None:
        return None

    fetch_errors = _cos_fetch_errors()
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            params: Dict[str, Any] = {"Bucket": COS_BUCKET, "Key": object_key}
            if max_bytes is not None and max_bytes > 0:
                params["Range"] = f"bytes=0-{max_bytes - 1}"
            response = client.get_object(**params)
            data = response["Body"].get_raw_stream().read()
            if max_bytes is not None and len(data) > max_bytes:
                return data[:max_bytes]
            return data
        except fetch_errors as exc:
            last_error = exc
            if CosServiceError is not None and isinstance(exc, CosServiceError):
                if cos_exc_call(exc, "get_error_code", "") == "NoSuchKey":
                    logger.debug("%s object missing key=%s", log_prefix, object_key)
                    return None
            if not _is_retryable_cos_error(exc) or attempt + 1 >= max_retries:
                break
            delay = min(5.0 * (2**attempt), 30.0)
            time.sleep(delay)

    if last_error is not None:
        logger.debug("%s get_object failed key=%s: %s", log_prefix, object_key, last_error)
    return None


def head_object(object_key: str) -> Optional[Dict[str, Any]]:
    """Return COS head_object metadata or None."""
    client = get_cos_client()
    if client is None:
        return None
    try:
        return client.head_object(Bucket=COS_BUCKET, Key=object_key)
    except _cos_fetch_errors() as exc:
        if CosServiceError is not None and isinstance(exc, CosServiceError):
            if cos_exc_call(exc, "get_error_code", "") == "NoSuchKey":
                return None
        return None


def object_exists(object_key: str) -> bool:
    """True if object exists in bucket."""
    return head_object(object_key) is not None


def get_json(object_key: str) -> Optional[Dict[str, Any]]:
    """Download and parse JSON object."""
    raw = get_object_bytes(object_key)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def put_json(object_key: str, payload: Dict[str, Any]) -> bool:
    """Upload dict as JSON."""
    data = json.dumps(payload, indent=2).encode("utf-8")
    return upload_bytes(data, object_key)


def delete_object(object_key: str) -> bool:
    """Delete a single COS object."""
    client = get_cos_client()
    if client is None:
        return False
    try:
        client.delete_object(Bucket=COS_BUCKET, Key=object_key)
        return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[COS] delete_object failed key=%s: %s", object_key, exc)
        return False


def generate_presigned_put_url(
    object_key: str,
    *,
    expired: int = 900,
    content_type: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Short-lived presigned PUT URL for browser→COS uploads (private bucket).

    ``Content-Type`` is signed via Headers (not query Params) so browser PUTs that
    send the same header match the signature. ``expired`` is TTL in seconds.
    Callers must not embed durable COS URLs in API JSON.
    """
    client = get_cos_client()
    if client is None:
        return None
    signed_headers: Dict[str, str] = {}
    if headers:
        signed_headers.update(headers)
    if content_type:
        signed_headers.setdefault("Content-Type", content_type)
    try:
        return client.get_presigned_url(
            Method="PUT",
            Bucket=COS_BUCKET,
            Key=object_key,
            Expired=expired,
            Headers=signed_headers or None,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[COS] presigned PUT failed key=%s: %s", object_key, exc)
        return None


def generate_presigned_get_url(
    object_key: str,
    *,
    expired: int = 300,
    response_content_disposition: Optional[str] = None,
) -> Optional[str]:
    """
    Short-lived presigned GET URL for authenticated downloads (private bucket).

    Prefer returning this only as a redirect Location, never as a durable API field.
    """
    client = get_cos_client()
    if client is None:
        return None
    params: Dict[str, Any] = {}
    if response_content_disposition:
        params["response-content-disposition"] = response_content_disposition
    try:
        return client.get_presigned_url(
            Method="GET",
            Bucket=COS_BUCKET,
            Key=object_key,
            Expired=expired,
            Params=params or None,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[COS] presigned GET failed key=%s: %s", object_key, exc)
        return None


def list_prefix(
    prefix: str,
    *,
    suffix_filter: Optional[str] = None,
    contains_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List objects under prefix.

    Returns list of {key, size, last_modified, filename}.
    """
    client = get_cos_client()
    if client is None:
        return []

    normalized = prefix.rstrip("/")
    results: List[Dict[str, Any]] = []
    marker = ""
    is_truncated = True

    try:
        while is_truncated:
            response = client.list_objects(Bucket=COS_BUCKET, Prefix=normalized, Marker=marker)
            for obj in response.get("Contents", []):
                obj_key = obj["Key"]
                if not obj_key.startswith(normalized):
                    continue
                filename = obj_key.rsplit("/", 1)[-1]
                if suffix_filter and not obj_key.endswith(suffix_filter):
                    continue
                if contains_filter and contains_filter not in obj_key:
                    continue
                last_modified = obj.get("LastModified")
                results.append(
                    {
                        "key": obj_key,
                        "size": int(obj.get("Size", 0)),
                        "last_modified": last_modified,
                        "filename": filename,
                    }
                )
            is_truncated = response.get("IsTruncated", "false") == "true"
            if is_truncated:
                marker = response.get("NextMarker", "")
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[COS] list_objects failed prefix=%s: %s", normalized, exc)
        return []

    return results


def parse_cos_timestamp(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse COS LastModified into datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        timestamp_str = value.replace("Z", "")
        try:
            if "." in timestamp_str:
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                return None
    return None


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def test_cos_connection() -> Dict[str, Any]:
    """
    Probe COS connectivity.

    Returns {ok, configured, sdk_available, error}.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "configured": cos_credentials_configured(),
        "sdk_available": cos_sdk_available(),
        "bucket": COS_BUCKET or None,
        "region": COS_REGION or None,
        "key_prefix": normalized_cos_prefix(),
        "error": None,
    }
    if not result["sdk_available"]:
        result["error"] = "cos_sdk_missing"
        return result
    if not result["configured"]:
        result["error"] = "cos_not_configured"
        return result
    client = get_cos_client()
    if client is None:
        result["error"] = "client_init_failed"
        return result
    try:
        prefix = normalized_cos_prefix()
        client.list_objects(Bucket=COS_BUCKET, Prefix=prefix, MaxKeys=1)
        result["ok"] = True
    except BACKGROUND_INFRA_ERRORS as exc:
        result["error"] = str(exc)
    return result
