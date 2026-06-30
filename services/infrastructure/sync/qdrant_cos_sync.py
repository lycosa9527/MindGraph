"""
Qdrant release COS mirror (publisher upload / consumer install).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.infrastructure.sync.cos_sync_env import (
    is_cos_consumer,
    is_cos_publisher,
    qdrant_cos_auto_install,
    qdrant_meta_cos_key,
    qdrant_tarball_cos_key,
)
from services.infrastructure.sync.qdrant_release import (
    detect_installed_qdrant_version,
    download_github_release_to_temp,
    install_qdrant_from_tarball,
    qdrant_linux_arch_suffix,
    qdrant_target_version,
    stop_qdrant_service,
    wait_for_qdrant_api,
)
from services.infrastructure.sync.qdrant_update_state import (
    write_qdrant_update_state,
)
from services.infrastructure.sync.release_version import compare_release_versions
from services.utils import tencent_cos_client
from services.utils.posix_identity import is_posix_root

logger = logging.getLogger(__name__)


def read_qdrant_cos_meta() -> Optional[Dict[str, Any]]:
    """Read Qdrant release meta from COS."""
    return tencent_cos_client.get_json(qdrant_meta_cos_key())


def qdrant_cos_update_needed() -> Dict[str, Any]:
    """True when COS meta version is newer than the locally installed binary."""
    cos_meta = read_qdrant_cos_meta()
    installed = detect_installed_qdrant_version()
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


def qdrant_update_status(
    target: str,
    installed: Optional[str],
    cos_meta: Optional[Dict[str, Any]],
) -> str:
    """Admin UI status label."""
    cos_version = None
    if cos_meta and isinstance(cos_meta.get("version"), str):
        cos_version = cos_meta["version"]
    if cos_version is None:
        return "not_on_cos"
    if installed is None:
        return "install_pending"
    if compare_release_versions(installed, target) >= 0:
        return "up_to_date"
    if compare_release_versions(installed, cos_version) < 0:
        return "update_available"
    return "up_to_date"


async def publish_qdrant_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download from GitHub and upload Qdrant tarball to COS (publisher role)."""
    if not is_cos_publisher():
        return {"ok": False, "error": "not_publisher", "version": None, "skipped": False}
    return await _publish_qdrant_release_to_cos(force=force)


async def publish_qdrant_to_cos_manual(*, force: bool = False) -> Dict[str, Any]:
    """Upload Qdrant release to COS when credentials are configured (CLI / manual)."""
    return await _publish_qdrant_release_to_cos(force=force)


async def publish_qdrant_tarball_file(tar_path: Path, *, force: bool = False) -> Dict[str, Any]:
    """Upload an existing Qdrant release tarball to COS (when GitHub is unreachable)."""
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tar_path.is_file():
        result["error"] = "tarball_not_found"
        return result
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    version = qdrant_target_version()
    arch = qdrant_linux_arch_suffix()
    if not arch:
        result["error"] = "unsupported_arch"
        return result
    object_key = qdrant_tarball_cos_key(version, arch)
    meta_key = qdrant_meta_cos_key()
    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    if not force and cos_meta and cos_meta.get("version") == version and cos_meta.get("arch") == arch:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
        return result

    def _upload() -> bool:
        ok = tencent_cos_client.upload_file(tar_path, object_key, log_prefix="[QdrantCOS]")
        if not ok:
            return False
        meta = {
            "version": version,
            "arch": arch,
            "sha256": tencent_cos_client.sha256_hex(tar_path.read_bytes()),
            "size_bytes": tar_path.stat().st_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "tarball_key": object_key,
            "meta_key": meta_key,
            "source": "local_tarball",
        }
        return tencent_cos_client.put_json(meta_key, meta)

    uploaded = await asyncio.to_thread(_upload)
    if not uploaded:
        result["error"] = "cos_upload_failed"
        return result
    result["ok"] = True
    result["version"] = version
    result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
    return result


