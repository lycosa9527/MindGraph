"""
Playwright Chromium apt-deps COS mirror (``.deb`` bundle publish / install).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.infrastructure.sync.cos_sync_env import (
    is_cos_publisher,
    playwright_apt_deps_meta_cos_key,
    playwright_apt_deps_tarball_cos_key,
)
from services.infrastructure.sync.playwright_apt_deps import (
    ensure_playwright_apt_deps_from_tarball,
    pack_playwright_apt_deps_to_temp,
    playwright_apt_distro_key,
    playwright_required_apt_packages,
)
from services.infrastructure.sync.playwright_release import (
    ensure_playwright_system_deps,
    playwright_system_deps_status,
    playwright_target_version,
)
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)


def read_playwright_apt_deps_cos_meta() -> Optional[Dict[str, Any]]:
    """Read Playwright apt-deps meta from COS."""
    return tencent_cos_client.get_json(playwright_apt_deps_meta_cos_key())


def playwright_apt_deps_cos_update_needed() -> Dict[str, Any]:
    """True when COS has an apt-deps bundle and local system deps are missing."""
    cos_meta = read_playwright_apt_deps_cos_meta()
    local_distro = playwright_apt_distro_key()
    deps = playwright_system_deps_status()
    cos_distro = None
    if cos_meta and isinstance(cos_meta.get("distro_key"), str):
        cos_distro = cos_meta["distro_key"]
    if cos_distro is None:
        return {
            "update_needed": False,
            "reason": "cos_meta_missing",
            "distro_key": local_distro,
            "cos_distro_key": None,
            "deps_ok": deps.get("ok"),
        }
    if local_distro and cos_distro != local_distro:
        return {
            "update_needed": False,
            "reason": "distro_mismatch",
            "distro_key": local_distro,
            "cos_distro_key": cos_distro,
            "deps_ok": deps.get("ok"),
        }
    if deps.get("ok"):
        return {
            "update_needed": False,
            "reason": "up_to_date",
            "distro_key": local_distro,
            "cos_distro_key": cos_distro,
            "deps_ok": True,
        }
    return {
        "update_needed": True,
        "reason": "missing_packages",
        "distro_key": local_distro,
        "cos_distro_key": cos_distro,
        "deps_ok": False,
        "missing": deps.get("missing") or [],
    }


async def publish_playwright_apt_deps_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download apt ``.deb``s and upload bundle to COS (publisher role)."""
    if not is_cos_publisher():
        return {"ok": False, "error": "not_publisher", "skipped": False}
    return await publish_playwright_apt_deps_to_cos_manual(force=force)


