"""
Celery PyPI wheel COS mirror (publisher upload / consumer pip install).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.infrastructure.sync.celery_release import (
    celery_target_version,
    detect_installed_celery_version,
    download_pypi_wheel_to_temp,
    install_celery_from_wheel,
    parse_celery_wheel_version,
    resolve_celery_wheel_path,
)
from services.infrastructure.sync.celery_update_state import write_celery_update_state
from services.infrastructure.sync.cos_sync_env import (
    celery_meta_cos_key,
    celery_wheel_cos_key,
    is_cos_publisher,
)
from services.infrastructure.sync.release_version import compare_release_versions
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)


def read_celery_cos_meta() -> Optional[Dict[str, Any]]:
    """Read Celery release meta from COS."""
    return tencent_cos_client.get_json(celery_meta_cos_key())


def celery_cos_update_needed() -> Dict[str, Any]:
    """True when COS meta version is newer than the active Python environment."""
    cos_meta = read_celery_cos_meta()
    installed = detect_installed_celery_version()
    cos_version: Optional[str] = None
    if cos_meta and isinstance(cos_meta.get("version"), str):
        cos_version = cos_meta["version"]
    if cos_version is None:
        return {
            "update_needed": False,
            "reason": "cos_meta_missing",
            "installed_version": installed,
            "cos_version": None,
        }
    if installed is None:
        return {
            "update_needed": True,
            "reason": "not_installed",
            "installed_version": None,
            "cos_version": cos_version,
        }
    if compare_release_versions(installed, cos_version) < 0:
        return {
            "update_needed": True,
            "reason": "cos_newer",
            "installed_version": installed,
            "cos_version": cos_version,
        }
    return {
        "update_needed": False,
        "reason": "up_to_date",
        "installed_version": installed,
        "cos_version": cos_version,
    }


async def publish_celery_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download Celery wheel from PyPI and upload to COS (publisher role)."""
    if not is_cos_publisher():
        return {"ok": False, "error": "not_publisher", "version": None, "skipped": False}
    return await _publish_celery_release_to_cos(force=force)


async def publish_celery_to_cos_manual(*, force: bool = False) -> Dict[str, Any]:
    """Download Celery wheel from PyPI and upload to COS (CLI / manual)."""
    return await _publish_celery_release_to_cos(force=force)


async def publish_celery_wheel_file(wheel_path: Path, *, force: bool = False) -> Dict[str, Any]:
    """Upload an existing Celery wheel to COS."""
    resolved = resolve_celery_wheel_path(wheel_path)
    if resolved is None:
        missing: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
        if wheel_path.is_file() and wheel_path.suffix.lower() == ".zip":
            missing["error"] = "no_wheel_in_archive"
        else:
            missing["error"] = "wheel_not_found"
        return missing
    wheel_path = resolved
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    version = parse_celery_wheel_version(wheel_path) or celery_target_version()
    wheel_filename = wheel_path.name
    object_key = celery_wheel_cos_key(version, wheel_filename)
    meta_key = celery_meta_cos_key()
    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    if (
        not force
        and cos_meta
        and cos_meta.get("version") == version
        and cos_meta.get("wheel_filename") == wheel_filename
    ):
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        result["cos_keys"] = {"meta": meta_key, "wheel": object_key}
        return result

    def _upload() -> bool:
        ok = tencent_cos_client.upload_file(wheel_path, object_key, log_prefix="[CeleryCOS]")
        if not ok:
            return False
        meta = {
            "version": version,
            "wheel_filename": wheel_filename,
            "sha256": tencent_cos_client.sha256_hex(wheel_path.read_bytes()),
            "size_bytes": wheel_path.stat().st_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "wheel_key": object_key,
            "meta_key": meta_key,
            "source": "local_wheel",
        }
        return tencent_cos_client.put_json(meta_key, meta)

    uploaded = await asyncio.to_thread(_upload)
    if not uploaded:
        result["error"] = "cos_upload_failed"
        return result
    result["ok"] = True
    result["version"] = version
    result["cos_keys"] = {"meta": meta_key, "wheel": object_key}
    return result


async def _publish_celery_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    version = celery_target_version()
    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    if not force and cos_meta and cos_meta.get("version") == version:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        wheel_filename = str(cos_meta.get("wheel_filename") or "")
        result["cos_keys"] = {
            "meta": celery_meta_cos_key(),
            "wheel": celery_wheel_cos_key(version, wheel_filename) if wheel_filename else None,
        }
        return result

    wheel_path = await asyncio.to_thread(download_pypi_wheel_to_temp, version)
    if wheel_path is None:
        result["error"] = "pypi_download_failed"
        return result

    publish_result = await publish_celery_wheel_file(wheel_path, force=True)
    try:
        wheel_path.unlink(missing_ok=True)
        wheel_path.parent.rmdir()
    except OSError:
        pass
    if publish_result.get("ok") and not publish_result.get("skipped"):
        logger.info(
            "[CeleryCOS] Published v%s to COS key=%s",
            publish_result.get("version"),
            (publish_result.get("cos_keys") or {}).get("wheel"),
        )
    return publish_result