async def _publish_qdrant_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Core publish: GitHub tarball -> COS with meta sidecar."""
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    version = qdrant_target_version()
    arch = qdrant_linux_arch_suffix()
    if not arch:
        result["error"] = "unsupported_arch"
        return result

    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    if not force and cos_meta and cos_meta.get("version") == version and cos_meta.get("arch") == arch:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        result["cos_keys"] = {
            "meta": qdrant_meta_cos_key(),
            "tarball": qdrant_tarball_cos_key(version, arch),
        }
        return result

    tar_path = await asyncio.to_thread(download_github_release_to_temp, version, arch)
    if tar_path is None:
        result["error"] = "github_download_failed"
        return result

    object_key = qdrant_tarball_cos_key(version, arch)
    meta_key = qdrant_meta_cos_key()

    def _upload() -> bool:
        ok = tencent_cos_client.upload_file(tar_path, object_key, log_prefix="[QdrantCOS]")
        if ok:
            size_bytes = tar_path.stat().st_size
            meta = {
                "version": version,
                "arch": arch,
                "sha256": tencent_cos_client.sha256_hex(tar_path.read_bytes()),
                "size_bytes": size_bytes,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "tarball_key": object_key,
                "meta_key": meta_key,
            }
            return tencent_cos_client.put_json(meta_key, meta)
        return False

    uploaded = await asyncio.to_thread(_upload)
    try:
        tar_path.unlink(missing_ok=True)
        tar_path.parent.rmdir()
    except OSError:
        pass

    if not uploaded:
        result["error"] = "cos_upload_failed"
        return result

    result["ok"] = True
    result["version"] = version
    result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
    logger.info("[QdrantCOS] Published v%s (%s) to COS key=%s", version, arch, object_key)
    return result


async def verify_qdrant_cos_pull() -> Dict[str, Any]:
    """Download tarball from COS and verify SHA-256 without installing."""
    result: Dict[str, Any] = {"ok": False, "error": None, "verified": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result
    version = str(cos_meta.get("version") or "")
    arch = str(cos_meta.get("arch") or qdrant_linux_arch_suffix() or "")
    expected_sha = cos_meta.get("sha256")
    object_key = qdrant_tarball_cos_key(version, arch)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_qdrant_verify_"))
    tar_path = tmp_dir / "qdrant.tgz"

    def _download() -> bool:
        return tencent_cos_client.download_file(object_key, tar_path, log_prefix="[QdrantCOS]")

    if not await asyncio.to_thread(_download):
        result["error"] = "cos_download_failed"
        return result

    actual_sha = tencent_cos_client.sha256_hex(tar_path.read_bytes())
    verified = isinstance(expected_sha, str) and actual_sha == expected_sha
    result["ok"] = True
    result["verified"] = verified
    result["version"] = version
    result["arch"] = arch
    result["object_key"] = object_key
    result["size_bytes"] = tar_path.stat().st_size
    result["sha256_match"] = verified
    if not verified:
        result["error"] = "sha256_mismatch"
        result["expected_sha256"] = expected_sha
        result["actual_sha256"] = actual_sha
    try:
        tar_path.unlink(missing_ok=True)
        tmp_dir.rmdir()
    except OSError:
        pass
    return result


async def install_qdrant_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download Qdrant tarball from COS and install."""
    result: Dict[str, Any] = {
        "ok": False,
        "error": None,
        "needs_root": False,
        "version": None,
        "skipped": False,
    }
    if os.name != "posix":
        result["error"] = "not_linux"
        return result
    if not is_posix_root():
        result["needs_root"] = True
        result["error"] = "requires_root"
        return result
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    version = str(cos_meta.get("version") or qdrant_target_version())
    arch = str(cos_meta.get("arch") or qdrant_linux_arch_suffix() or "")
    if not arch:
        result["error"] = "unsupported_arch"
        return result

    installed = detect_installed_qdrant_version()
    if not force and installed and compare_release_versions(installed, version) >= 0:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = installed
        return result

    object_key = qdrant_tarball_cos_key(version, arch)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_qdrant_cos_"))
    tar_path = tmp_dir / "qdrant.tgz"

    def _download_and_install() -> bool:
        if not tencent_cos_client.download_file(object_key, tar_path, log_prefix="[QdrantCOS]"):
            return False
        if isinstance(cos_meta.get("sha256"), str):
            actual = tencent_cos_client.sha256_hex(tar_path.read_bytes())
            if actual != cos_meta["sha256"]:
                return False
        return install_qdrant_from_tarball(tar_path, stop_service=True)

    ok = await asyncio.to_thread(_download_and_install)
    try:
        if tar_path.exists():
            tar_path.unlink()
        tmp_dir.rmdir()
    except OSError:
        pass

    if not ok:
        result["error"] = "install_failed"
        return result

    result["ok"] = True
    result["version"] = version
    result["object_key"] = object_key
    await asyncio.to_thread(
        write_qdrant_update_state,
        {
            "version": version,
            "arch": arch,
            "source": "cos",
            "object_key": object_key,
            "previous_version": installed,
        },
    )
    logger.info("[QdrantCOS] Installed Qdrant v%s from COS", version)
    return result


async def update_qdrant_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Stop Qdrant, install from COS, verify API, record update state."""
    if os.name != "posix":
        return {"ok": False, "error": "not_linux"}
    if not is_posix_root():
        return {"ok": False, "error": "requires_root", "needs_root": True}
    stop_qdrant_service()
    result = await install_qdrant_from_cos(force=force)
    if not result.get("ok"):
        return result
    if result.get("skipped"):
        return result
    if not wait_for_qdrant_api():
        result["api_ok"] = False
        result["error"] = "api_not_responding_after_install"
        return result
    result["api_ok"] = True
    return result


async def maybe_auto_install_qdrant_from_cos() -> None:
    """Startup hook for consumer when auto-install enabled."""
    if not is_cos_consumer() or not qdrant_cos_auto_install():
        return
    if os.name != "posix" or not is_posix_root():
        logger.info("[QdrantCOS] Auto-install skipped (run as root or use admin panel / CLI)")
        return
    result = await install_qdrant_from_cos()
    if result.get("ok") and not result.get("skipped"):
        logger.info("[QdrantCOS] Auto-install completed: v%s", result.get("version"))


async def get_qdrant_cos_status() -> Dict[str, Any]:
    """Status snapshot for admin API."""
    target = qdrant_target_version()
    installed = await asyncio.to_thread(detect_installed_qdrant_version)
    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    arch = qdrant_linux_arch_suffix()
    return {
        "target_version": target,
        "installed_version": installed,
        "cos_meta": cos_meta,
        "arch": arch,
        "status": qdrant_update_status(target, installed, cos_meta),
        "auto_install_enabled": qdrant_cos_auto_install(),
        "is_root": is_posix_root(),
    }
