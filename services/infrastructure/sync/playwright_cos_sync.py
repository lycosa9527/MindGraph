"""
Playwright Chromium COS mirror (publisher upload / consumer install).

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

from services.infrastructure.sync.cos_sync_env import (
    is_cos_publisher,
    playwright_meta_cos_key,
    playwright_tarball_cos_key,
)
from services.infrastructure.sync.playwright_apt_cos_sync import (
    ensure_playwright_deps_via_cos_or_apt,
    get_playwright_apt_deps_cos_status,
    publish_playwright_apt_deps_to_cos_manual,
)
from services.infrastructure.sync.playwright_release import (
    chromium_revision_from_path,
    detect_installed_chromium_revision,
    detect_installed_playwright_browser_version,
    download_playwright_chromium_to_temp,
    install_playwright_chromium_from_tarball,
    parse_playwright_tarball_version,
    playwright_package_version,
    playwright_platform_tag,
    playwright_system_deps_status,
    playwright_target_version,
)
from services.infrastructure.sync.playwright_update_state import write_playwright_update_state
from services.infrastructure.sync.release_version import compare_release_versions
from services.utils import tencent_cos_client

logger = logging.getLogger(__name__)

_PACKAGE_NEWER = "package_newer_than_cos"
_COS_NEWER = "cos_newer_than_package"


def read_playwright_cos_meta() -> Optional[Dict[str, Any]]:
    """Read Playwright Chromium release meta from COS."""
    return tencent_cos_client.get_json(playwright_meta_cos_key())


def playwright_package_cos_mismatch(
    package_version: Optional[str],
    cos_version: str,
) -> Optional[Dict[str, Any]]:
    """
    Return a blocked update plan when pip package and COS Chromium versions differ.

    Chromium builds are tied to the Playwright package revision; a mismatch always
    fails install (opaque ``install_failed`` without this check).
    """
    if not package_version or not cos_version:
        return None
    cmp = compare_release_versions(package_version, cos_version)
    if cmp == 0:
        return None
    if cmp > 0:
        hint = (
            f"Local Playwright package {package_version} is newer than COS Chromium "
            f"{cos_version}. Republish Playwright to COS from a host with package "
            f"{package_version}."
        )
        return {
            "update_needed": False,
            "reason": _PACKAGE_NEWER,
            "package_version": package_version,
            "cos_version": cos_version,
            "hint": hint,
        }
    hint = (
        f"COS Chromium {cos_version} is newer than local Playwright package "
        f"{package_version}. Upgrade the package first "
        f"(pip install 'playwright=={cos_version}'), then retry."
    )
    return {
        "update_needed": False,
        "reason": _COS_NEWER,
        "package_version": package_version,
        "cos_version": cos_version,
        "hint": hint,
    }


def playwright_cos_update_needed() -> Dict[str, Any]:
    """True when COS meta version is newer than the locally installed Chromium."""
    cos_meta = read_playwright_cos_meta()
    installed = detect_installed_playwright_browser_version()
    package = playwright_package_version()
    if not cos_meta or not isinstance(cos_meta.get("version"), str):
        return {
            "update_needed": False,
            "reason": "cos_meta_missing",
            "installed_version": installed,
            "package_version": package,
            "cos_version": None,
        }
    cos_version = cos_meta["version"]
    mismatch = playwright_package_cos_mismatch(package, cos_version)
    if mismatch is not None:
        mismatch["installed_version"] = installed
        return mismatch
    if installed is None:
        return {
            "update_needed": True,
            "reason": "not_installed",
            "installed_version": None,
            "package_version": package,
            "cos_version": cos_version,
        }
    cos_revision = cos_meta.get("browser_revision")
    local_revision = detect_installed_chromium_revision()
    if (
        isinstance(cos_revision, str)
        and local_revision
        and cos_revision != local_revision
        and compare_release_versions(installed, cos_version) <= 0
    ):
        return {
            "update_needed": True,
            "reason": "revision_mismatch",
            "installed_version": installed,
            "package_version": package,
            "cos_version": cos_version,
        }
    if compare_release_versions(installed, cos_version) < 0:
        return {
            "update_needed": True,
            "reason": "cos_newer",
            "installed_version": installed,
            "package_version": package,
            "cos_version": cos_version,
        }
    return {
        "update_needed": False,
        "reason": "up_to_date",
        "installed_version": installed,
        "package_version": package,
        "cos_version": cos_version,
    }


async def publish_playwright_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download/pack Chromium and upload to COS (publisher role)."""
    if not is_cos_publisher():
        return {"ok": False, "error": "not_publisher", "version": None, "skipped": False}
    return await _publish_playwright_release_to_cos(force=force)


async def publish_playwright_to_cos_manual(*, force: bool = False) -> Dict[str, Any]:
    """Upload Playwright Chromium to COS when credentials are configured (CLI)."""
    return await _publish_playwright_release_to_cos(force=force)


