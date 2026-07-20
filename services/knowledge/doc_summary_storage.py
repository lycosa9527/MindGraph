"""Document Summary extracted-content storage (COS + Redis cache + PG pointers).

Only extracted markdown is persisted — original uploads are discarded after
extraction. Each extract gets a unique ``object_id`` (UUID) so test/prod can
share one COS bucket without colliding on overlapping MG user ids. Postgres
holds the cos_key; APIs check package ownership before any fetch.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import config
from services.redis import keys as redis_keys
from services.redis.redis_async_ops import AsyncRedisOps
from services.utils.tencent_cos_client import (
    COS_BUCKET,
    cos_credentials_configured,
    cos_object_key,
    delete_object,
    get_object_bytes,
    upload_bytes,
)

logger = logging.getLogger(__name__)

STORAGE_COS = "cos"
STORAGE_LOCAL = "local"

# Skip Redis text cache above this size (COS/local remain source of truth).
_REDIS_TEXT_CACHE_MAX_CHARS = 2_000_000


def cos_documents_enabled() -> bool:
    """True when COS document storage is enabled and credentials are configured."""
    if not config.COS_DOCUMENTS_ENABLED:
        return False
    return cos_credentials_configured()


def new_object_id() -> str:
    """Allocate a unique opaque id for one extracted markdown object."""
    return uuid.uuid4().hex


def build_cos_key(object_id: str) -> str:
    """COS object key for one extracted markdown blob (UUID-based, not user id)."""
    oid = (object_id or "").strip()
    if not oid:
        raise ValueError("object_id is required for Document Summary COS keys")
    relative = f"{oid}.md"
    return cos_object_key(relative, prefix=config.COS_DOCUMENTS_PREFIX)


def build_local_fallback_path(object_id: str) -> Path:
    """Local extracted-markdown path when COS is unavailable (dev/tests)."""
    oid = (object_id or "").strip()
    if not oid:
        raise ValueError("object_id is required for Document Summary local paths")
    base = Path(config.KNOWLEDGE_STORAGE_DIR) / "doc_summary"
    return base / f"{oid}.md"


def build_storage_metadata(
    *,
    object_id: str,
    markdown: str,
    source_filename: str,
    source_mime: str,
    ingest_source: str,
    page_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build ``doc_metadata`` payload after a successful extract/store."""
    text = markdown.strip()
    now = datetime.now(UTC).isoformat()
    meta: Dict[str, Any] = {
        "storage": STORAGE_COS if cos_documents_enabled() else STORAGE_LOCAL,
        "object_id": object_id,
        "ingest_source": ingest_source,
        "source_filename": source_filename,
        "source_mime": source_mime,
        "extract_char_count": len(text),
        "extracted_at": now,
        "doc_summary_lite": True,
    }
    if page_url:
        meta["page_url"] = page_url
    if cos_documents_enabled():
        meta["cos_bucket"] = COS_BUCKET
        meta["cos_key"] = build_cos_key(object_id)
    else:
        meta["local_path"] = str(build_local_fallback_path(object_id))
    return meta


