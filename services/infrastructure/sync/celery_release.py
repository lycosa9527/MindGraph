"""
Celery PyPI release helpers (version detect, download wheel, pip install).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Any, Optional

CELERY_PYPI_VERSION = "5.6.3"
_WHEEL_VERSION_RE = re.compile(r"celery-(\d+\.\d+\.\d+)", re.IGNORECASE)


def celery_target_version() -> str:
    """Pinned or env override Celery release version."""
    override = os.getenv("CELERY_TARGET_VERSION", "").strip()
    if override:
        return override.lstrip("v")
    return CELERY_PYPI_VERSION


def detect_installed_celery_version() -> Optional[str]:
    """Read installed Celery version from pip or import metadata."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "celery"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0:
        for line in result.stdout.splitlines():
            if line.lower().startswith("version:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    try:
        return pkg_version("celery")
    except PackageNotFoundError:
        return None


def parse_celery_wheel_version(wheel_path: Path) -> Optional[str]:
    """Extract semver from a celery-*.whl filename."""
    match = _WHEEL_VERSION_RE.search(wheel_path.name)
    if match:
        return match.group(1)
    return None


def resolve_celery_wheel_path(archive_path: Path) -> Optional[Path]:
    """Return a local .whl path from a wheel file or zip archive containing one."""
    if not archive_path.is_file():
        return None
    suffix = archive_path.suffix.lower()
    if suffix == ".whl":
        return archive_path
    if suffix != ".zip":
        return None
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            wheel_names = [name for name in archive.namelist() if name.endswith(".whl")]
            if not wheel_names:
                return None
            tmp_dir = Path(tempfile.mkdtemp(prefix="mg_celery_wheel_"))
            archive.extract(wheel_names[0], tmp_dir)
            wheel_path = tmp_dir / wheel_names[0]
            if wheel_path.is_file():
                return wheel_path
    except (OSError, zipfile.BadZipFile, ValueError):
        return None
    return None


def _pypi_json(version: str) -> Optional[dict[str, Any]]:
    url = f"https://pypi.org/pypi/celery/{version.lstrip('v')}/json"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def select_pypi_wheel_url(version: str) -> Optional[tuple[str, str]]:
    """Return (download_url, filename) for the best matching wheel on PyPI."""
    payload = _pypi_json(version)
    if not payload:
        return None
    urls = payload.get("urls")
    if not isinstance(urls, list):
        return None
    wheels: list[dict[str, Any]] = [
        item for item in urls if isinstance(item, dict) and item.get("packagetype") == "bdist_wheel"
    ]
    if not wheels:
        return None
    preferred = None
    for item in wheels:
        filename = str(item.get("filename") or "")
        if filename.endswith("py3-none-any.whl"):
            preferred = item
            break
    chosen = preferred or wheels[0]
    download_url = str(chosen.get("url") or "")
    filename = str(chosen.get("filename") or "")
    if not download_url or not filename:
        return None
    return download_url, filename


def download_pypi_wheel_to_temp(version: str) -> Optional[Path]:
    """Download Celery wheel from PyPI into a temp directory."""
    selected = select_pypi_wheel_url(version)
    if selected is None:
        return None
    download_url, filename = selected
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_celery_"))
    dest = tmp_dir / filename
    try:
        with urllib.request.urlopen(download_url, timeout=600) as response:
            dest.write_bytes(response.read())
    except (urllib.error.URLError, OSError):
        return None
    if not dest.is_file() or dest.stat().st_size == 0:
        return None
    return dest


def install_celery_from_wheel(wheel_path: Path) -> bool:
    """Install or upgrade Celery from a local wheel via pip."""
    if not wheel_path.is_file():
        return False
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                str(wheel_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