async def publish_playwright_tarball_file(tar_path: Path, *, force: bool = False) -> Dict[str, Any]:
    """Upload an existing Playwright Chromium tarball to COS."""
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tar_path.is_file():
        result["error"] = "tarball_not_found"
        return result
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    platform_tag = playwright_platform_tag()
    if not platform_tag:
        result["error"] = "unsupported_platform"
        return result
    version = parse_playwright_tarball_version(tar_path) or playwright_target_version()
    revision = chromium_revision_from_path(tar_path.name) or "unknown"
    object_key = playwright_tarball_cos_key(version, platform_tag, tar_path.name)
    meta_key = playwright_meta_cos_key()
    cos_meta = await asyncio.to_thread(read_playwright_cos_meta)
    if (
        not force
        and cos_meta
        and cos_meta.get("version") == version
        and cos_meta.get("platform") == platform_tag
        and cos_meta.get("tarball_filename") == tar_path.name
    ):
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        result["cos_keys"] = {"meta": meta_key, "tarball": object_key}
        return result

    def _upload() -> bool:
        ok = tencent_cos_client.upload_file(tar_path, object_key, log_prefix="[PlaywrightCOS]")
        if not ok:
            return False
        meta = {
            "version": version,
            "platform": platform_tag,
            "browser_revision": revision,
            "tarball_filename": tar_path.name,
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


async def _publish_playwright_release_to_cos(*, force: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "error": None, "version": None, "skipped": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    platform_tag = playwright_platform_tag()
    if not platform_tag:
        result["error"] = "unsupported_platform"
        return result

    version = playwright_target_version()
    cos_meta = await asyncio.to_thread(read_playwright_cos_meta)
    if not force and cos_meta and cos_meta.get("version") == version and cos_meta.get("platform") == platform_tag:
        result["skipped"] = True
        result["ok"] = True
        result["version"] = version
        tarball_filename = str(cos_meta.get("tarball_filename") or "")
        result["cos_keys"] = {
            "meta": playwright_meta_cos_key(),
            "tarball": (
                playwright_tarball_cos_key(version, platform_tag, tarball_filename) if tarball_filename else None
            ),
        }
        return result

    tar_path = await asyncio.to_thread(download_playwright_chromium_to_temp)
    if tar_path is None:
        result["error"] = "chromium_pack_failed"
        return result

    publish_result = await publish_playwright_tarball_file(tar_path, force=True)
    try:
        tar_path.unlink(missing_ok=True)
        tar_path.parent.rmdir()
    except OSError:
        pass
    if publish_result.get("ok") and not publish_result.get("skipped"):
        logger.info(
            "[PlaywrightCOS] Published v%s to COS key=%s",
            publish_result.get("version"),
            (publish_result.get("cos_keys") or {}).get("tarball"),
        )
    return publish_result


async def verify_playwright_cos_pull() -> Dict[str, Any]:
    """Download tarball from COS and verify SHA-256 without installing."""
    result: Dict[str, Any] = {"ok": False, "error": None, "verified": False}
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result
    cos_meta = await asyncio.to_thread(read_playwright_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result
    version = str(cos_meta.get("version") or "")
    platform_tag = str(cos_meta.get("platform") or playwright_platform_tag() or "")
    tarball_filename = str(cos_meta.get("tarball_filename") or "")
    expected_sha = cos_meta.get("sha256")
    if not tarball_filename or not platform_tag:
        result["error"] = "tarball_filename_missing"
        return result
    object_key = playwright_tarball_cos_key(version, platform_tag, tarball_filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_playwright_verify_"))
    tar_path = tmp_dir / tarball_filename

    def _download() -> bool:
        return tencent_cos_client.download_file(object_key, tar_path, log_prefix="[PlaywrightCOS]")

    if not await asyncio.to_thread(_download):
        result["error"] = "cos_download_failed"
        return result

    actual_sha = tencent_cos_client.sha256_hex(tar_path.read_bytes())
    verified = isinstance(expected_sha, str) and actual_sha == expected_sha
    result["ok"] = True
    result["verified"] = verified
    result["version"] = version
    result["tarball_filename"] = tarball_filename
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


async def install_playwright_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Download Playwright Chromium from COS and extract into the browsers cache."""
    result: Dict[str, Any] = {
        "ok": False,
        "error": None,
        "version": None,
        "skipped": False,
    }
    if not tencent_cos_client.cos_credentials_configured():
        result["error"] = "cos_not_configured"
        return result

    cos_meta = await asyncio.to_thread(read_playwright_cos_meta)
    if not cos_meta:
        result["error"] = "cos_meta_missing"
        return result

    version = str(cos_meta.get("version") or playwright_target_version())
    platform_tag = str(cos_meta.get("platform") or "")
    tarball_filename = str(cos_meta.get("tarball_filename") or "")
    if not tarball_filename or not platform_tag:
        result["error"] = "tarball_filename_missing"
        return result

    local_platform = playwright_platform_tag()
    if local_platform and platform_tag != local_platform:
        result["error"] = "platform_mismatch"
        result["cos_platform"] = platform_tag
        result["local_platform"] = local_platform
        return result

    package = await asyncio.to_thread(playwright_package_version)
    mismatch = playwright_package_cos_mismatch(package, version)
    if mismatch is not None:
        result["error"] = str(mismatch["reason"])
        result["package_version"] = mismatch.get("package_version")
        result["cos_version"] = mismatch.get("cos_version")
        result["hint"] = mismatch.get("hint")
        return result

    installed = await asyncio.to_thread(detect_installed_playwright_browser_version)
    plan = await asyncio.to_thread(playwright_cos_update_needed)
    if not force and installed and not plan.get("update_needed"):
        result["skipped"] = True
        result["ok"] = True
        result["version"] = installed
        return result

    object_key = playwright_tarball_cos_key(version, platform_tag, tarball_filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_playwright_cos_"))
    tar_path = tmp_dir / tarball_filename

    def _download_and_install() -> bool:
        if not tencent_cos_client.download_file(object_key, tar_path, log_prefix="[PlaywrightCOS]"):
            return False
        if isinstance(cos_meta.get("sha256"), str):
            actual = tencent_cos_client.sha256_hex(tar_path.read_bytes())
            if actual != cos_meta["sha256"]:
                return False
        return install_playwright_chromium_from_tarball(tar_path)

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
    result["version"] = await asyncio.to_thread(detect_installed_playwright_browser_version) or version
    result["browser_revision"] = await asyncio.to_thread(detect_installed_chromium_revision)
    result["object_key"] = object_key
    await asyncio.to_thread(
        write_playwright_update_state,
        {
            "version": result["version"],
            "browser_revision": result.get("browser_revision"),
            "tarball_filename": tarball_filename,
            "source": "cos",
            "object_key": object_key,
            "previous_version": installed,
        },
    )
    logger.info("[PlaywrightCOS] Installed Chromium for Playwright v%s from COS", result["version"])
    return result


async def update_playwright_from_cos(*, force: bool = False) -> Dict[str, Any]:
    """Install Playwright Chromium from COS and confirm the binary is launchable."""
    result = await install_playwright_from_cos(force=force)
    if not result.get("ok"):
        return result
    if result.get("skipped"):
        deps = await ensure_playwright_deps_via_cos_or_apt()
        result["system_deps"] = deps
        result["deps_ok"] = bool(deps.get("ok"))
        return result
    installed = await asyncio.to_thread(detect_installed_playwright_browser_version)
    if not installed:
        result["browser_ok"] = False
        result["error"] = "browser_not_detected_after_install"
        return result
    result["browser_ok"] = True
    deps = await ensure_playwright_deps_via_cos_or_apt()
    result["system_deps"] = deps
    result["deps_ok"] = bool(deps.get("ok"))
    if not deps.get("ok"):
        logger.warning(
            "[PlaywrightCOS] Chromium installed but system deps missing (%s). Hint: %s",
            deps.get("missing") or (deps.get("system_deps") or {}).get("missing"),
            deps.get("hint"),
        )
    return result


async def publish_playwright_with_apt_deps_to_cos(*, force: bool = False) -> Dict[str, Any]:
    """Publish Chromium browser tarball and apt-deps ``.deb`` bundle to COS."""
    browser = await publish_playwright_to_cos_manual(force=force)
    apt_deps = await publish_playwright_apt_deps_to_cos_manual(force=force)
    return {
        "ok": bool(browser.get("ok")) and bool(apt_deps.get("ok")),
        "browser": browser,
        "apt_deps": apt_deps,
    }


async def get_playwright_cos_status() -> Dict[str, Any]:
    """Status snapshot for CLI / admin."""
    target = playwright_target_version()
    installed = await asyncio.to_thread(detect_installed_playwright_browser_version)
    package = await asyncio.to_thread(playwright_package_version)
    revision = await asyncio.to_thread(detect_installed_chromium_revision)
    cos_meta = await asyncio.to_thread(read_playwright_cos_meta)
    plan = await asyncio.to_thread(playwright_cos_update_needed)
    deps = await asyncio.to_thread(playwright_system_deps_status)
    apt_status = await get_playwright_apt_deps_cos_status()
    return {
        "target_version": target,
        "package_version": package,
        "installed_version": installed,
        "browser_revision": revision,
        "platform": playwright_platform_tag(),
        "cos_meta": cos_meta,
        "update_plan": plan,
        "update_needed": plan.get("update_needed"),
        "system_deps": deps,
        "apt_deps": apt_status,
    }
