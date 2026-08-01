"""
Playwright Chromium release helpers (detect, install, pack, unpack).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

_CHROMIUM_DIR_RE = re.compile(r"(?:^|/)chromium(?:_headless_shell)?-(\d+)(?:/|$)")
_TARBALL_REVISION_RE = re.compile(r"-r(\d+)(?:\.tar\.gz)?$", re.IGNORECASE)
_PLAYWRIGHT_SYNC_ERRORS = (OSError, RuntimeError, ValueError, ImportError, PlaywrightError)


def playwright_package_version() -> Optional[str]:
    """Installed Playwright Python package version."""
    try:
        return pkg_version("playwright")
    except PackageNotFoundError:
        return None


def playwright_target_version() -> str:
    """Pinned or env override Playwright package version for COS meta."""
    override = os.getenv("PLAYWRIGHT_TARGET_VERSION", "").strip()
    if override:
        return override.lstrip("v")
    installed = playwright_package_version()
    if installed:
        return installed
    return "0.0.0"


def playwright_platform_tag() -> Optional[str]:
    """Return COS platform tag (linux-x64 / linux-arm64) or None if unsupported."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system != "linux":
        return None
    if machine in ("x86_64", "amd64"):
        return "linux-x64"
    if machine in ("aarch64", "arm64"):
        return "linux-arm64"
    return None


def playwright_browsers_dir() -> Path:
    """Directory where Playwright stores browser builds."""
    override = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if override and override != "0":
        return Path(override).expanduser()
    return Path.home() / ".cache" / "ms-playwright"


def _query_playwright_chromium_path() -> Optional[str]:
    """Ask Playwright for its Chromium path (sync API; call from a worker thread)."""
    try:
        with sync_playwright() as playwright_api:
            path = playwright_api.chromium.executable_path
    except _PLAYWRIGHT_SYNC_ERRORS:
        return None
    return path if path else None


def _chromium_executable_path() -> Optional[str]:
    path = _query_playwright_chromium_path()
    if path and os.path.exists(path):
        return path
    return None


def chromium_revision_from_path(path: str | Path) -> Optional[str]:
    """Extract chromium revision from a cache path or COS tarball filename."""
    text = str(path).replace("\\", "/")
    dir_match = _CHROMIUM_DIR_RE.search(text)
    if dir_match:
        return dir_match.group(1)
    tarball_match = _TARBALL_REVISION_RE.search(Path(text).name)
    if tarball_match:
        return tarball_match.group(1)
    return None


def detect_installed_playwright_browser_version() -> Optional[str]:
    """
    Return Playwright package version when its Chromium binary is present.

    Used as the local version for COS update comparisons.
    """
    package = playwright_package_version()
    if not package:
        return None
    if _chromium_executable_path() is None:
        return None
    return package


def detect_installed_chromium_revision() -> Optional[str]:
    """Revision folder for the current Playwright Chromium binary."""
    executable = _chromium_executable_path()
    if not executable:
        return None
    return chromium_revision_from_path(executable)