async def publish_playwright_apt_deps_to_cos_manual(*, force: bool = False) -> Dict[str, Any]:
    """Pack host apt deps for Playwright Chromium and upload to COS."""
    result: Dict[str, Any] = {"ok": False, "error": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    distro_key = playwright_apt_distro_key()
    if not distro_key:
        result["error"] = "unsupported_distro"
        return result
    leaf = playwright_required_apt_packages(distro_key)
    if not leaf:
        result["error"] = "package_list_missing"
        return result

    version = playwright_target_version()
    tarball_filename = f"playwright-apt-deps-{distro_key}.tar.gz"
    object_key = playwright_apt_deps_tarball_cos_key(distro_key, tarball_filename)
    meta_key = playwright_apt_deps_meta_cos_key()
    cos_meta = await asyncio.to_thread(read_playwright_apt_deps_cos_meta)
    if (
        not force
        and cos_meta
        and cos_meta.get("distro_key") == distro_key
        and cos_meta.get("playwright_version") == version
        and cos_meta.get("tarball_filename") == tarball_filename
    ):
        result["skipped"] = True
        result["ok"] = True
        result["distro_key"] = distro_key
        result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
        return result

    tar_path = await asyncio.to_thread(pack_playwright_apt_deps_to_temp, distro_key=distro_key)
    if tar_path is None:
        result["error"] = "apt_pack_failed"
        return result

    def _upload() -> bool:
        ok = tencent_cos_client.upload_file(tar_path, object_key, log_prefix="[PlaywrightAptCOS]")
        if not ok:
            return False
        meta = {
            "playwright_version": version,
            "distro_key": distro_key,
            "tarball_filename": tar_path.name,
            "leaf_packages": leaf,
            "sha256": tencent_cos_client.sha256_hex(tar_path.read_bytes()),
            "size_bytes": tar_path.stat().st_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "tarball_key": object_key,
            "meta_key": meta_key,
            "source": "apt-get download",
        }
        return tencent_cos_client.put_json(meta_key, meta)

    uploaded = await asyncio.to_thread(_upload)
    shutil.rmtree(tar_path.parent, ignore_errors=True)

    if not uploaded:
        result["error"] = "cos_upload_failed"
        return result
    result["ok"] = True
    result["distro_key"] = distro_key
    result["playwright_version"] = version
    result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
    logger.info("[PlaywrightAptCOS] Published apt-deps for %s to COS", distro_key)
    return result


async def install_playwright_apt_deps_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download apt-deps bundle from COS and install ``.deb`` packages."""
    result: Dict[str, Any] = {"ok": False, "error": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    plan = await asyncio.to_thread(playwright_apt_deps_cos_update_needed)
    if not force and not plan.get("update_needed"):
        if plan.get("reason") == "up_to_date":
            result["ok"] = True
            result["skipped"] = True
            result["reason"] = "up_to_date"
            return result
        if plan.get("reason") == "cos_meta_missing":
            result["error"] = "cos_meta_missing"
            return result
        if plan.get("reason") == "distro_mismatch":
            result["error"] = "distro_mismatch"
            result["distro_key"] = plan.get("distro_key")
            result["cos_distro_key"] = plan.get("cos_distro_key")
            return result

    cos_meta = await asyncio.to_thread(read_playwright_apt_deps_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result
    distro_key = str(cos_meta.get("distro_key") or "")
    tarball_filename = str(cos_meta.get("tarball_filename") or "")
    local_distro = playwright_apt_distro_key()
    if local_distro and distro_key and local_distro != distro_key:
        result["error"] = "distro_mismatch"
        result["distro_key"] = local_distro
        result["cos_distro_key"] = distro_key
        return result
    if not distro_key or not tarball_filename:
        result["error"] = "tarball_filename_missing"
        return result

    object_key = playwright_apt_deps_tarball_cos_key(distro_key, tarball_filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_pw_apt_cos_"))
    tar_path = tmp_dir / tarball_filename

    def _download() -> bool:
        if not tencent_cos_client.download_file(
            object_key,
            tar_path,
            log_prefix="[PlaywrightAptCOS]",
        ):
            return False
        if isinstance(cos_meta.get("sha256"), str):
            actual = tencent_cos_client.sha256_hex(tar_path.read_bytes())
            if actual != cos_meta["sha256"]:
                return False
        return True

    if not await asyncio.to_thread(_download):
        try:
            tar_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass
        result["error"] = "cos_download_failed"
        return result

    install_result = await asyncio.to_thread(ensure_playwright_apt_deps_from_tarball, tar_path)
    try:
        tar_path.unlink(missing_ok=True)
        tmp_dir.rmdir()
    except OSError:
        pass

    if not install_result.get("ok"):
        result["error"] = str(install_result.get("reason") or "install_failed")
        result["system_deps"] = install_result
        return result

    status = await asyncio.to_thread(playwright_system_deps_status)
    result["ok"] = True
    result["distro_key"] = distro_key
    result["object_key"] = object_key
    result["deps_ok"] = bool(status.get("ok"))
    result["system_deps"] = status
    logger.info("[PlaywrightAptCOS] Installed apt-deps for %s from COS", distro_key)
    return result


async def ensure_playwright_deps_via_cos_or_apt() -> Dict[str, Any]:
    """
    Prefer COS ``.deb`` bundle; fall back to online ``playwright install-deps``.
    """
    status = await asyncio.to_thread(playwright_system_deps_status)
    if status.get("ok"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_satisfied",
            "source": None,
            "system_deps": status,
        }

    cos_result = await install_playwright_apt_deps_from_cos(force=False)
    if cos_result.get("ok"):
        cos_result["source"] = "cos"
        return cos_result

    apt_result = await asyncio.to_thread(ensure_playwright_system_deps)
    apt_result["source"] = "apt"
    apt_result["cos_error"] = cos_result.get("error")
    return apt_result


async def get_playwright_apt_deps_cos_status() -> Dict[str, Any]:
    """Status snapshot for CLI / admin."""
    cos_meta = await asyncio.to_thread(read_playwright_apt_deps_cos_meta)
    plan = await asyncio.to_thread(playwright_apt_deps_cos_update_needed)
    deps = await asyncio.to_thread(playwright_system_deps_status)
    return {
        "distro_key": playwright_apt_distro_key(),
        "leaf_packages": playwright_required_apt_packages(),
        "cos_meta": cos_meta,
        "update_plan": plan,
        "system_deps": deps,
    }
