"""
Playwright Chromium apt dependency pack / offline install helpers.

Packs Ubuntu/Debian ``.deb`` files (leaf packages from Playwright's nativeDeps
plus transitive deps via ``apt-cache``) for COS offline install when apt mirrors
are unreachable.

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
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

import playwright

_PKG_RE = re.compile(r'"([a-z0-9][a-z0-9.+-]*)"')
_SECTION_ARRAY_RE = re.compile(
    r"(?P<section>tools|chromium)\s*:\s*\[(?P<pkgs>[^\]]*)\]",
    re.DOTALL,
)


def linux_os_release() -> dict[str, str]:
    """Parse ``/etc/os-release`` into a dict."""
    path = Path("/etc/os-release")
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return data
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"')
    return data


def playwright_apt_distro_key() -> Optional[str]:
    """
    Playwright nativeDeps key for this host (e.g. ``ubuntu24.04-x64``).

    Only amd64 / x86_64 is supported for COS apt bundles.
    """
    if platform.system().lower() != "linux":
        return None
    machine = platform.machine().lower()
    if machine not in ("x86_64", "amd64"):
        return None
    release = linux_os_release()
    os_id = release.get("ID", "").lower()
    version_id = release.get("VERSION_ID", "").strip()
    if not os_id or not version_id:
        return None
    if os_id == "ubuntu":
        return f"ubuntu{version_id}-x64"
    if os_id == "debian":
        return f"debian{version_id}-x64"
    return None


def _core_bundle_path() -> Optional[Path]:
    package_root = Path(playwright.__file__).resolve().parent
    candidate = package_root / "driver" / "package" / "lib" / "coreBundle.js"
    if candidate.is_file():
        return candidate
    return None


def playwright_required_apt_packages(distro_key: Optional[str] = None) -> list[str]:
    """Leaf apt packages Playwright expects for Chromium on this distro."""
    key = distro_key or playwright_apt_distro_key()
    if not key:
        return []
    bundle = _core_bundle_path()
    if bundle is None:
        return []
    try:
        text = bundle.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    marker = f'"{key}"'
    start = text.find(marker)
    if start < 0:
        return []
    # Limit scan to this distro block (until the next ubuntu/debian x64 key).
    rest = text[start : start + 12000]
    next_distro = re.search(r'\n\s*"(?:ubuntu|debian)[^"]*-x64"\s*:', rest[len(marker) :])
    region = rest[: len(marker) + next_distro.start()] if next_distro else rest
    packages: list[str] = []
    seen: set[str] = set()
    for section in _SECTION_ARRAY_RE.finditer(region):
        for pkg in _PKG_RE.findall(section.group("pkgs")):
            if pkg not in seen:
                seen.add(pkg)
                packages.append(pkg)
    return packages


def _apt_recursive_packages(leaf_packages: list[str]) -> list[str]:
    """Expand leaf packages to a recursive apt dependency set."""
    if not leaf_packages:
        return []
    cmd = [
        "apt-cache",
        "depends",
        "--recurse",
        "--no-recommends",
        "--no-suggests",
        "--no-conflicts",
        "--no-breaks",
        "--no-replaces",
        "--no-enhances",
        *leaf_packages,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return list(leaf_packages)
    if result.returncode != 0:
        return list(leaf_packages)
    packages: list[str] = []
    seen: set[str] = set()
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or ":" in line:
            continue
        if re.fullmatch(r"[a-z0-9][a-z0-9.+-]*", line) and line not in seen:
            seen.add(line)
            packages.append(line)
    return packages or list(leaf_packages)


def pack_playwright_apt_deps_to_temp(
    *,
    distro_key: Optional[str] = None,
) -> Optional[Path]:
    """
    Download ``.deb`` files for Playwright Chromium deps into a temp ``.tar.gz``.

    Requires network access to the host apt mirror (publisher side).
    """
    key = distro_key or playwright_apt_distro_key()
    if not key:
        return None
    leaf = playwright_required_apt_packages(key)
    if not leaf:
        return None
    expanded = _apt_recursive_packages(leaf)
    tmp_root = Path(tempfile.mkdtemp(prefix="mg_pw_apt_"))
    deb_dir = tmp_root / "debs"
    deb_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["apt-get", "download", *expanded],
            cwd=str(deb_dir),
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(tmp_root, ignore_errors=True)
        return None
    deb_files = sorted(deb_dir.glob("*.deb"))
    if not deb_files:
        shutil.rmtree(tmp_root, ignore_errors=True)
        return None
    manifest = tmp_root / "packages.txt"
    manifest.write_text("\n".join(expanded) + "\n", encoding="utf-8")
    meta_txt = tmp_root / "distro.txt"
    meta_txt.write_text(
        f"distro_key={key}\nleaf_count={len(leaf)}\nexpanded_count={len(expanded)}\n"
        f"deb_count={len(deb_files)}\napt_get_rc={result.returncode}\n",
        encoding="utf-8",
    )
    archive_name = f"playwright-apt-deps-{key}.tar.gz"
    archive_path = tmp_root / archive_name
    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(manifest, arcname="packages.txt")
            archive.add(meta_txt, arcname="distro.txt")
            for deb in deb_files:
                archive.add(deb, arcname=f"debs/{deb.name}")
    except (OSError, tarfile.TarError):
        shutil.rmtree(tmp_root, ignore_errors=True)
        return None
    if not archive_path.is_file() or archive_path.stat().st_size == 0:
        shutil.rmtree(tmp_root, ignore_errors=True)
        return None
    return archive_path


def local_deb_install_args(deb_files: list[Path]) -> list[str]:
    """Return apt argv entries for local ``.deb`` files (``./name.deb``)."""
    return [f"./{path.name}" for path in deb_files]


def install_playwright_apt_deps_from_tarball(
    tar_path: Path,
    *,
    use_sudo: bool = False,
) -> dict[str, object]:
    """Install ``.deb`` bundle from a COS tarball via ``apt-get install``."""
    if not tar_path.is_file():
        return {"ok": False, "reason": "tarball_not_found"}
    if platform.system().lower() != "linux":
        return {"ok": False, "reason": "non_linux"}
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_pw_apt_install_"))
    try:
        with tarfile.open(tar_path, "r:gz") as archive:
            archive.extractall(path=tmp_dir, filter="data")
    except (OSError, tarfile.TarError, ValueError):
        try:
            with tarfile.open(tar_path, "r:gz") as archive:
                archive.extractall(path=tmp_dir)
        except (OSError, tarfile.TarError):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"ok": False, "reason": "extract_failed"}
    deb_dir = tmp_dir / "debs"
    deb_files = sorted(deb_dir.glob("*.deb")) if deb_dir.is_dir() else []
    if not deb_files:
        # tarball may have flattened layout
        deb_files = sorted(tmp_dir.glob("**/*.deb"))
    if not deb_files:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"ok": False, "reason": "no_debs_in_archive"}

    # Install with cwd=debs dir. Prefix "./" so apt treats args as local .deb files
    # (required when filenames contain encoded epochs like "2%3a21...").
    install_cwd = deb_files[0].parent
    deb_names = local_deb_install_args(deb_files)
    cmd = ["apt-get", "install", "-y", "--allow-downgrades", *deb_names]
    if use_sudo:
        cmd = ["sudo", "-n", "-E", *cmd]
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    try:
        result = subprocess.run(
            cmd,
            cwd=str(install_cwd),
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {
            "ok": False,
            "reason": "install_failed",
            "error": str(exc),
            "used_sudo": use_sudo,
        }
    shutil.rmtree(tmp_dir, ignore_errors=True)
    if result.returncode != 0:
        return {
            "ok": False,
            "reason": "install_failed",
            "returncode": result.returncode,
            "stderr": (result.stderr or "")[-800:],
            "used_sudo": use_sudo,
            "deb_count": len(deb_files),
        }
    return {
        "ok": True,
        "reason": "installed",
        "used_sudo": use_sudo,
        "deb_count": len(deb_files),
    }


def ensure_playwright_apt_deps_from_tarball(tar_path: Path) -> dict[str, object]:
    """Install apt deps from tarball without sudo, then with passwordless sudo."""
    first = install_playwright_apt_deps_from_tarball(tar_path, use_sudo=False)
    if first.get("ok"):
        return first
    second = install_playwright_apt_deps_from_tarball(tar_path, use_sudo=True)
    if second.get("ok"):
        return second
    return {
        "ok": False,
        "reason": "needs_sudo_or_apt",
        "hint": (
            f"sudo -E apt-get install -y $(tar -tzf {tar_path} | "
            "grep '\\.deb$' | sed 's|^|./|')  # or extract then apt-get install ./*.deb"
        ),
        "attempts": [first, second],
    }