def install_playwright_chromium_via_cdn() -> bool:
    """Run ``python -m playwright install chromium`` (needs CDN access)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and _chromium_executable_path() is not None


def _related_browser_dirs(chromium_dir: Path) -> list[Path]:
    """Chromium dir plus sibling ffmpeg / headless_shell dirs when present."""
    dirs = [chromium_dir]
    parent = chromium_dir.parent
    revision = chromium_revision_from_path(chromium_dir)
    if revision:
        headless = parent / f"chromium_headless_shell-{revision}"
        if headless.is_dir():
            dirs.append(headless)
    for child in sorted(parent.iterdir()):
        if child.is_dir() and child.name.startswith("ffmpeg-"):
            dirs.append(child)
    return dirs


def pack_playwright_chromium_to_temp() -> Optional[Path]:
    """
    Pack installed Chromium (and related dirs) into a temp ``.tar.gz``.

    Archive members are relative to the browsers cache root
    (e.g. ``chromium-1228/...``).
    """
    executable = _chromium_executable_path()
    if not executable:
        return None
    chromium_dir: Optional[Path] = None
    current = Path(executable).resolve()
    for parent in [current, *current.parents]:
        if parent.name.startswith("chromium-") and parent.is_dir():
            chromium_dir = parent
            break
    if chromium_dir is None:
        return None
    members = _related_browser_dirs(chromium_dir)
    revision = chromium_revision_from_path(chromium_dir) or "unknown"
    platform_tag = playwright_platform_tag() or "linux"
    version = playwright_target_version()
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_playwright_"))
    archive_name = f"playwright-chromium-{version}-{platform_tag}-r{revision}.tar.gz"
    archive_path = tmp_dir / archive_name
    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            for member_dir in members:
                archive.add(member_dir, arcname=member_dir.name, recursive=True)
    except (OSError, tarfile.TarError):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None
    if not archive_path.is_file() or archive_path.stat().st_size == 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None
    return archive_path


def download_playwright_chromium_to_temp() -> Optional[Path]:
    """Ensure Chromium is installed (CDN if needed), then pack to a temp tarball."""
    if _chromium_executable_path() is None:
        if not install_playwright_chromium_via_cdn():
            return None
    return pack_playwright_chromium_to_temp()


def install_playwright_chromium_from_tarball(tar_path: Path) -> bool:
    """Extract a Playwright Chromium tarball into the browsers cache directory."""
    if not tar_path.is_file():
        return False
    browsers_dir = playwright_browsers_dir()
    browsers_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(tar_path, "r:gz") as archive:
            archive.extractall(path=browsers_dir, filter="data")
    except (OSError, tarfile.TarError, ValueError):
        try:
            with tarfile.open(tar_path, "r:gz") as archive:
                archive.extractall(path=browsers_dir)
        except (OSError, tarfile.TarError):
            return False
    return _chromium_executable_path() is not None


def parse_playwright_tarball_version(tar_path: Path) -> Optional[str]:
    """Extract Playwright package version from archive filename when present."""
    match = re.search(
        r"playwright-chromium-(\d+\.\d+\.\d+)",
        tar_path.name,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None


def parse_install_deps_dry_run(stdout: str, stderr: str = "") -> list[str]:
    """Parse package names from ``playwright install-deps --dry-run`` output."""
    text = f"{stdout}\n{stderr}"
    packages: list[str] = []
    in_list = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("missing system dependencies"):
            in_list = True
            continue
        if not in_list:
            continue
        if not line or line.startswith("$") or line.lower().startswith("sudo"):
            if packages:
                break
            continue
        # apt package names: lowercase, digits, + - .
        if re.fullmatch(r"[a-z0-9][a-z0-9.+-]*", line):
            packages.append(line)
        elif packages:
            break
    return packages


def playwright_system_deps_status() -> dict[str, object]:
    """
    Check Chromium OS library deps via ``install-deps --dry-run``.

    These are apt packages (not Playwright CDN / COS artifacts).
    """
    if platform.system().lower() != "linux":
        return {
            "checked": False,
            "ok": True,
            "missing": [],
            "reason": "non_linux",
        }
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "playwright",
                "install-deps",
                "chromium",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "checked": False,
            "ok": False,
            "missing": [],
            "reason": "dry_run_failed",
            "error": str(exc),
        }
    missing = parse_install_deps_dry_run(result.stdout, result.stderr)
    return {
        "checked": True,
        "ok": result.returncode == 0 and not missing,
        "missing": missing,
        "reason": "ok" if not missing and result.returncode == 0 else "missing_packages",
    }


def install_playwright_system_deps(*, use_sudo: bool = False) -> dict[str, object]:
    """
    Install Chromium OS deps via ``python -m playwright install-deps chromium``.

    Uses the host apt mirror (not COS). May require root / passwordless sudo.
    """
    if platform.system().lower() != "linux":
        return {"ok": True, "skipped": True, "reason": "non_linux"}
    cmd = [sys.executable, "-m", "playwright", "install-deps", "chromium"]
    if use_sudo:
        cmd = ["sudo", "-n", "-E", *cmd]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "ok": False,
            "skipped": False,
            "reason": "install_failed",
            "error": str(exc),
            "used_sudo": use_sudo,
        }
    if result.returncode != 0:
        return {
            "ok": False,
            "skipped": False,
            "reason": "install_failed",
            "returncode": result.returncode,
            "stderr": (result.stderr or "")[-500:],
            "used_sudo": use_sudo,
        }
    status = playwright_system_deps_status()
    return {
        "ok": bool(status.get("ok")),
        "skipped": False,
        "reason": "installed" if status.get("ok") else "still_missing",
        "missing": status.get("missing") or [],
        "used_sudo": use_sudo,
    }


def ensure_playwright_system_deps() -> dict[str, object]:
    """Check deps; install without sudo, then with passwordless sudo if needed."""
    status = playwright_system_deps_status()
    if status.get("ok"):
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_satisfied",
            "missing": [],
        }
    if not status.get("checked"):
        return {
            "ok": False,
            "skipped": True,
            "reason": status.get("reason") or "unchecked",
            "missing": [],
        }
    installed = install_playwright_system_deps(use_sudo=False)
    if installed.get("ok"):
        return installed
    sudo_install = install_playwright_system_deps(use_sudo=True)
    if sudo_install.get("ok"):
        return sudo_install
    missing = status.get("missing") or []
    return {
        "ok": False,
        "skipped": False,
        "reason": "needs_sudo_or_apt",
        "missing": missing,
        "hint": (f"sudo -E {sys.executable} -m playwright install-deps chromium"),
    }