def _write_local(path: Path, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def _read_local(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def store_extracted_markdown_sync(
    markdown: str,
    object_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist extracted markdown to COS or local fallback. Returns storage keys."""
    text = markdown.strip()
    if not text:
        raise ValueError("Extracted content is empty")

    oid = (object_id or new_object_id()).strip()
    if cos_documents_enabled():
        cos_key = build_cos_key(oid)
        payload = text.encode("utf-8")
        if not upload_bytes(payload, cos_key, log_prefix="[DocSummary/COS]"):
            raise RuntimeError("Failed to upload extracted content to COS")
        return {
            "storage": STORAGE_COS,
            "object_id": oid,
            "cos_key": cos_key,
            "cos_bucket": COS_BUCKET,
        }

    local_path = build_local_fallback_path(oid)
    _write_local(local_path, text)
    return {
        "storage": STORAGE_LOCAL,
        "object_id": oid,
        "local_path": str(local_path),
    }


async def store_extracted_markdown(
    markdown: str,
    object_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Async wrapper around :func:`store_extracted_markdown_sync`."""
    return await asyncio.to_thread(store_extracted_markdown_sync, markdown, object_id)


def fetch_extracted_markdown_sync(doc_metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """Load extracted markdown from COS or local path described in metadata."""
    if not doc_metadata:
        return None

    storage = doc_metadata.get("storage")
    if storage == STORAGE_COS:
        cos_key = doc_metadata.get("cos_key")
        if not cos_key:
            object_id = doc_metadata.get("object_id")
            if object_id:
                cos_key = build_cos_key(str(object_id))
        if not cos_key:
            return None
        raw = get_object_bytes(cos_key, log_prefix="[DocSummary/COS]")
        if raw is None:
            return None
        return raw.decode("utf-8")

    local_path = doc_metadata.get("local_path")
    if local_path:
        return _read_local(Path(local_path))
    object_id = doc_metadata.get("object_id")
    if object_id:
        return _read_local(build_local_fallback_path(str(object_id)))
    return None


async def fetch_extracted_markdown(doc_metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """Async fetch from COS/local."""
    return await asyncio.to_thread(fetch_extracted_markdown_sync, doc_metadata)


def _redis_status_key(package_id: int) -> str:
    return redis_keys.DOC_SUMMARY_PKG_STATUS.format(package_id=package_id)


def _redis_text_key(package_id: int) -> str:
    return redis_keys.DOC_SUMMARY_PKG_TEXT.format(package_id=package_id)


async def set_package_status(package_id: int, status: str) -> None:
    """Cache processing status for UI polling (legacy string form)."""
    await set_package_extract_progress(package_id, status, status, 0 if status == "failed" else 50)


async def set_package_extract_progress(
    package_id: int,
    status: str,
    stage: str,
    percent: int,
) -> None:
    """Cache extract status + stage + percent for UI polling."""
    payload = json.dumps(
        {
            "status": status,
            "stage": stage,
            "percent": max(0, min(100, int(percent))),
        }
    )
    await AsyncRedisOps.set_with_ttl(
        _redis_status_key(package_id),
        payload,
        redis_keys.TTL_DOC_SUMMARY_STATUS,
    )


async def get_package_status(package_id: int) -> Optional[str]:
    """Return cached package extract status string (legacy or JSON payload)."""
    raw = await AsyncRedisOps.get(_redis_status_key(package_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw
    if isinstance(data, dict):
        status = data.get("status")
        return str(status) if status is not None else None
    return str(raw)


async def get_package_extract_progress(package_id: int) -> Optional[Dict[str, Any]]:
    """Return ``{status, stage, percent}`` when Redis holds a progress payload."""
    raw = await AsyncRedisOps.get(_redis_status_key(package_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"status": raw, "stage": raw, "percent": 0}
    if isinstance(data, dict):
        return {
            "status": data.get("status"),
            "stage": data.get("stage"),
            "percent": int(data.get("percent") or 0),
        }
    return None


async def cache_extracted_text(package_id: int, markdown: str) -> None:
    """Cache extracted markdown in Redis for fast regenerate."""
    text = markdown.strip()
    if not text:
        return
    if len(text) > _REDIS_TEXT_CACHE_MAX_CHARS:
        # Oversized extracts stay on COS/local only.
        return
    await AsyncRedisOps.set_with_ttl(
        _redis_text_key(package_id),
        text,
        redis_keys.TTL_DOC_SUMMARY_TEXT,
    )


async def fetch_extracted_markdown_cached(
    package_id: int,
    doc_metadata: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Redis cache first, then COS/local."""
    cached = await AsyncRedisOps.get(_redis_text_key(package_id))
    if cached:
        return cached

    text = await fetch_extracted_markdown(doc_metadata)
    if text:
        await cache_extracted_text(package_id, text)
    return text


def delete_extracted_content_sync(doc_metadata: Optional[Dict[str, Any]]) -> None:
    """Remove COS object or local extracted file."""
    if not doc_metadata:
        return

    storage = doc_metadata.get("storage")
    if storage == STORAGE_COS:
        cos_key = doc_metadata.get("cos_key")
        if not cos_key and doc_metadata.get("object_id"):
            cos_key = build_cos_key(str(doc_metadata["object_id"]))
        if cos_key:
            delete_object(cos_key)
        return

    local_path = doc_metadata.get("local_path")
    if local_path:
        path = Path(local_path)
        if path.is_file():
            path.unlink()
        return
    object_id = doc_metadata.get("object_id")
    if object_id:
        path = build_local_fallback_path(str(object_id))
        if path.is_file():
            path.unlink()


async def delete_extracted_content(doc_metadata: Optional[Dict[str, Any]]) -> None:
    """Async delete of stored extracted content."""
    await asyncio.to_thread(delete_extracted_content_sync, doc_metadata)


async def clear_package_redis(package_id: int) -> None:
    """Drop cached status/text for a package."""
    await AsyncRedisOps.delete(_redis_status_key(package_id))
    await AsyncRedisOps.delete(_redis_text_key(package_id))
