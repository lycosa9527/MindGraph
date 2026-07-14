"""
GeoLite2-Country MMDB COS mirror (publisher upload / consumer install).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.auth.geoip_country import (
    get_geolite_country_mmdb_path,
    is_geolite_country_mmdb_file_present,
    reload_geolite_country_reader,
)
from services.infrastructure.sync.cos_sync_env import (
    geolite_meta_cos_key,
    geolite_mmdb_cos_key,
    is_cos_consumer,
    is_cos_publisher,
)
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)


def read_geolite_cos_meta() -> Optional[Dict[str, Any]]:
    """Read GeoLite meta JSON from COS."""
    return tencent_cos_client.get_json(geolite_meta_cos_key())


async def publish_geolite_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Upload local GeoLite2-Country.mmdb to COS (publisher only)."""
    result: Dict[str, Any] = {
        "ok": False,
        "skipped": False,
        "error": None,
        "source": "local",
    }
    if not is_cos_publisher():
        result["error"] = "not_publisher"
        return result
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    path = get_geolite_country_mmdb_path()
    if not path.is_file():
        result["error"] = "local_mmdb_missing"
        result["path"] = str(path)
        return result

    body = await asyncio.to_thread(path.read_bytes)
    digest = tencent_cos_client.sha256_hex(body)
    if not force:
        cos_meta = await asyncio.to_thread(read_geolite_cos_meta)
        if cos_meta and cos_meta.get("sha256") == digest:
            result["ok"] = True
            result["skipped"] = True
            result["sha256"] = digest
            return result

    meta = {
        "sha256": digest,
        "size_bytes": len(body),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "last_merge_unix": time.time(),
        "filename": path.name,
    }
    mmdb_key = geolite_mmdb_cos_key()
    meta_key = geolite_meta_cos_key()
    ok_body = await asyncio.to_thread(
        lambda: tencent_cos_client.upload_bytes(
            body,
            mmdb_key,
            log_prefix="[GeoLiteCOS]",
        ),
    )
    ok_meta = await asyncio.to_thread(tencent_cos_client.put_json, meta_key, meta)
    if ok_body and ok_meta:
        logger.info("[GeoLiteCOS] Published %s (%s bytes) to COS", path.name, len(body))
        result["ok"] = True
        result["sha256"] = digest
        result["size_bytes"] = len(body)
        return result
    result["error"] = "cos_upload_failed"
    return result


async def install_geolite_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download GeoLite MMDB from COS to the local expected path (consumer)."""
    result: Dict[str, Any] = {
        "ok": False,
        "skipped": False,
        "error": None,
        "source": "cos",
    }
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    cos_meta = await asyncio.to_thread(read_geolite_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    expected_sha = cos_meta.get("sha256")
    dest = get_geolite_country_mmdb_path()
    if not force and isinstance(expected_sha, str) and dest.is_file():
        local_digest = tencent_cos_client.sha256_hex(await asyncio.to_thread(dest.read_bytes))
        if local_digest == expected_sha:
            result["ok"] = True
            result["skipped"] = True
            result["sha256"] = local_digest
            return result

    mmdb_key = geolite_mmdb_cos_key()

    def _fetch() -> Optional[bytes]:
        return tencent_cos_client.get_object_bytes(mmdb_key, log_prefix="[GeoLiteCOS]")

    raw = await asyncio.to_thread(_fetch)
    if raw is None:
        result["error"] = "cos_mmdb_missing"
        return result

    if isinstance(expected_sha, str) and tencent_cos_client.sha256_hex(raw) != expected_sha:
        result["error"] = "sha256_mismatch"
        return result

    dest.parent.mkdir(parents=True, exist_ok=True)

    def _atomic_write() -> None:
        with tempfile.NamedTemporaryFile(
            dir=str(dest.parent),
            delete=False,
            suffix=".mmdb.tmp",
        ) as handle:
            handle.write(raw)
            tmp_name = handle.name
        Path(tmp_name).replace(dest)

    try:
        await asyncio.to_thread(_atomic_write)
    except OSError as exc:
        result["error"] = str(exc)
        return result

    reloaded = reload_geolite_country_reader()
    result["ok"] = True
    result["path"] = str(dest)
    result["sha256"] = expected_sha if isinstance(expected_sha, str) else None
    result["reader_reloaded"] = reloaded
    logger.info("[GeoLiteCOS] Installed GeoLite MMDB at %s (reader_ok=%s)", dest, reloaded)
    return result


async def sync_geolite_for_role(*, force: bool = False) -> Dict[str, Any]:
    """Publisher uploads local MMDB; consumer installs from COS; off skips."""
    if is_cos_consumer():
        return await install_geolite_from_cos(force=force)
    if is_cos_publisher():
        return await publish_geolite_to_cos(force=force)
    return {"ok": False, "skipped": True, "error": "role_off", "source": "none"}


async def get_geolite_cos_status() -> Dict[str, Any]:
    """Status for admin / CLI."""
    cos_meta = await asyncio.to_thread(read_geolite_cos_meta)
    local_present = is_geolite_country_mmdb_file_present()
    local_sha: Optional[str] = None
    if local_present:
        path = get_geolite_country_mmdb_path()
        local_sha = tencent_cos_client.sha256_hex(await asyncio.to_thread(path.read_bytes))
    cos_sha = cos_meta.get("sha256") if cos_meta else None
    if cos_meta is None:
        sync_state = "missing_on_cos"
    elif local_sha and cos_sha and local_sha == cos_sha:
        sync_state = "in_sync"
    elif not local_present:
        sync_state = "consumer_behind"
    else:
        sync_state = "consumer_behind" if cos_sha else "unknown"
    return {
        "local_present": local_present,
        "local_path": str(get_geolite_country_mmdb_path()),
        "local_sha256": local_sha,
        "cos_meta": cos_meta,
        "sync_state": sync_state,
    }