async def verify_celery_cos_pull() -> Dict[str, Any]:
    """Download wheel from COS and verify SHA-256 without installing."""
    result: Dict[str, Any] = {"ok": False, "error": None, "verified": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result
    version = str(cos_meta.get("version") or "")
    wheel_filename = str(cos_meta.get("wheel_filename") or "")
    expected_sha = cos_meta.get("sha256")
    if not wheel_filename:
        result["error"] = "wheel_filename_missing"
        return result
    object_key = celery_wheel_cos_key(version, wheel_filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_celery_verify_"))
    wheel_path = tmp_dir / wheel_filename

    def _download() -> bool:
        return tencent_cos_client.download_file(object_key, wheel_path, log_prefix="[CeleryCOS]")

    if not await asyncio.to_thread(_download):
        result["error"] = "cos_download_failed"
        return result

    actual_sha = tencent_cos_client.sha256_hex(wheel_path.read_bytes())
    verified = isinstance(expected_sha, str) and actual_sha == expected_sha
    result["ok"] = True
    result["verified"] = verified
    result["version"] = version
    result["wheel_filename"] = wheel_filename
    result["object_key"] = object_key
    result["size_bytes"] = wheel_path.stat().st_size
    result["sha256_match"] = verified
    if not verified:
        result["error"] = "sha256_mismatch"
        result["expected_sha256"] = expected_sha
        result["actual_sha256"] = actual_sha
    try:
        wheel_path.unlink(missing_ok=True)
        tmp_dir.rmdir()
    except OSError:
        pass
    return result


async def install_celery_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download Celery wheel from COS and pip install into the active environment."""
    result: Dict[str, Any] = {
        "ok": False,
        "error": None,
        "version": None,
        "skipped": False,
    }
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    version = str(cos_meta.get("version") or celery_target_version())
    wheel_filename = str(cos_meta.get("wheel_filename") or "")
    if not wheel_filename:
        result["error"] = "wheel_filename_missing"
        return result

    installed = detect_installed_celery_version()
    if not force and installed and compare_release_versions(installed, version) >= 0:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = installed
        return result

    object_key = celery_wheel_cos_key(version, wheel_filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_celery_cos_"))
    wheel_path = tmp_dir / wheel_filename

    def _download_and_install() -> bool:
        if not tencent_cos_client.download_file(object_key, wheel_path, log_prefix="[CeleryCOS]"):
            return False
        if isinstance(cos_meta.get("sha256"), str):
            actual = tencent_cos_client.sha256_hex(wheel_path.read_bytes())
            if actual != cos_meta["sha256"]:
                return False
        return install_celery_from_wheel(wheel_path)

    ok = await asyncio.to_thread(_download_and_install)
    try:
        if wheel_path.exists():
            wheel_path.unlink()
        tmp_dir.rmdir()
    except OSError:
        pass

    if not ok:
        result["error"] = "install_failed"
        return result

    result["ok"] = True
    result["version"] = detect_installed_celery_version() or version
    result["object_key"] = object_key
    await asyncio.to_thread(
        write_celery_update_state,
        {
            "version": result["version"],
            "wheel_filename": wheel_filename,
            "source": "cos",
            "object_key": object_key,
            "previous_version": installed,
        },
    )
    logger.info("[CeleryCOS] Installed Celery v%s from COS", result["version"])
    return result


async def update_celery_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Install Celery from COS and confirm the new version is importable."""
    result = await install_celery_from_cos(force=force)
    if not result.get("ok"):
        return result
    if result.get("skipped"):
        return result
    installed = detect_installed_celery_version()
    if not installed:
        result["import_ok"] = False
        result["error"] = "version_not_detected_after_install"
        return result
    result["import_ok"] = True
    return result


async def get_celery_cos_status() -> Dict[str, Any]:
    """Status snapshot for CLI / admin."""
    target = celery_target_version()
    installed = await asyncio.to_thread(detect_installed_celery_version)
    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    plan = celery_cos_update_needed()
    return {
        "target_version": target,
        "installed_version": installed,
        "cos_meta": cos_meta,
        "update_plan": plan,
        "update_needed": plan.get("update_needed"),
    }
